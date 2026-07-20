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
    area: dict[str, Any] = {"label": label, "table": table, "count": count, "query": query}

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
        area: dict[str, Any] = {"key": key, "label": label, "table": table, "count": count, "query": query}
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
    area_configs = [
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
    ]

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
    category: str = "",
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