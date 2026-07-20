from __future__ import annotations

import re
import uuid
from typing import Any

from mcp.server.fastmcp import FastMCP

from spie_mcp.client import ServiceNowClient


mcp = FastMCP("spie", json_response=True)


def _client() -> ServiceNowClient:
    return ServiceNowClient.from_env()


def _fields_list(fields: str) -> list[str] | None:
    values = [value.strip() for value in fields.split(",") if value.strip()]
    return values or None


def _clean_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in payload.items()
        if value is not None and not (isinstance(value, str) and value == "")
    }


def _normalize_bool(value: bool | str) -> bool:
    if isinstance(value, bool):
        return value
    return value.strip().lower() in {"true", "1", "yes", "y"}


def _extract_value(field: Any) -> Any:
    if isinstance(field, dict) and "value" in field:
        return field["value"]
    return field


def _resolve_atf_input_variable_sys_id(
    step_config_sys_id: str,
    *,
    variable_sys_id: str = "",
    reference_table: str = "",
) -> str:
    if variable_sys_id:
        return variable_sys_id

    variables = _client().get_records(
        "atf_input_variable",
        query=f"model_id={step_config_sys_id}",
        fields=["sys_id", "reference", "name", "order"],
        limit=20,
    ).get("result", [])

    if not isinstance(variables, list) or not variables:
        raise ValueError(f"No ATF input variables found for step_config_sys_id={step_config_sys_id}.")

    if reference_table:
        matches = [
            row
            for row in variables
            if str(_extract_value(row.get("reference", ""))) == reference_table
        ]
        if len(matches) == 1:
            return str(_extract_value(matches[0].get("sys_id")))
        if len(matches) > 1:
            raise ValueError(
                f"Multiple ATF input variables matched reference_table={reference_table}; provide variable_sys_id explicitly."
            )
        raise ValueError(
            f"No ATF input variable matched reference_table={reference_table} for step_config_sys_id={step_config_sys_id}."
        )

    if len(variables) == 1:
        return str(_extract_value(variables[0].get("sys_id")))

    raise ValueError(
        "Multiple ATF input variables are available for this step config; provide variable_sys_id or reference_table."
    )


def _update_payload(values: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in _clean_payload(values).items() if value is not None}


def _normalized_phrase(value: str) -> str:
    return " ".join(value.split()).strip()


def _analysis_terms(problem_statement: str) -> list[str]:
    phrase = _normalized_phrase(problem_statement)
    if not phrase:
        raise ValueError("problem_statement is required.")

    terms = [phrase]
    for token in re.split(r"[^A-Za-z0-9]+", phrase):
        normalized = token.strip()
        if len(normalized) < 3:
            continue
        if normalized.lower() not in {term.lower() for term in terms}:
            terms.append(normalized)
    return terms[:6]


def _analysis_query(fields: list[str], terms: list[str]) -> str:
    clauses: list[str] = []
    for term in terms:
        safe_term = term.replace("^", " ").strip()
        if not safe_term:
            continue
        clauses.extend(f"{field}LIKE{safe_term}" for field in fields)
    return "^OR".join(clauses)


def _string_value(value: Any) -> str:
    extracted = _extract_value(value)
    if extracted is None:
        return ""
    return str(extracted).strip()


def _analysis_sample(
    row: dict[str, Any],
    *,
    title_fields: list[str],
    detail_fields: list[str],
) -> dict[str, Any]:
    title = next((_string_value(row.get(field)) for field in title_fields if _string_value(row.get(field))), "")
    details = {
        field: _string_value(row.get(field))
        for field in detail_fields
        if _string_value(row.get(field))
    }
    sample = {"sys_id": _string_value(row.get("sys_id")), "title": title}
    if details:
        sample["details"] = details
    return sample


def _collect_analysis_area(
    *,
    client: ServiceNowClient,
    key: str,
    label: str,
    table: str,
    query_fields: list[str],
    result_fields: list[str],
    title_fields: list[str],
    detail_fields: list[str],
    terms: list[str],
    sample_limit: int,
) -> dict[str, Any]:
    query = _analysis_query(query_fields, terms)
    count = client.count_records(table, query=query)
    area: dict[str, Any] = {"key": key, "label": label, "table": table, "count": count, "query": query}

    if count > 0 and sample_limit > 0:
        response = client.get_records(
            table,
            query=query,
            fields=result_fields,
            limit=sample_limit,
            display_value="all",
        )
        records = response.get("result", [])
        if isinstance(records, list):
            area["samples"] = [
                _analysis_sample(row, title_fields=title_fields, detail_fields=detail_fields)
                for row in records
                if isinstance(row, dict)
            ]

    area["has_more"] = count > len(area.get("samples", []))
    return area


def _analysis_recommendations(problem_statement: str, areas: list[dict[str, Any]]) -> list[str]:
    total_matches = sum(int(area.get("count", 0)) for area in areas)
    populated_areas = [area for area in areas if int(area.get("count", 0)) > 0]

    if not populated_areas:
        return [
            f"No related artifacts were found for '{problem_statement}'. You likely need a net-new design, but validate naming and scope choices before creating records.",
        ]

    recommendations = [
        f"Found {total_matches} related artifacts across {len(populated_areas)} areas. Review those first to avoid duplicating data models, automation, or request experiences.",
    ]

    labels = {str(area.get('label')) for area in populated_areas}
    if "Applications" in labels or "Tables" in labels:
        recommendations.append("Start by extending an existing application scope or data model when ownership and lifecycle already align with the requested capability.")
    if "Flows" in labels or "Catalog Items" in labels:
        recommendations.append("Reuse existing flows and catalog entry points before adding new orchestration or request surfaces.")
    if "Script Includes" in labels:
        recommendations.append("Inspect the related Script Includes for reusable business logic before introducing new server-side APIs.")

    return recommendations


def _analysis_next_step(areas: list[dict[str, Any]]) -> str:
    populated_areas = [area for area in areas if int(area.get("count", 0)) > 0]
    if not populated_areas:
        return "No close matches were found. Do you want to sketch a net-new application design with governance checks?"

    labels = ", ".join(area["label"].lower() for area in populated_areas)
    return f"I found related {labels}. Would you like to extend these instead of creating new ones?"


def _analysis_area_configs() -> list[dict[str, Any]]:
    return [
        {
            "key": "tables",
            "label": "Tables",
            "table": "sys_db_object",
            "query_fields": ["name", "label"],
            "result_fields": ["sys_id", "name", "label", "sys_scope"],
            "title_fields": ["label", "name"],
            "detail_fields": ["name", "sys_scope"],
        },
        {
            "key": "script_includes",
            "label": "Script Includes",
            "table": "sys_script_include",
            "query_fields": ["name", "api_name", "description"],
            "result_fields": ["sys_id", "name", "api_name", "description"],
            "title_fields": ["name", "api_name"],
            "detail_fields": ["api_name", "description"],
        },
        {
            "key": "applications",
            "label": "Applications",
            "table": "sys_scope",
            "query_fields": ["name", "scope", "short_description"],
            "result_fields": ["sys_id", "name", "scope", "short_description"],
            "title_fields": ["name", "scope"],
            "detail_fields": ["scope", "short_description"],
        },
        {
            "key": "flows",
            "label": "Flows",
            "table": "sys_hub_flow",
            "query_fields": ["name", "description"],
            "result_fields": ["sys_id", "name", "description"],
            "title_fields": ["name"],
            "detail_fields": ["description"],
        },
        {
            "key": "catalog_items",
            "label": "Catalog Items",
            "table": "sc_cat_item",
            "query_fields": ["name", "short_description", "description"],
            "result_fields": ["sys_id", "name", "short_description", "description"],
            "title_fields": ["name"],
            "detail_fields": ["short_description", "description"],
        },
        {
            "key": "business_rules",
            "label": "Business Rules",
            "table": "sys_script",
            "query_fields": ["name", "collection", "filter_condition"],
            "result_fields": ["sys_id", "name", "collection", "when", "filter_condition"],
            "title_fields": ["name"],
            "detail_fields": ["collection", "when", "filter_condition"],
        },
        {
            "key": "client_scripts",
            "label": "Client Scripts",
            "table": "sys_script_client",
            "query_fields": ["name", "table", "field"],
            "result_fields": ["sys_id", "name", "table", "type", "field"],
            "title_fields": ["name"],
            "detail_fields": ["table", "type", "field"],
        },
        {
            "key": "catalog_client_scripts",
            "label": "Catalog Client Scripts",
            "table": "catalog_script_client",
            "query_fields": ["name", "type"],
            "result_fields": ["sys_id", "name", "type", "cat_item", "variable_set"],
            "title_fields": ["name"],
            "detail_fields": ["type", "cat_item", "variable_set"],
        },
        {
            "key": "ui_actions",
            "label": "UI Actions",
            "table": "sys_ui_action",
            "query_fields": ["name", "action_name", "table"],
            "result_fields": ["sys_id", "name", "action_name", "table", "client"],
            "title_fields": ["name", "action_name"],
            "detail_fields": ["action_name", "table", "client"],
        },
        {
            "key": "ui_pages",
            "label": "UI Pages",
            "table": "sys_ui_page",
            "query_fields": ["name"],
            "result_fields": ["sys_id", "name", "direct"],
            "title_fields": ["name"],
            "detail_fields": ["direct"],
        },
        {
            "key": "system_properties",
            "label": "System Properties",
            "table": "sys_properties",
            "query_fields": ["name", "description"],
            "result_fields": ["sys_id", "name", "description", "type"],
            "title_fields": ["name"],
            "detail_fields": ["description", "type"],
        },
        {
            "key": "atf_tests",
            "label": "ATF Tests",
            "table": "sys_atf_test",
            "query_fields": ["name", "description"],
            "result_fields": ["sys_id", "name", "description", "active"],
            "title_fields": ["name"],
            "detail_fields": ["description", "active"],
        },
    ]


def _analysis_area_map(analysis: dict[str, Any]) -> dict[str, dict[str, Any]]:
    areas = analysis.get("areas", [])
    if not isinstance(areas, list):
        return {}
    return {
        str(area.get("key")): area
        for area in areas
        if isinstance(area, dict) and area.get("key")
    }


def _contains_any(text: str, phrases: list[str]) -> bool:
    normalized = text.lower()
    return any(phrase.lower() in normalized for phrase in phrases)


def _score_check(
    checks: list[dict[str, Any]],
    *,
    name: str,
    passed: bool,
    weight: int,
    detail: str,
    standard: str,
) -> None:
    checks.append(
        {
            "name": name,
            "passed": passed,
            "weight": weight,
            "detail": detail,
            "standard": standard,
        }
    )


def _parsed_artifacts(proposed_artifacts: str) -> list[dict[str, str]]:
    parsed: list[dict[str, str]] = []
    for item in proposed_artifacts.split(";"):
        value = item.strip()
        if not value:
            continue
        artifact_type, separator, name = value.partition(":")
        if not separator:
            continue
        parsed.append({"type": artifact_type.strip().lower(), "name": name.strip()})
    return parsed


def _artifact_naming_checks(parsed_artifacts: list[dict[str, str]]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for artifact in parsed_artifacts:
        artifact_type = artifact["type"]
        name = artifact["name"]
        if not name:
            continue

        if artifact_type == "script_include":
            passed = bool(re.fullmatch(r"[A-Z][A-Za-z0-9]+(?:Helper|Service|Validator)", name))
            _score_check(
                checks,
                name=f"{artifact_type} naming",
                passed=passed,
                weight=8,
                detail=f"Script Include '{name}' should follow CompanyPrefixFeatureHelper/Service/Validator naming.",
                standard="ServiceNow Governance Standards > Script Includes",
            )
        elif artifact_type == "business_rule":
            passed = name.count(" - ") >= 2
            _score_check(
                checks,
                name=f"{artifact_type} naming",
                passed=passed,
                weight=8,
                detail=f"Business Rule '{name}' should follow '<Table> - <Trigger or Outcome> - <Short Purpose>'.",
                standard="ServiceNow Governance Standards > Business Rules",
            )
        elif artifact_type in {"client_script", "catalog_client_script"}:
            passed = name.count(" - ") >= 2
            _score_check(
                checks,
                name=f"{artifact_type} naming",
                passed=passed,
                weight=7,
                detail=f"Client script '{name}' should follow '<Table or Item> - <Behavior> - <Purpose>'.",
                standard="ServiceNow Governance Standards > Client Scripts and Catalog Client Scripts",
            )
        elif artifact_type == "catalog_item":
            passed = name.count(" - ") >= 1
            _score_check(
                checks,
                name=f"{artifact_type} naming",
                passed=passed,
                weight=7,
                detail=f"Catalog item '{name}' should follow '<Category> - <Request Name>'.",
                standard="ServiceNow Governance Standards > Catalog Items",
            )
        elif artifact_type == "ui_action":
            passed = name.count(" - ") >= 1
            _score_check(
                checks,
                name=f"{artifact_type} naming",
                passed=passed,
                weight=6,
                detail=f"UI Action '{name}' should follow '<Table> - <Action Name>'.",
                standard="ServiceNow Governance Standards > UI Actions and UI Pages",
            )
        elif artifact_type == "ui_page":
            passed = name.endswith(" Page")
            _score_check(
                checks,
                name=f"{artifact_type} naming",
                passed=passed,
                weight=6,
                detail=f"UI Page '{name}' should end with 'Page'.",
                standard="ServiceNow Governance Standards > UI Actions and UI Pages",
            )
        elif artifact_type == "atf_test":
            passed = name.startswith("ATF - ")
            _score_check(
                checks,
                name=f"{artifact_type} naming",
                passed=passed,
                weight=8,
                detail=f"ATF test '{name}' should start with 'ATF - '.",
                standard="ServiceNow Governance Standards > ATF Tests",
            )
        elif artifact_type == "system_property":
            passed = bool(re.fullmatch(r"[a-z0-9]+(?:\.[a-z0-9_]+)+", name))
            _score_check(
                checks,
                name=f"{artifact_type} naming",
                passed=passed,
                weight=7,
                detail=f"System property '{name}' should use lowercase dotted naming.",
                standard="ServiceNow Governance Standards > System Properties",
            )
    return checks


def _update_set_naming_assessment(update_set_name: str) -> dict[str, Any]:
    normalized = _normalized_phrase(update_set_name)
    parts = [part.strip() for part in normalized.split(" - ")]
    allowed_suffixes = {"DEV", "TEST", "QA", "UAT", "PROD", "PRD", "STAGE", "STAGING", "HOTFIX"}

    name_ok = len(parts) == 3 and all(parts)
    suffix_ok = False
    suffix = ""
    if name_ok:
        suffix = parts[2].upper()
        suffix_ok = bool(
            re.fullmatch(r"(?:[A-Z]{2,}|[A-Z]+\d+)", suffix)
            or re.fullmatch(r"(?:INC|CHG|TASK)\d+", suffix)
            or suffix in allowed_suffixes
        )

    passed = name_ok and suffix_ok
    detail = "Update set names should follow '<APP or DOMAIN> - <SHORT PURPOSE> - <ENV or TICKET>'."
    if passed:
        detail = "Update set naming matches the documented convention."
    else:
        if len(parts) != 3:
            detail = "Use exactly three parts separated by ' - ': '<APP or DOMAIN> - <SHORT PURPOSE> - <ENV or TICKET>'."
        elif not suffix_ok:
            detail = "The final segment should be a clear environment or work-item identifier such as DEV, TEST, UAT, PROD, INC12345, or CHG67890."

    return {
        "name": normalized,
        "parts": parts,
        "passed": passed,
        "detail": detail,
        "standard": "ServiceNow Governance Standards > Update Sets",
    }


def _validated_update_set_name(update_set_name: str) -> str:
    assessment = _update_set_naming_assessment(update_set_name)
    if not assessment["passed"]:
        raise ValueError(assessment["detail"])
    return str(assessment["name"])


def _strategy_from_analysis(
    analysis: dict[str, Any],
    *,
    problem_statement: str,
    needs_request_experience: bool,
    needs_workflow: bool,
    needs_server_logic: bool,
    needs_custom_data_model: bool,
    needs_external_integration: bool,
    prefer_existing_scope: bool,
) -> dict[str, Any]:
    area_map = _analysis_area_map(analysis)
    summary = analysis.get("summary", {}) if isinstance(analysis.get("summary"), dict) else {}

    app_count = int(summary.get("applications", 0))
    table_count = int(summary.get("tables", 0))
    flow_count = int(summary.get("flows", 0))
    script_include_count = int(summary.get("script_includes", 0))
    catalog_item_count = int(summary.get("catalog_items", 0))

    if prefer_existing_scope and (app_count > 0 or table_count > 0):
        strategy = "extend_existing"
    elif needs_custom_data_model and app_count == 0 and table_count == 0:
        strategy = "create_new_scoped_app"
    else:
        strategy = "hybrid"

    rationale: list[str] = []
    if strategy == "extend_existing":
        rationale.append("Existing application or table matches were found, so extending the current model is the lowest-duplication path.")
    elif strategy == "create_new_scoped_app":
        rationale.append("No close application or data-model matches were found, so a new scoped app is the cleaner boundary.")
    else:
        rationale.append("The instance has reusable assets, but not enough direct ownership fit to recommend a pure extension path.")

    building_blocks: list[str] = []
    if needs_custom_data_model:
        building_blocks.append("Define only the minimum custom tables and fields needed after validating out-of-box coverage.")
    if needs_server_logic:
        if script_include_count > 0:
            building_blocks.append("Extend or wrap an existing Script Include before creating new server-side service layers.")
        else:
            building_blocks.append("Create a focused Script Include service layer for reusable server-side logic.")
    if needs_workflow:
        if flow_count > 0:
            building_blocks.append("Reuse an existing flow or subflow as the orchestration anchor where the lifecycle matches.")
        else:
            building_blocks.append("Model orchestration in Flow Designer with narrow triggers and explicit error branches.")
    if needs_request_experience:
        if catalog_item_count > 0:
            building_blocks.append("Reuse an existing catalog item or variable pattern before creating a new request surface.")
        else:
            building_blocks.append("Add a catalog experience only if the solution needs a user-facing request path.")
    if needs_external_integration:
        building_blocks.append("Use credential aliases, timeouts, retries, and versioned API boundaries for outbound or inbound integrations.")

    reuse_candidates: list[dict[str, Any]] = []
    for key in ["applications", "tables", "script_includes", "flows", "catalog_items"]:
        area = area_map.get(key)
        if not area or int(area.get("count", 0)) <= 0:
            continue
        reuse_candidates.append(
            {
                "area": area["label"],
                "count": area["count"],
                "samples": area.get("samples", []),
            }
        )

    risks: list[str] = []
    if strategy != "create_new_scoped_app" and needs_custom_data_model and table_count > 0:
        risks.append("Creating more custom tables without reconciling the existing model will increase duplicate data structures.")
    if needs_request_experience and catalog_item_count > 0:
        risks.append("A new catalog item may duplicate an existing intake path unless variables and approvals are aligned.")
    if needs_workflow and flow_count > 0:
        risks.append("Adding new flows without checking existing triggers can create overlapping automation.")
    if needs_external_integration:
        risks.append("Integrations need explicit validation, timeout, retry, and least-privilege design before implementation.")

    return {
        "problem_statement": _normalized_phrase(problem_statement),
        "strategy": strategy,
        "rationale": rationale,
        "building_blocks": building_blocks,
        "reuse_candidates": reuse_candidates,
        "risks": risks,
    }


def _governance_assessment(
    *,
    problem_statement: str,
    proposed_scope: str,
    proposed_artifacts: str,
    business_purpose: str,
    reuse_plan: str,
    test_plan: str,
    security_model: str,
    integration_notes: str,
    update_set_name: str,
    uses_global_scope: bool,
    creates_new_tables: bool,
    uses_client_scripts: bool,
    uses_ui_policies: bool,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    parsed_artifacts = _parsed_artifacts(proposed_artifacts)

    _score_check(
        checks,
        name="scope",
        passed=not uses_global_scope and proposed_scope.strip().lower() != "global",
        weight=15,
        detail="Prefer application scope over global scope unless a global artifact is required.",
        standard="ServiceNow Governance Standards > General Rules",
    )
    _score_check(
        checks,
        name="business purpose",
        passed=len(_normalized_phrase(business_purpose)) >= 15,
        weight=12,
        detail="Document the business purpose of every custom artifact.",
        standard="ServiceNow Governance Standards > General Rules",
    )
    _score_check(
        checks,
        name="reuse strategy",
        passed=_contains_any(reuse_plan, ["reuse", "extend", "script include", "subflow", "existing"]),
        weight=14,
        detail="Reuse logic and existing platform assets instead of duplicating them.",
        standard="ServiceNow Governance Standards > Quick Checklist",
    )
    _score_check(
        checks,
        name="test strategy",
        passed=_contains_any(test_plan, ["atf", "test", "validate", "rollback", "cleanup"]),
        weight=14,
        detail="Changes should include test coverage or equivalent validation, ideally with ATF for critical paths.",
        standard="ServiceNow Best Practices > ATF and Testing",
    )
    _score_check(
        checks,
        name="security model",
        passed=_contains_any(security_model, ["acl", "role", "least privilege", "credential", "alias", "impersonation"]),
        weight=14,
        detail="Use ACLs, least privilege, and secure credential handling instead of ad hoc checks or secrets in code.",
        standard="ServiceNow Best Practices > Security and Access Control",
    )
    _score_check(
        checks,
        name="update set naming",
        passed=_update_set_naming_assessment(update_set_name)["passed"],
        weight=10,
        detail=_update_set_naming_assessment(update_set_name)["detail"],
        standard="ServiceNow Governance Standards > Update Sets",
    )
    _score_check(
        checks,
        name="integration resilience",
        passed=(not integration_notes.strip()) or _contains_any(integration_notes, ["timeout", "retry", "version", "correlation", "validate"]),
        weight=10,
        detail="Integrations should define timeout, retry, versioning, validation, and traceability expectations.",
        standard="ServiceNow Best Practices > Integrations and APIs",
    )
    _score_check(
        checks,
        name="data model restraint",
        passed=(not creates_new_tables) or _contains_any(reuse_plan, ["out-of-box", "reuse", "existing table", "reference"]),
        weight=8,
        detail="Reuse out-of-box tables and fields before creating new schema.",
        standard="ServiceNow Best Practices > Data Model and CMDB",
    )
    _score_check(
        checks,
        name="client-side restraint",
        passed=(not uses_client_scripts) or uses_ui_policies,
        weight=7,
        detail="Prefer UI Policies for simple field behavior and keep client scripts minimal.",
        standard="ServiceNow Governance Standards > Client Scripts and Catalog Client Scripts",
    )

    checks.extend(_artifact_naming_checks(parsed_artifacts))

    achieved = sum(check["weight"] for check in checks if check["passed"])
    possible = sum(check["weight"] for check in checks) or 1
    score = round((achieved / possible) * 100)

    failures = [check for check in checks if not check["passed"]]
    strengths = [check for check in checks if check["passed"]]
    recommendations = [check["detail"] for check in failures[:6]]

    return {
        "problem_statement": _normalized_phrase(problem_statement),
        "score": score,
        "rating": "strong" if score >= 85 else "moderate" if score >= 65 else "weak",
        "checks": checks,
        "strengths": strengths[:6],
        "gaps": failures[:6],
        "recommendations": recommendations,
    }


def _integration_request_flags(integration_request: str) -> dict[str, bool]:
    text = _normalized_phrase(integration_request).lower()
    return {
        "batch": _contains_any(text, ["batch", "file", "csv", "flat file", "scheduled", "import set", "etl"]),
        "real_time": _contains_any(text, ["real time", "real-time", "near real-time", "event", "sync", "immediate"]),
        "oauth": _contains_any(text, ["oauth", "bearer", "token", "sso"]),
        "mid_network": _contains_any(text, ["mid", "mid server", "on-prem", "private network", "firewall"]),
        "api": _contains_any(text, ["rest", "soap", "api", "odata", "web service"]),
        "message_based": _contains_any(text, ["soap", "web service", "message", "payload"]),
    }


def _integration_keywords(integration_request: str) -> list[str]:
    stopwords = {
        "and",
        "any",
        "api",
        "application",
        "build",
        "for",
        "from",
        "how",
        "i",
        "in",
        "integrate",
        "integration",
        "need",
        "of",
        "product",
        "service",
        "servicenow",
        "should",
        "the",
        "to",
        "with",
        "what",
    }
    keywords: list[str] = []
    for token in re.split(r"[^A-Za-z0-9]+", _normalized_phrase(integration_request).lower()):
        token = token.strip()
        if len(token) < 3 or token in stopwords:
            continue
        if token not in keywords:
            keywords.append(token)
    return keywords[:5]


def _integration_target_name(integration_request: str) -> str:
    keywords = _integration_keywords(integration_request)
    if not keywords:
        return ""
    return keywords[0]


def _project_record(row: dict[str, Any], fields: list[str]) -> dict[str, Any]:
    sample: dict[str, Any] = {"sys_id": _string_value(row.get("sys_id"))}
    for field in fields:
        value = _string_value(row.get(field))
        if value:
            sample[field] = value
    return sample


def _collect_architecture_signal(
    *,
    client: ServiceNowClient,
    key: str,
    label: str,
    table: str,
    fields: list[str],
    query: str | None = None,
    sample_limit: int = 3,
) -> dict[str, Any]:
    try:
        count = client.count_records(table, query=query)
        records = client.get_records(
            table,
            query=query,
            fields=fields,
            limit=sample_limit,
            display_value="all",
        ).get("result", [])
        samples = [
            _project_record(row, fields)
            for row in records
            if isinstance(row, dict)
        ] if isinstance(records, list) else []

        return {
            "key": key,
            "label": label,
            "table": table,
            "count": count,
            "query": query,
            "available": True,
            "samples": samples,
            "has_more": count > len(samples),
        }
    except Exception as exc:  # pragma: no cover - runtime instance diagnostics
        return {
            "key": key,
            "label": label,
            "table": table,
            "available": False,
            "error": str(exc),
        }


def _integration_architecture_signals(problem_statement: str, sample_limit: int) -> list[dict[str, Any]]:
    keywords = _integration_keywords(problem_statement)
    keyword_query = _analysis_query(["name", "description", "endpoint", "source_table", "target_table"], keywords) if keywords else None
    client = _client()
    return [
        _collect_architecture_signal(
            client=client,
            key="mid_servers",
            label="MID Servers",
            table="ecc_agent",
            fields=["name", "agent_version", "status"],
            sample_limit=sample_limit,
        ),
        _collect_architecture_signal(
            client=client,
            key="integrationhub_plugins",
            label="IntegrationHub Plugins",
            table="sys_plugins",
            fields=["name", "active", "description"],
            query="nameLIKEIntegrationHub^ORdescriptionLIKEIntegrationHub^ORnameLIKEintegrationhub",
            sample_limit=sample_limit,
        ),
        _collect_architecture_signal(
            client=client,
            key="integration_actions",
            label="Integration Actions",
            table="sys_hub_action_type_definition",
            fields=["name", "description", "active"],
            query=keyword_query,
            sample_limit=sample_limit,
        ),
        _collect_architecture_signal(
            client=client,
            key="rest_messages",
            label="REST Messages",
            table="sys_rest_message",
            fields=["name", "endpoint", "authentication_type", "active"],
            query=keyword_query,
            sample_limit=sample_limit,
        ),
        _collect_architecture_signal(
            client=client,
            key="soap_messages",
            label="SOAP Messages",
            table="sys_ws_definition",
            fields=["name", "endpoint", "active"],
            query=keyword_query,
            sample_limit=sample_limit,
        ),
        _collect_architecture_signal(
            client=client,
            key="oauth_providers",
            label="OAuth Providers",
            table="sys_oauth_provider",
            fields=["name", "grant_type", "active"],
            query=keyword_query,
            sample_limit=sample_limit,
        ),
        _collect_architecture_signal(
            client=client,
            key="import_sets",
            label="Import Sets",
            table="sys_import_set",
            fields=["name", "state", "sys_created_on"],
            query=keyword_query,
            sample_limit=sample_limit,
        ),
        _collect_architecture_signal(
            client=client,
            key="transform_maps",
            label="Transform Maps",
            table="sys_transform_map",
            fields=["name", "source_table", "target_table", "active"],
            query=keyword_query,
            sample_limit=sample_limit,
        ),
        _collect_architecture_signal(
            client=client,
            key="ecc_properties",
            label="ECC Properties",
            table="sys_properties",
            fields=["name", "value", "description"],
            query="nameLIKEglide.ecc^ORnameLIKEecc",
            sample_limit=sample_limit,
        ),
    ]


def _first_available_sample(areas: list[dict[str, Any]], key: str) -> dict[str, Any] | None:
    for area in areas:
        if area.get("key") == key and area.get("available") and area.get("samples"):
            samples = area.get("samples")
            if isinstance(samples, list) and samples:
                first = samples[0]
                return first if isinstance(first, dict) else None
    return None


def _architecture_matched_assets(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    matched: list[dict[str, Any]] = []
    for area in signals:
        if not area.get("available"):
            continue
        samples = area.get("samples", [])
        if not isinstance(samples, list):
            continue
        for sample in samples:
            if not isinstance(sample, dict):
                continue
            matched.append(
                {
                    "category": area.get("label"),
                    "sys_id": sample.get("sys_id", ""),
                    "name": sample.get("name") or sample.get("title") or sample.get("endpoint") or "",
                }
            )
    return matched[:12]


def _recommend_integration_architecture(
    problem_statement: str,
    signals: list[dict[str, Any]],
) -> dict[str, Any]:
    summary = {
        area["key"]: int(area.get("count", 0)) if area.get("available") else 0
        for area in signals
    }
    flags = _integration_request_flags(problem_statement)
    mid_servers = summary.get("mid_servers", 0)
    integrationhub_plugins = summary.get("integrationhub_plugins", 0)
    integration_actions = summary.get("integration_actions", 0)
    rest_messages = summary.get("rest_messages", 0)
    soap_messages = summary.get("soap_messages", 0)
    oauth_providers = summary.get("oauth_providers", 0)
    import_sets = summary.get("import_sets", 0)
    transform_maps = summary.get("transform_maps", 0)
    target_name = _integration_target_name(problem_statement)

    ecc_sample = _first_available_sample(signals, "ecc_properties")
    ecc_version_signal = ""
    if ecc_sample:
        ecc_version_signal = ecc_sample.get("value", "") or ecc_sample.get("description", "")

    matched_assets = _architecture_matched_assets(signals)
    has_target_specific_assets = any(target_name and target_name.lower() in str(asset.get("name", "")).lower() for asset in matched_assets)

    if flags["batch"] or import_sets > 0 and not flags["real_time"]:
        architecture = {
            "name": "Import Sets + Transform Maps + Flow Designer",
            "pattern": "Use batch ingestion with import sets, transform maps, and orchestration for downstream processing.",
            "why": [
                "The instance already has import-set or transform-map signals, which points to a batch-oriented integration path.",
                "This is the cleanest fit when the source delivers files, extracts, or scheduled payloads rather than synchronous requests.",
            ],
            "prerequisites": [
                "Define inbound file or payload validation.",
                "Keep transform logic small and reusable.",
                "Add ATF or equivalent validation for import outcomes.",
            ],
            "implementation_sequence": [
                "Land incoming data into an import set table.",
                "Normalize and map the payload with transform maps.",
                "Trigger follow-up processing in Flow Designer or Script Includes.",
            ],
            "risks": [
                "Batch processing can hide data-quality issues until transform time.",
                "Overlapping schedules can duplicate imports if controls are weak.",
            ],
        }
    elif integrationhub_plugins > 0 and mid_servers > 0 and (integration_actions > 0 or rest_messages > 0 or soap_messages > 0):
        architecture = {
            "name": "IntegrationHub + MID Server",
            "pattern": "Use IntegrationHub with a MID Server for secure connectivity to the target system.",
            "why": [
                "The instance already has an active MID Server signal and integration action coverage, which is the lowest-friction reusable path.",
                "IntegrationHub plus MID Server is the best fit when the target is on-prem or behind network boundaries.",
            ],
            "prerequisites": [
                "Confirm the IntegrationHub entitlement or plugin signal in the instance.",
                "Verify MID Server health, version, and network reachability.",
                "Map the target system operation to the spoke or action surface before coding custom integrations.",
            ],
            "implementation_sequence": [
                "Use the existing spoke or integration action if it matches the business operation.",
                "Route calls through MID Server for network isolation and credential containment.",
                "Wrap the spoke invocation in Flow Designer or Script Includes for reuse.",
            ],
            "risks": [
                "If the target behavior diverges from the available action, custom orchestration may still be needed.",
                "MID Server outages will block real-time requests unless you design a fallback path.",
            ],
        }
    elif integrationhub_plugins > 0 and (integration_actions > 0 or rest_messages > 0 or soap_messages > 0):
        architecture = {
            "name": "IntegrationHub with MID Server Gap",
            "pattern": "Use IntegrationHub, but add a MID Server before production if the target is not directly reachable.",
            "why": [
                "The instance shows integration coverage and IntegrationHub, but no MID Server signal.",
                "For targets behind internal firewalls, the MID Server is usually the missing transport layer.",
            ],
            "prerequisites": [
                "Install or validate a MID Server.",
                "Confirm network path, certificates, and outbound trust.",
            ],
            "implementation_sequence": [
                "Prototype the spoke or action flow in a dev instance.",
                "Add the MID Server and verify connectivity.",
                "Promote the reusable orchestration once network access is proven.",
            ],
            "risks": [
                "A spoke or action without transport does not solve connectivity by itself.",
                "Direct connectivity assumptions can break in on-prem target environments.",
            ],
        }
    elif oauth_providers > 0 and flags["api"]:
        architecture = {
            "name": "REST/SOAP API Integration with OAuth",
            "pattern": "Use direct API integration with OAuth-based authentication, then add MID Server only if network constraints require it.",
            "why": [
                "OAuth provider signals exist in the instance, so secure token-based integration is already plausible.",
                "This is the best fit when the target exposes REST or SOAP endpoints and the network path is reachable.",
            ],
            "prerequisites": [
                "Register the target endpoint and confirm auth flow.",
                "Use a credential strategy instead of hard-coded secrets.",
                "Add retries, timeouts, and correlation IDs for observability.",
            ],
            "implementation_sequence": [
                "Call the target system through a scoped integration layer or Script Include.",
                "Use OAuth or bearer-token handling from a secure credential store.",
                "Orchestrate retries and error handling in Flow Designer or server-side code.",
            ],
            "risks": [
                "If the target is not directly reachable, you will still need a MID Server.",
                "Synchronous API calls can become brittle without careful timeout design.",
            ],
        }
    else:
        architecture = {
            "name": "Hybrid Integration Architecture",
            "pattern": "Start with the smallest transport that matches the instance, then add MID Server, spokes, or batch processing only where needed.",
            "why": [
                "The instance signals are incomplete or mixed, so a rigid pattern would be premature.",
                "This path keeps the design flexible while you validate connectivity and data shape.",
            ],
            "prerequisites": [
                "Confirm whether the target is on-prem, cloud, or mixed.",
                "Validate whether the process is real-time or batch.",
                "Identify whether the instance already has reusable spokes, transforms, or OAuth providers.",
            ],
            "implementation_sequence": [
                "Prototype the narrowest viable transport path.",
                "Reuse existing instance assets first.",
                "Promote only after you can prove connectivity and data quality.",
            ],
            "risks": [
                "A generic integration pattern can hide transport assumptions.",
                "Skipping instance validation can lead to duplicated custom integration layers.",
            ],
        }

    evidence_labels = [
        area["label"]
        for area in signals
        if area.get("available") and int(area.get("count", 0)) > 0
    ]
    confidence = "medium"
    if architecture["name"] == "Import Sets + Transform Maps + Flow Designer" and import_sets > 0 and transform_maps > 0:
        confidence = "high"
    elif architecture["name"] in {"IntegrationHub + MID Server", "REST/SOAP API Integration with OAuth"} and (
        (integrationhub_plugins > 0 and mid_servers > 0) or (oauth_providers > 0 and (rest_messages > 0 or soap_messages > 0))
    ):
        confidence = "high"
    elif has_target_specific_assets:
        confidence = "high"

    return {
        "problem_statement": _normalized_phrase(problem_statement),
        "target_name": target_name,
        "signals": {
            "mid_servers": mid_servers,
            "integrationhub_plugins": integrationhub_plugins,
            "integration_actions": integration_actions,
            "rest_messages": rest_messages,
            "soap_messages": soap_messages,
            "oauth_providers": oauth_providers,
            "import_sets": import_sets,
            "transform_maps": transform_maps,
            "ecc_version_signal": ecc_version_signal,
            "intent_flags": flags,
        },
        "matched_assets": matched_assets,
        "decision_basis": evidence_labels,
        "confidence": confidence,
        "recommended_architecture": architecture,
        "alternatives": [
            "Import Sets + Transform Maps + Flow Designer",
            "IntegrationHub + MID Server",
            "REST/SOAP API Integration with OAuth",
        ],
    }


@mcp.tool()
def test_connection() -> dict[str, Any]:
    """Verify connectivity and authentication against the ServiceNow instance."""
    return _client().test_connection()


@mcp.tool()
def get_records(
    table: str,
    sysparm_query: str = "",
    fields: str = "",
    limit: int = 50,
    offset: int = 0,
    display_value: str = "all",
) -> dict[str, Any]:
    """Read records from a ServiceNow table using the Table API."""
    return _client().get_records(
        table,
        query=sysparm_query or None,
        fields=_fields_list(fields),
        limit=limit,
        offset=offset,
        display_value=display_value,
    )


@mcp.tool()
def get_record(
    table: str,
    sys_id: str,
    fields: str = "",
    display_value: str = "all",
) -> dict[str, Any]:
    """Read a single ServiceNow record by sys_id."""
    return _client().get_record(
        table,
        sys_id,
        fields=_fields_list(fields),
        display_value=display_value,
    )


@mcp.tool()
def analyze_solution_context(
    problem_statement: str,
    sample_limit: int = 5,
) -> dict[str, Any]:
    """Inspect the current ServiceNow instance for related artifacts before creating a new solution."""
    if sample_limit < 0:
        raise ValueError("sample_limit must be greater than or equal to 0.")

    terms = _analysis_terms(problem_statement)
    client = _client()
    area_configs = _analysis_area_configs()

    areas = [
        _collect_analysis_area(
            client=client,
            key=config["key"],
            label=config["label"],
            table=config["table"],
            query_fields=config["query_fields"],
            result_fields=config["result_fields"],
            title_fields=config["title_fields"],
            detail_fields=config["detail_fields"],
            terms=terms,
            sample_limit=sample_limit,
        )
        for config in area_configs
    ]

    return {
        "problem_statement": _normalized_phrase(problem_statement),
        "search_terms": terms,
        "summary": {area["key"]: area["count"] for area in areas},
        "areas": areas,
        "recommendations": _analysis_recommendations(problem_statement, areas),
        "next_step": _analysis_next_step(areas),
    }


@mcp.tool()
def recommend_solution_approach(
    problem_statement: str,
    needs_request_experience: bool = False,
    needs_workflow: bool = True,
    needs_server_logic: bool = True,
    needs_custom_data_model: bool = False,
    needs_external_integration: bool = False,
    prefer_existing_scope: bool = True,
    sample_limit: int = 3,
) -> dict[str, Any]:
    """Recommend whether to extend existing ServiceNow capabilities or design a new scoped solution."""
    analysis = analyze_solution_context(problem_statement=problem_statement, sample_limit=sample_limit)
    recommendation = _strategy_from_analysis(
        analysis,
        problem_statement=problem_statement,
        needs_request_experience=needs_request_experience,
        needs_workflow=needs_workflow,
        needs_server_logic=needs_server_logic,
        needs_custom_data_model=needs_custom_data_model,
        needs_external_integration=needs_external_integration,
        prefer_existing_scope=prefer_existing_scope,
    )
    recommendation["analysis_summary"] = analysis.get("summary", {})
    recommendation["analysis_next_step"] = analysis.get("next_step", "")
    return recommendation


@mcp.tool()
def score_solution_governance(
    problem_statement: str,
    proposed_scope: str,
    proposed_artifacts: str = "",
    business_purpose: str = "",
    reuse_plan: str = "",
    test_plan: str = "",
    security_model: str = "",
    integration_notes: str = "",
    update_set_name: str = "",
    uses_global_scope: bool = False,
    creates_new_tables: bool = False,
    uses_client_scripts: bool = False,
    uses_ui_policies: bool = False,
    sample_limit: int = 1,
) -> dict[str, Any]:
    """Score a proposed ServiceNow solution against repository governance and best-practice guidance."""
    analysis = analyze_solution_context(problem_statement=problem_statement, sample_limit=sample_limit)
    assessment = _governance_assessment(
        problem_statement=problem_statement,
        proposed_scope=proposed_scope,
        proposed_artifacts=proposed_artifacts,
        business_purpose=business_purpose,
        reuse_plan=reuse_plan,
        test_plan=test_plan,
        security_model=security_model,
        integration_notes=integration_notes,
        update_set_name=update_set_name,
        uses_global_scope=uses_global_scope,
        creates_new_tables=creates_new_tables,
        uses_client_scripts=uses_client_scripts,
        uses_ui_policies=uses_ui_policies,
    )

    summary = analysis.get("summary", {}) if isinstance(analysis.get("summary"), dict) else {}
    existing_matches = sum(int(value) for value in summary.values())
    if existing_matches > 0 and not _contains_any(reuse_plan, ["reuse", "extend", "existing"]):
        assessment["recommendations"] = [
            "Existing related artifacts were found in the instance. Add an explicit reuse or extension plan before implementation.",
            *assessment.get("recommendations", []),
        ]

    assessment["analysis_summary"] = summary
    assessment["analysis_next_step"] = analysis.get("next_step", "")
    return assessment


@mcp.tool()
def check_update_set_naming(update_set_name: str) -> dict[str, Any]:
    """Validate an update set name against the repository naming convention."""
    assessment = _update_set_naming_assessment(update_set_name)
    return {
        "update_set_name": assessment["name"],
        "passed": assessment["passed"],
        "parts": assessment["parts"],
        "detail": assessment["detail"],
        "standard": assessment["standard"],
        "example": "VRM - Vendor Risk Foundation - DEV",
    }


@mcp.tool()
def create_update_set(
    name: str,
    description: str,
) -> dict[str, Any]:
    """Create a ServiceNow update set only if the name matches the repository naming convention."""
    validated_name = _validated_update_set_name(name)
    payload = {
        "name": validated_name,
        "description": description,
    }
    result = _client().create_record("sys_update_set", payload)
    return {
        "naming_validation": _update_set_naming_assessment(validated_name),
        **result,
    }


@mcp.tool()
def advise_integration_architecture(
    problem_statement: str,
    sample_limit: int = 3,
) -> dict[str, Any]:
    """Recommend a ServiceNow integration architecture by inspecting instance signals."""
    signals = _integration_architecture_signals(problem_statement, sample_limit)
    recommendation = _recommend_integration_architecture(problem_statement, signals)
    return {
        **recommendation,
        "signals_detail": signals,
    }


@mcp.tool()
def create_script_include(
    name: str,
    script: str,
    api_name: str = "",
    description: str = "",
    client_callable: bool = False,
    active: bool = True,
) -> dict[str, Any]:
    """Create a Script Include record in ServiceNow."""
    payload = _clean_payload(
        {
            "name": name,
            "api_name": api_name,
            "description": description,
            "script": script,
            "client_callable": client_callable,
            "active": active,
        }
    )
    return _client().create_record("sys_script_include", payload)


@mcp.tool()
def create_business_rule(
    name: str,
    table: str,
    script: str,
    when: str = "before",
    filter_condition: str = "",
    order: int = 100,
    active: bool = True,
    advanced: bool = True,
    action_insert: bool = False,
    action_update: bool = True,
    action_delete: bool = False,
    action_query: bool = False,
) -> dict[str, Any]:
    """Create a Business Rule record in ServiceNow."""
    payload = _clean_payload(
        {
            "name": name,
            "collection": table,
            "script": script,
            "when": when,
            "filter_condition": filter_condition,
            "order": order,
            "active": active,
            "advanced": advanced,
            "action_insert": action_insert,
            "action_update": action_update,
            "action_delete": action_delete,
            "action_query": action_query,
        }
    )
    return _client().create_record("sys_script", payload)


@mcp.tool()
def create_client_script(
    name: str,
    table: str,
    script: str,
    script_type: str = "onLoad",
    field_name: str = "",
    ui_type: str = "0",
    active: bool = True,
) -> dict[str, Any]:
    """Create a standard Client Script record in ServiceNow."""
    payload = _clean_payload(
        {
            "name": name,
            "table": table,
            "script": script,
            "type": script_type,
            "field": field_name,
            "ui_type": ui_type,
            "active": active,
        }
    )
    return _client().create_record("sys_script_client", payload)


@mcp.tool()
def create_catalog_client_script(
    name: str,
    script: str,
    catalog_item_sys_id: str = "",
    variable_set_sys_id: str = "",
    script_type: str = "onLoad",
    applies_to: str = "item",
    ui_type: str = "0",
    active: bool = True,
) -> dict[str, Any]:
    """Create a Catalog Client Script record in ServiceNow."""
    payload = _clean_payload(
        {
            "name": name,
            "script": script,
            "type": script_type,
            "applies_to": applies_to,
            "cat_item": catalog_item_sys_id,
            "variable_set": variable_set_sys_id,
            "ui_type": ui_type,
            "active": active,
        }
    )
    return _client().create_record("catalog_script_client", payload)


@mcp.tool()
def create_catalog_item(
    name: str,
    short_description: str,
    description: str = "",
    category_sys_id: str = "",
    active: bool = True,
    visible_standalone: bool = True,
    billable: bool = False,
    delivery_time: int = 0,
    meta: str = "",
) -> dict[str, Any]:
    """Create a Service Catalog item in ServiceNow."""
    payload = _clean_payload(
        {
            "name": name,
            "short_description": short_description,
            "description": description,
            "category": category_sys_id,
            "active": active,
            "visible_standalone": visible_standalone,
            "billable": billable,
            "delivery_time": delivery_time,
            "meta": meta,
        }
    )
    return _client().create_record("sc_cat_item", payload)


@mcp.tool()
def create_catalog_variable(
    catalog_item_sys_id: str,
    name: str,
    question_text: str,
    variable_type: str = "1",
    order: int = 100,
    active: bool = True,
    mandatory: bool = False,
    default_value: str = "",
    help_text: str = "",
) -> dict[str, Any]:
    """Create a catalog variable for a Service Catalog item."""
    payload = _clean_payload(
        {
            "cat_item": catalog_item_sys_id,
            "name": name,
            "question_text": question_text,
            "type": variable_type,
            "order": order,
            "active": active,
            "mandatory": mandatory,
            "default_value": default_value,
            "help_text": help_text,
        }
    )
    return _client().create_record("item_option_new", payload)


@mcp.tool()
def create_catalog_ui_policy(
    catalog_item_sys_id: str,
    short_description: str,
    catalog_conditions: str = "",
    script_true: str = "",
    script_false: str = "",
    on_load: bool = True,
    reverse_if_false: bool = False,
    active: bool = True,
) -> dict[str, Any]:
    """Create a catalog UI policy for a Service Catalog item."""
    payload = _clean_payload(
        {
            "catalog_item": catalog_item_sys_id,
            "short_description": short_description,
            "catalog_conditions": catalog_conditions,
            "script_true": script_true,
            "script_false": script_false,
            "on_load": on_load,
            "reverse_if_false": reverse_if_false,
            "active": active,
        }
    )
    return _client().create_record("catalog_ui_policy", payload)


@mcp.tool()
def create_catalog_ui_policy_action(
    ui_policy_sys_id: str,
    catalog_variable_sys_id: str,
    visible: bool = True,
    mandatory: bool = False,
    disabled: bool = False,
    cleared: bool = False,
) -> dict[str, Any]:
    """Create a catalog UI policy action for a specific catalog variable."""
    payload = _clean_payload(
        {
            "ui_policy": ui_policy_sys_id,
            "catalog_variable": catalog_variable_sys_id,
            "visible": visible,
            "mandatory": mandatory,
            "disabled": disabled,
            "cleared": cleared,
        }
    )
    return _client().create_record("catalog_ui_policy_action", payload)


@mcp.tool()
def create_catalog_item_bundle(
    name: str,
    short_description: str,
    variables: list[dict[str, Any]] | None = None,
    ui_policies: list[dict[str, Any]] | None = None,
    client_scripts: list[dict[str, Any]] | None = None,
    description: str = "",
    category_sys_id: str = "",
    active: bool = True,
) -> dict[str, Any]:
    """Create a catalog item and optionally attach variables, UI policies, and catalog client scripts."""
    item = create_catalog_item(
        name=name,
        short_description=short_description,
        description=description,
        category_sys_id=category_sys_id,
        active=active,
    )
    item_record = item.get("result", {})
    item_sys_id = item_record.get("sys_id", {}).get("value") if isinstance(item_record.get("sys_id"), dict) else item_record.get("sys_id")

    variable_results: list[dict[str, Any]] = []
    variable_ids_by_name: dict[str, str] = {}
    for variable in variables or []:
        created_variable = create_catalog_variable(
            catalog_item_sys_id=item_sys_id,
            name=variable["name"],
            question_text=variable["question_text"],
            variable_type=str(variable.get("variable_type", variable.get("type", "1"))),
            order=int(variable.get("order", 100)),
            active=_normalize_bool(variable.get("active", True)),
            mandatory=_normalize_bool(variable.get("mandatory", False)),
            default_value=str(variable.get("default_value", "")),
            help_text=str(variable.get("help_text", "")),
        )
        variable_results.append(created_variable)
        variable_record = created_variable.get("result", {})
        variable_sys_id = variable_record.get("sys_id", {}).get("value") if isinstance(variable_record.get("sys_id"), dict) else variable_record.get("sys_id")
        variable_ids_by_name[variable["name"]] = variable_sys_id

    ui_policy_results: list[dict[str, Any]] = []
    ui_policy_action_results: list[dict[str, Any]] = []
    for policy in ui_policies or []:
        created_policy = create_catalog_ui_policy(
            catalog_item_sys_id=item_sys_id,
            short_description=policy["short_description"],
            catalog_conditions=str(policy.get("catalog_conditions", "")),
            script_true=str(policy.get("script_true", "")),
            script_false=str(policy.get("script_false", "")),
            on_load=_normalize_bool(policy.get("on_load", True)),
            reverse_if_false=_normalize_bool(policy.get("reverse_if_false", False)),
            active=_normalize_bool(policy.get("active", True)),
        )
        ui_policy_results.append(created_policy)
        policy_record = created_policy.get("result", {})
        policy_sys_id = policy_record.get("sys_id", {}).get("value") if isinstance(policy_record.get("sys_id"), dict) else policy_record.get("sys_id")

        for action in policy.get("actions", []):
            variable_sys_id = str(action.get("catalog_variable_sys_id") or variable_ids_by_name.get(str(action.get("variable_name", "")), ""))
            if not variable_sys_id:
                raise ValueError(
                    "Catalog UI policy actions require catalog_variable_sys_id or a variable_name that exists in variables."
                )
            created_action = create_catalog_ui_policy_action(
                ui_policy_sys_id=policy_sys_id,
                catalog_variable_sys_id=variable_sys_id,
                visible=_normalize_bool(action.get("visible", True)),
                mandatory=_normalize_bool(action.get("mandatory", False)),
                disabled=_normalize_bool(action.get("disabled", False)),
                cleared=_normalize_bool(action.get("cleared", False)),
            )
            ui_policy_action_results.append(created_action)

    client_script_results: list[dict[str, Any]] = []
    for client_script in client_scripts or []:
        created_client_script = create_catalog_client_script(
            name=client_script["name"],
            script=client_script["script"],
            catalog_item_sys_id=item_sys_id,
            variable_set_sys_id=str(client_script.get("variable_set_sys_id", "")),
            script_type=str(client_script.get("script_type", "onLoad")),
            applies_to=str(client_script.get("applies_to", "item")),
            ui_type=str(client_script.get("ui_type", "0")),
            active=_normalize_bool(client_script.get("active", True)),
        )
        client_script_results.append(created_client_script)

    return {
        "result": {
            "catalog_item": item,
            "variables": variable_results,
            "ui_policies": ui_policy_results,
            "ui_policy_actions": ui_policy_action_results,
            "catalog_client_scripts": client_script_results,
        }
    }


@mcp.tool()
def create_atf_test(
    name: str,
    description: str = "",
    active: bool = False,
) -> dict[str, Any]:
    """Create an Automated Test Framework test record in ServiceNow."""
    payload = _clean_payload(
        {
            "name": name,
            "description": description,
            "active": active,
        }
    )
    return _client().create_record("sys_atf_test", payload)


@mcp.tool()
def create_atf_test_step(
    test_sys_id: str,
    step_config_sys_id: str,
    order: int = 100,
    active: bool = False,
    description: str = "",
    input_values: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Create an ATF test step from an existing step configuration."""
    payload = _clean_payload(
        {
            "test": test_sys_id,
            "step_config": step_config_sys_id,
            "order": order,
            "active": active,
            "description": description,
        }
    )
    created_step = _client().create_record("sys_atf_step", payload)
    step_record = created_step.get("result", {})
    step_sys_id = _extract_value(step_record.get("sys_id"))

    created_inputs = []
    try:
        for input_value in input_values or []:
            created_input = create_atf_step_input_value(
                step_sys_id=step_sys_id,
                step_config_sys_id=step_config_sys_id,
                value=str(input_value["value"]),
                variable_sys_id=str(input_value.get("variable_sys_id", "")),
                reference_table=str(input_value.get("reference_table", "")),
                order=int(input_value.get("order", 100)),
            )
            created_inputs.append(created_input)
    except Exception:
        _client().delete_record("sys_atf_step", step_sys_id)
        raise

    if created_inputs:
        created_step["input_values"] = created_inputs

    return created_step


@mcp.tool()
def get_atf_step_config_inputs(step_config_sys_id: str) -> dict[str, Any]:
    """List available ATF input variables for a step configuration."""
    return _client().get_records(
        "atf_input_variable",
        query=f"model_id={step_config_sys_id}",
        fields=["sys_id", "name", "reference", "order"],
        limit=20,
    )


@mcp.tool()
def create_atf_step_input_value(
    step_sys_id: str,
    step_config_sys_id: str,
    value: str,
    variable_sys_id: str = "",
    reference_table: str = "",
    order: int = 100,
) -> dict[str, Any]:
    """Create an ATF step input value on sys_variable_value for a step."""
    resolved_variable_sys_id = _resolve_atf_input_variable_sys_id(
        step_config_sys_id,
        variable_sys_id=variable_sys_id,
        reference_table=reference_table,
    )
    payload = _clean_payload(
        {
            "document": "sys_atf_step",
            "document_key": step_sys_id,
            "variable": resolved_variable_sys_id,
            "value": value,
            "order": order,
        }
    )
    return _client().create_record("sys_variable_value", payload)


@mcp.tool()
def create_atf_test_bundle(
    name: str,
    description: str = "",
    active: bool = False,
    steps: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Create an ATF test and optionally attach ATF step skeletons."""
    test = create_atf_test(name=name, description=description, active=active)
    test_record = test.get("result", {})
    test_sys_id = test_record.get("sys_id", {}).get("value") if isinstance(test_record.get("sys_id"), dict) else test_record.get("sys_id")

    created_steps: list[dict[str, Any]] = []
    try:
        for index, step in enumerate(steps or [], start=1):
            created_step = create_atf_test_step(
                test_sys_id=test_sys_id,
                step_config_sys_id=step["step_config_sys_id"],
                order=int(step.get("order", index * 100)),
                active=_normalize_bool(step.get("active", active)),
                description=str(step.get("description", "")),
                input_values=step.get("input_values"),
            )
            created_steps.append(created_step)
    except Exception:
        for created_step in reversed(created_steps):
            step_record = created_step.get("result", {})
            step_sys_id = _extract_value(step_record.get("sys_id"))
            if step_sys_id:
                _client().delete_record("sys_atf_step", step_sys_id)
        _client().delete_record("sys_atf_test", test_sys_id)
        raise

    return {
        "result": {
            "test": test,
            "steps": created_steps,
        }
    }


@mcp.tool()
def update_record(table: str, sys_id: str, fields: dict[str, Any]) -> dict[str, Any]:
    """Update a ServiceNow record by table and sys_id using partial fields."""
    payload = _update_payload(fields)
    if not payload:
        raise ValueError("At least one field must be provided for update.")
    return _client().update_record(table, sys_id, payload)


@mcp.tool()
def update_atf_test(
    sys_id: str,
    name: str = "",
    description: str = "",
    active: bool | None = None,
) -> dict[str, Any]:
    """Update an ATF test record."""
    return update_record(
        "sys_atf_test",
        sys_id,
        {
            "name": name,
            "description": description,
            "active": active,
        },
    )


@mcp.tool()
def update_atf_test_step(
    sys_id: str,
    step_config_sys_id: str = "",
    order: int | None = None,
    active: bool | None = None,
    description: str = "",
) -> dict[str, Any]:
    """Update an ATF test step record."""
    return update_record(
        "sys_atf_step",
        sys_id,
        {
            "step_config": step_config_sys_id,
            "order": order,
            "active": active,
            "description": description,
        },
    )


@mcp.tool()
def update_catalog_item(
    sys_id: str,
    name: str = "",
    short_description: str = "",
    description: str = "",
    category_sys_id: str = "",
    active: bool | None = None,
    visible_standalone: bool | None = None,
    billable: bool | None = None,
    delivery_time: int | None = None,
    meta: str = "",
) -> dict[str, Any]:
    """Update a Service Catalog item."""
    return update_record(
        "sc_cat_item",
        sys_id,
        {
            "name": name,
            "short_description": short_description,
            "description": description,
            "category": category_sys_id,
            "active": active,
            "visible_standalone": visible_standalone,
            "billable": billable,
            "delivery_time": delivery_time,
            "meta": meta,
        },
    )


@mcp.tool()
def update_catalog_variable(
    sys_id: str,
    name: str = "",
    question_text: str = "",
    variable_type: str = "",
    order: int | None = None,
    active: bool | None = None,
    mandatory: bool | None = None,
    default_value: str = "",
    help_text: str = "",
) -> dict[str, Any]:
    """Update a catalog variable."""
    return update_record(
        "item_option_new",
        sys_id,
        {
            "name": name,
            "question_text": question_text,
            "type": variable_type,
            "order": order,
            "active": active,
            "mandatory": mandatory,
            "default_value": default_value,
            "help_text": help_text,
        },
    )


@mcp.tool()
def update_catalog_ui_policy(
    sys_id: str,
    short_description: str = "",
    catalog_conditions: str = "",
    script_true: str = "",
    script_false: str = "",
    on_load: bool | None = None,
    reverse_if_false: bool | None = None,
    active: bool | None = None,
) -> dict[str, Any]:
    """Update a catalog UI policy."""
    return update_record(
        "catalog_ui_policy",
        sys_id,
        {
            "short_description": short_description,
            "catalog_conditions": catalog_conditions,
            "script_true": script_true,
            "script_false": script_false,
            "on_load": on_load,
            "reverse_if_false": reverse_if_false,
            "active": active,
        },
    )


@mcp.tool()
def update_catalog_ui_policy_action(
    sys_id: str,
    visible: bool | None = None,
    mandatory: bool | None = None,
    disabled: bool | None = None,
    cleared: bool | None = None,
) -> dict[str, Any]:
    """Update a catalog UI policy action."""
    return update_record(
        "catalog_ui_policy_action",
        sys_id,
        {
            "visible": visible,
            "mandatory": mandatory,
            "disabled": disabled,
            "cleared": cleared,
        },
    )


@mcp.tool()
def update_catalog_client_script(
    sys_id: str,
    name: str = "",
    script: str = "",
    script_type: str = "",
    applies_to: str = "",
    ui_type: str = "",
    active: bool | None = None,
) -> dict[str, Any]:
    """Update a catalog client script."""
    return update_record(
        "catalog_script_client",
        sys_id,
        {
            "name": name,
            "script": script,
            "type": script_type,
            "applies_to": applies_to,
            "ui_type": ui_type,
            "active": active,
        },
    )


@mcp.tool()
def create_ui_page(
    name: str,
    html: str,
    client_script: str = "",
    processing_script: str = "",
        display_value: str = "all",
    direct: bool = False,
) -> dict[str, Any]:
    """Create a UI Page record in ServiceNow."""
    payload = _clean_payload(
        {
            "name": name,
            "html": html,
            "client_script": client_script,
            "processing_script": processing_script,
            "category": category,
            "direct": direct,
        }
    )
    return _client().create_record("sys_ui_page", payload)


@mcp.tool()
def create_ui_action(
    name: str,
    table: str,
    action_name: str,
    script: str,
    condition: str = "",
    client: bool = False,
    client_script: str = "",
    order: int = 100,
    active: bool = True,
    form_button: bool = True,
    form_context_menu: bool = False,
    form_link: bool = False,
    list_action: bool = False,
    list_banner_button: bool = False,
    list_choice: bool = False,
    list_context_menu: bool = False,
) -> dict[str, Any]:
    """Create a UI Action record in ServiceNow."""
    payload = _clean_payload(
        {
            "name": name,
            "table": table,
            "action_name": action_name,
            "script": script,
            "condition": condition,
            "client": client,
            "client_script": client_script,
            "order": order,
            "active": active,
            "form_button": form_button,
            "form_context_menu": form_context_menu,
            "form_link": form_link,
            "list_action": list_action,
            "list_banner_button": list_banner_button,
            "list_choice": list_choice,
            "list_context_menu": list_context_menu,
        }
    )
    return _client().create_record("sys_ui_action", payload)


@mcp.tool()
def delete_record(table: str, sys_id: str) -> dict[str, Any]:
    """Delete a ServiceNow record by table and sys_id."""
    return _client().delete_record(table, sys_id)


@mcp.tool()
def validate_permissions(
    probe_create: bool = False,
    catalog_item_sys_id: str = "",
    variable_set_sys_id: str = "",
) -> dict[str, Any]:
    """Validate read access and optional create/delete access for target ServiceNow tables."""
    client = _client()
    results: dict[str, Any] = {}

    tables = {
        "script_include": "sys_script_include",
        "business_rule": "sys_script",
        "client_script": "sys_script_client",
        "atf_test": "sys_atf_test",
        "atf_step": "sys_atf_step",
        "atf_step_config": "sys_atf_step_config",
        "catalog_client_script": "catalog_script_client",
        "catalog_item": "sc_cat_item",
        "catalog_variable": "item_option_new",
        "catalog_ui_policy": "catalog_ui_policy",
        "catalog_ui_policy_action": "catalog_ui_policy_action",
        "ui_page": "sys_ui_page",
        "ui_action": "sys_ui_action",
    }

    for label, table_name in tables.items():
        entry: dict[str, Any] = {"table": table_name}
        try:
            client.get_records(table_name, limit=1)
            entry["read_access"] = True
        except Exception as exc:  # pragma: no cover - passthrough for runtime API diagnostics
            entry["read_access"] = False
            entry["read_error"] = str(exc)
        results[label] = entry

    if not probe_create:
        return {"result": results}

    probes = [
        (
            "script_include",
            "sys_script_include",
            lambda suffix: {
                "name": f"MCP Validate Script Include {suffix}",
                "description": "Temporary permission probe created by MCP validation.",
                "script": (
                    "var MCPValidateScriptInclude = Class.create();\n"
                    "MCPValidateScriptInclude.prototype = {\n"
                    "    initialize: function() {},\n"
                    "    type: 'MCPValidateScriptInclude'\n"
                    "};"
                ),
                "active": False,
                "client_callable": False,
            },
        ),
        (
            "business_rule",
            "sys_script",
            lambda suffix: {
                "name": f"MCP Validate Business Rule {suffix}",
                "collection": "sys_user",
                "when": "before",
                "order": 100,
                "active": False,
                "advanced": True,
                "action_insert": False,
                "action_update": True,
                "action_delete": False,
                "action_query": False,
                "script": "(function executeRule(current, previous) {\n})(current, previous);",
            },
        ),
        (
            "client_script",
            "sys_script_client",
            lambda suffix: {
                "name": f"MCP Validate Client Script {suffix}",
                "table": "sys_user",
                "type": "onLoad",
                "ui_type": "0",
                "active": False,
                "script": "function onLoad() {\n}",
            },
        ),
        (
            "atf_test",
            "sys_atf_test",
            lambda suffix: {
                "name": f"MCP Validate ATF Test {suffix}",
                "description": "Temporary ATF test created by MCP validation.",
                "active": False,
            },
        ),
        (
            "ui_page",
            "sys_ui_page",
            lambda suffix: {
                "name": f"mcp_validate_ui_page_{suffix.lower()}",
                "html": "<g:ui_form><div>MCP validation page</div></g:ui_form>",
                "direct": False,
            },
        ),
        (
            "ui_action",
            "sys_ui_action",
            lambda suffix: {
                "name": f"MCP Validate UI Action {suffix}",
                "table": "sys_user",
                "action_name": f"mcp_validate_ui_action_{suffix.lower()}",
                "script": "gs.addInfoMessage('MCP validation action');",
                "active": False,
                "form_button": False,
                "form_context_menu": False,
                "form_link": True,
                "list_action": False,
                "list_banner_button": False,
                "list_choice": False,
                "list_context_menu": False,
            },
        ),
        (
            "catalog_item",
            "sc_cat_item",
            lambda suffix: {
                "name": f"MCP Validate Catalog Item {suffix}",
                "short_description": "Temporary catalog item created by MCP validation.",
                "description": "Temporary catalog item created by MCP validation.",
                "active": False,
                "visible_standalone": True,
            },
        ),
    ]

    if catalog_item_sys_id or variable_set_sys_id:
        probes.append(
            (
                "catalog_client_script",
                "catalog_script_client",
                lambda suffix: {
                    "name": f"MCP Validate Catalog Client Script {suffix}",
                    "type": "onLoad",
                    "applies_to": "item" if catalog_item_sys_id else "variable_set",
                    "cat_item": catalog_item_sys_id,
                    "variable_set": variable_set_sys_id,
                    "ui_type": "0",
                    "active": False,
                    "script": "function onLoad() {\n}",
                },
            )
        )
    else:
        results["catalog_client_script"]["create_access"] = "skipped"
        results["catalog_client_script"]["create_error"] = (
            "Provide catalog_item_sys_id or variable_set_sys_id to probe catalog client script creation."
        )

    if catalog_item_sys_id:
        probes.extend(
            [
                (
                    "catalog_variable",
                    "item_option_new",
                    lambda suffix: {
                        "cat_item": catalog_item_sys_id,
                        "name": f"mcp_validate_variable_{suffix.lower()}",
                        "question_text": f"MCP Validate Variable {suffix}",
                        "type": "1",
                        "order": 100,
                        "active": True,
                        "mandatory": False,
                    },
                ),
                (
                    "catalog_ui_policy",
                    "catalog_ui_policy",
                    lambda suffix: {
                        "catalog_item": catalog_item_sys_id,
                        "short_description": f"MCP Validate Catalog UI Policy {suffix}",
                        "on_load": True,
                        "reverse_if_false": False,
                        "active": False,
                    },
                ),
            ]
        )
    else:
        results["catalog_variable"]["create_access"] = "skipped"
        results["catalog_variable"]["create_error"] = "Provide catalog_item_sys_id to probe catalog variable creation."
        results["catalog_ui_policy"]["create_access"] = "skipped"
        results["catalog_ui_policy"]["create_error"] = "Provide catalog_item_sys_id to probe catalog UI policy creation."
        results["catalog_ui_policy_action"]["create_access"] = "skipped"
        results["catalog_ui_policy_action"]["create_error"] = (
            "Provide catalog_item_sys_id to probe catalog UI policy action creation."
        )

    results["atf_step"]["create_access"] = "skipped"
    results["atf_step"]["create_error"] = (
        "Provide a step_config_sys_id and create the ATF test first when probing ATF step creation."
    )

    for label, table_name, build_payload in probes:
        suffix = uuid.uuid4().hex[:8]
        try:
            created = client.create_record(table_name, build_payload(suffix))
            record = created.get("result", {})
            sys_id = record.get("sys_id", {}).get("value") if isinstance(record.get("sys_id"), dict) else record.get("sys_id")
            delete_result = client.delete_record(table_name, sys_id)
            results[label]["create_access"] = True
            results[label]["delete_access"] = bool(delete_result.get("ok"))
            results[label]["probe_sys_id"] = sys_id
        except Exception as exc:  # pragma: no cover - passthrough for runtime API diagnostics
            results[label]["create_access"] = False
            results[label]["create_error"] = str(exc)

    try:
        step_config_result = client.get_records(
            "sys_atf_step_config",
            fields=["sys_id", "name"],
            limit=1,
        )
        step_config_rows = step_config_result.get("result", [])
        if isinstance(step_config_rows, list) and step_config_rows:
            step_config = step_config_rows[0]
            step_config_sys_id = step_config.get("sys_id", {}).get("value") if isinstance(step_config.get("sys_id"), dict) else step_config.get("sys_id")
            test_probe = client.create_record(
                "sys_atf_test",
                {
                    "name": f"MCP Validate ATF Step Test {uuid.uuid4().hex[:8]}",
                    "description": "Temporary ATF step validation test.",
                    "active": False,
                },
            )
            test_record = test_probe.get("result", {})
            test_sys_id = test_record.get("sys_id", {}).get("value") if isinstance(test_record.get("sys_id"), dict) else test_record.get("sys_id")
            step_probe = client.create_record(
                "sys_atf_step",
                {
                    "test": test_sys_id,
                    "step_config": step_config_sys_id,
                    "order": 100,
                    "active": False,
                    "description": "Temporary ATF step validation record.",
                },
            )
            step_record = step_probe.get("result", {})
            step_sys_id = step_record.get("sys_id", {}).get("value") if isinstance(step_record.get("sys_id"), dict) else step_record.get("sys_id")
            client.delete_record("sys_atf_step", step_sys_id)
            client.delete_record("sys_atf_test", test_sys_id)
            results["atf_step"]["create_access"] = True
            results["atf_step"]["delete_access"] = True
            results["atf_step"]["probe_sys_id"] = step_sys_id
            results["atf_step"].pop("create_error", None)
        else:
            results["atf_step"]["create_access"] = False
            results["atf_step"]["create_error"] = "No ATF step configuration records were found."
    except Exception as exc:  # pragma: no cover - passthrough for runtime API diagnostics
        results["atf_step"]["create_access"] = False
        results["atf_step"]["create_error"] = str(exc)

    if catalog_item_sys_id:
        try:
            variable_probe = client.create_record(
                "item_option_new",
                {
                    "cat_item": catalog_item_sys_id,
                    "name": f"mcp_validate_policy_variable_{uuid.uuid4().hex[:8].lower()}",
                    "question_text": "MCP Validate Policy Variable",
                    "type": "1",
                    "order": 100,
                    "active": True,
                },
            )
            variable_record = variable_probe.get("result", {})
            variable_sys_id = variable_record.get("sys_id", {}).get("value") if isinstance(variable_record.get("sys_id"), dict) else variable_record.get("sys_id")

            policy_probe = client.create_record(
                "catalog_ui_policy",
                {
                    "catalog_item": catalog_item_sys_id,
                    "short_description": f"MCP Validate Policy Action {uuid.uuid4().hex[:8]}",
                    "on_load": True,
                    "active": False,
                },
            )
            policy_record = policy_probe.get("result", {})
            policy_sys_id = policy_record.get("sys_id", {}).get("value") if isinstance(policy_record.get("sys_id"), dict) else policy_record.get("sys_id")

            action_probe = client.create_record(
                "catalog_ui_policy_action",
                {
                    "ui_policy": policy_sys_id,
                    "catalog_variable": variable_sys_id,
                    "visible": True,
                    "mandatory": False,
                    "disabled": False,
                    "cleared": False,
                },
            )
            action_record = action_probe.get("result", {})
            action_sys_id = action_record.get("sys_id", {}).get("value") if isinstance(action_record.get("sys_id"), dict) else action_record.get("sys_id")

            client.delete_record("catalog_ui_policy_action", action_sys_id)
            client.delete_record("catalog_ui_policy", policy_sys_id)
            client.delete_record("item_option_new", variable_sys_id)
            results["catalog_ui_policy_action"]["create_access"] = True
            results["catalog_ui_policy_action"]["delete_access"] = True
            results["catalog_ui_policy_action"]["probe_sys_id"] = action_sys_id
        except Exception as exc:  # pragma: no cover - passthrough for runtime API diagnostics
            results["catalog_ui_policy_action"]["create_access"] = False
            results["catalog_ui_policy_action"]["create_error"] = str(exc)

    return {"result": results}


if __name__ == "__main__":
    mcp.run(transport="stdio")