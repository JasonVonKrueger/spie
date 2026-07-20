# CLI Examples

This project does not currently expose a separate interactive command-line interface. For direct terminal usage, call the underlying Python functions with `uv run python`.

## Connection and Reads

### Test the ServiceNow connection

```bash
uv run python - <<'PY'
from spie_mcp.server import test_connection

print(test_connection())
PY
```

### Read records from a table

```bash
uv run python - <<'PY'
from spie_mcp.server import get_records

result = get_records(
	table="sys_user",
	fields="sys_id,user_name,email",
	limit=2,
)
print(result)
PY
```

## Analysis and Governance

### Analyze existing solution context before building something new

```bash
uv run python - <<'PY'
from spie_mcp.server import analyze_solution_context

result = analyze_solution_context(
	problem_statement="Vendor Risk application",
	sample_limit=3,
)
print(result)
PY
```

### Recommend an architecture approach from live instance context

```bash
uv run python - <<'PY'
from spie_mcp.server import recommend_solution_approach

result = recommend_solution_approach(
	problem_statement="Vendor Risk application",
	needs_request_experience=True,
	needs_workflow=True,
	needs_server_logic=True,
	needs_custom_data_model=True,
	sample_limit=2,
)
print(result)
PY
```

### Score a proposed solution against governance standards

```bash
uv run python - <<'PY'
from spie_mcp.server import score_solution_governance

result = score_solution_governance(
	problem_statement="Vendor Risk application",
	proposed_scope="x_acme_vendor_risk",
	proposed_artifacts="script_include:ACMEVendorRiskService;business_rule:Vendor - Before Update - Normalize Risk;catalog_item:Risk - Vendor Review",
	business_purpose="Manage vendor risk onboarding, review, and approval workflows.",
	reuse_plan="Extend the existing vendor data model and reuse shared Script Includes and flows where they already fit.",
	test_plan="Add ATF coverage for intake, approval routing, and lifecycle validation.",
	security_model="Use ACLs, scoped roles, and least privilege integration credentials.",
	integration_notes="Validate inbound payloads and use timeout, retry, version, and correlation ID patterns.",
	update_set_name="VRM - Vendor Risk Foundation - DEV",
	creates_new_tables=True,
	uses_client_scripts=True,
	uses_ui_policies=True,
)
print(result)
PY
```

### Validate an update set name

```bash
uv run python - <<'PY'
from spie_mcp.server import check_update_set_naming

result = check_update_set_naming("VRM - Vendor Risk Foundation - DEV")
print(result)
PY
```

### Create a valid update set

This is the supported path for new update sets. Direct raw creation of `sys_update_set` records is intentionally blocked in the client layer.

```bash
uv run python - <<'PY'
from spie_mcp.server import create_update_set

result = create_update_set(
	name="VRM - Vendor Risk Foundation - DEV",
	description="Initial vendor risk foundation changes.",
)
print(result)
PY
```

### Reject an invalid update set name

```bash
uv run python - <<'PY'
from spie_mcp.server import create_update_set

try:
	create_update_set(
		name="bob update",
		description="This should fail naming validation.",
	)
except ValueError as exc:
	print(exc)
PY
```

### Rename or update an existing update set

This is the supported path for update set renames. Direct raw updates to `sys_update_set.name` are intentionally blocked in the client layer.

```bash
uv run python - <<'PY'
from spie_mcp.server import update_update_set

result = update_update_set(
	sys_id="YOUR_UPDATE_SET_SYS_ID",
	name="VRM - Vendor Risk Foundation - DEV",
	description="Renamed to match the repository naming standard.",
)
print(result)
PY
```

### Advise an integration architecture for any target system and ServiceNow

```bash
uv run python - <<'PY'
from spie_mcp.server import advise_integration_architecture

result = advise_integration_architecture(
	problem_statement="I need to integrate Workday with ServiceNow in real time.",
	sample_limit=2,
)

print("Target:", result["target_name"])
print("Confidence:", result["confidence"])
print("Decision basis:", result["decision_basis"])
print("Matched assets:", result["matched_assets"])
print("Recommended architecture:", result["recommended_architecture"]["name"])
print(result)
PY
```

### Scan Script Includes for redundant behavior

```bash
uv run python - <<'PY'
from spie_mcp.server import scan_script_include_redundancy

result = scan_script_include_redundancy()
print(result)
PY
```

## Artifact Creation and Updates

### Create a valid Script Include

```bash
uv run python - <<'PY'
from spie_mcp.server import create_script_include

result = create_script_include(
	name="ACMEVendorRiskService",
	script="var ACMEVendorRiskService = Class.create();\nACMEVendorRiskService.prototype = {\n\ttype: 'ACMEVendorRiskService'\n};",
	description="Vendor risk service layer.",
)
print(result)
PY
```

### Reject an invalid Business Rule name

```bash
uv run python - <<'PY'
from spie_mcp.server import create_business_rule

try:
	create_business_rule(
		name="bad rule name",
		table="incident",
		script="(function executeRule(current, previous) {\n})(current, previous);",
	)
except ValueError as exc:
	print(exc)
PY
```

### Update a Client Script with naming validation

```bash
uv run python - <<'PY'
from spie_mcp.server import update_client_script

result = update_client_script(
	sys_id="YOUR_CLIENT_SCRIPT_SYS_ID",
	name="Incident - On Load - Hide Internal Fields",
	active=True,
)
print(result)
PY
```

### Create a catalog item bundle with a variable, UI policy, and catalog client script

```bash
uv run python - <<'PY'
from spie_mcp.server import create_catalog_item_bundle

result = create_catalog_item_bundle(
	name="Example Catalog Item",
	short_description="Example item created from the CLI.",
	description="This item was created with the MCP server's Python entrypoints.",
	active=False,
	variables=[
		{
			"name": "requested_for",
			"question_text": "Requested for",
			"variable_type": "31",
			"order": 100,
			"mandatory": True,
		}
	],
	ui_policies=[
		{
			"short_description": "Show requested_for on load",
			"on_load": True,
			"active": False,
			"actions": [
				{
					"variable_name": "requested_for",
					"visible": True,
					"mandatory": True,
				}
			],
		}
	],
	client_scripts=[
		{
			"name": "Example Catalog Client Script",
			"script_type": "onLoad",
			"active": False,
			"script": "function onLoad() {\\n}"
		}
	],
)
print(result)
PY
```

### Create an ATF test with a step skeleton

```bash
uv run python - <<'PY'
from spie_mcp.server import create_atf_test_bundle

result = create_atf_test_bundle(
	name="Example ATF Test",
	description="ATF example created from the CLI.",
	active=False,
	steps=[
		{
			"step_config_sys_id": "YOUR_STEP_CONFIG_SYS_ID",
			"order": 100,
			"description": "Example step",
		}
	],
)
print(result)
PY
```

### Update an existing catalog item

```bash
uv run python - <<'PY'
from spie_mcp.server import update_catalog_item

result = update_catalog_item(
	sys_id="YOUR_CATALOG_ITEM_SYS_ID",
	short_description="Updated from the CLI example.",
	active=True,
)
print(result)
PY
```

### Delete a record

```bash
uv run python - <<'PY'
from spie_mcp.server import delete_record

result = delete_record(
	table="sys_script_include",
	sys_id="YOUR_RECORD_SYS_ID",
	confirm=True,
)
print(result)
PY
```