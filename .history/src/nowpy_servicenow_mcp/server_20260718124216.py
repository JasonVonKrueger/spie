from __future__ import annotations

import uuid
from typing import Any

from mcp.server.fastmcp import FastMCP

from nowpy_servicenow_mcp.client import ServiceNowClient


mcp = FastMCP("ServiceNow MCP", json_response=True)


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
        "catalog_client_script": "catalog_script_client",
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

    return {"result": results}


if __name__ == "__main__":
    mcp.run(transport="stdio")