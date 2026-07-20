from __future__ import annotations

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


if __name__ == "__main__":
    mcp.run(transport="stdio")