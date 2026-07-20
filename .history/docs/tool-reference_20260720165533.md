# Tool Reference

## Exposed MCP Tools

- `test_connection`
- `get_records`
- `get_record`
- `delete_record`
- `validate_permissions`
- `create_atf_test`
- `create_atf_test_step`
- `get_atf_step_config_inputs`
- `create_atf_step_input_value`
- `create_atf_test_bundle`
- `update_record`
- `update_atf_test`
- `update_atf_test_step`
- `create_catalog_item`
- `create_catalog_variable`
- `create_catalog_ui_policy`
- `create_catalog_ui_policy_action`
- `create_catalog_item_bundle`
- `update_catalog_item`
- `update_catalog_variable`
- `update_catalog_ui_policy`
- `update_catalog_ui_policy_action`
- `update_catalog_client_script`
- `create_script_include`
- `create_business_rule`
- `create_client_script`
- `create_catalog_client_script`
- `create_ui_page`
- `create_ui_action`

## Notes

- The server uses the ServiceNow Table API for reads and record creation.
- ATF step input values are stored through `sys_variable_value` records linked to `sys_atf_step`.
- Creating ATF step input values requires insert access to `sys_variable_value`. On the current instance, direct inserts to that table are blocked by ACLs, so the server rolls back the parent ATF step and test if input creation fails.

## More Examples

### `create_atf_test_bundle` payload shape

```python
create_atf_test_bundle(
	name="Validate Catalog Item Flow",
	description="ATF created through MCP",
	active=False,
	steps=[
		{
			"step_config_sys_id": "071ee5b253331200040729cac2dc348d",
			"order": 100,
			"description": "Impersonate a user",
			"input_values": [
				{
					"reference_table": "sys_user",
					"value": "08e4bcf053231300e321ddeeff7b12f8",
				},
			]
		}
	],
)
```

Use `get_atf_step_config_inputs(step_config_sys_id=...)` first when a step config has multiple input variables and you need the exact `variable_sys_id` values.

### Example update calls

```python
update_atf_test(
	sys_id="your_atf_test_sys_id",
	description="Revised ATF description",
	active=True,
)

update_catalog_item(
	sys_id="your_catalog_item_sys_id",
	short_description="Updated catalog item description",
	active=True,
)
```