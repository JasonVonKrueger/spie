# ServiceNow Platform Intelligence Engine (SPIE)

<p align="center">
  <img src="docs/logo/logo.png" alt="SPIE" style="width: 400px; height: auto;"/>
</p>

This project provides a Python-based MCP server for ServiceNow.

It supports:

- Analyzing existing ServiceNow solution context before generating new artifacts
- Recommending whether to extend existing platform assets or create a new scoped solution
- Scoring proposed solutions against local governance and ServiceNow best-practice guidance
- Checking update set names against the documented naming convention
- Creating update sets through a strict naming-convention gate
- Updating update sets through the same naming-convention gate for renames
- Enforcing naming-convention guardrails for Script Includes, Business Rules, and Client Scripts on create and update
- Advising integration architecture by inspecting instance signals for any target system
- Scanning Script Includes for redundant behavior and duplicate helpers
- Reading data from any ServiceNow table through the Table API
- Enforcing read/create/update-only ServiceNow automation patterns (no delete operations)
- Creating ATF tests, ATF test step skeletons, and ATF step input values
- Creating catalog items
- Creating catalog variables
- Creating catalog UI policies and UI policy actions
- Creating script includes
- Creating business rules
- Creating client scripts
- Creating catalog client scripts
- Creating UI pages
- Creating UI actions

## Documentation

- [Getting Started](docs/getting-started.md) for setup, configuration, and launch steps.
- [CLI Examples](docs/cli-examples.md) for end-to-end usage snippets.
- [Tool Reference](docs/tool-reference.md) for the exposed MCP tools.
- [Authentication](docs/authentication.md) for auth modes and OAuth setup.
- [ServiceNow Best Practices](docs/servicenow-best-practices.md) for the governance guidance used by the analyzer.
- [OAuth Flow](docs/oauth_flow.md) for the MCP-to-ServiceNow client-credentials flow.

## Workspace Customizations

This repository includes Copilot instruction and prompt files under `.github/` that shape how artifact automation is implemented:

- `.github/instructions/servicenow-no-delete.instructions.md`
- `.github/instructions/servicenow-naming-governance.instructions.md`
- `.github/instructions/servicenow-atf-conventions.instructions.md`
- `.github/prompts/create-servicenow-artifact-bundle.prompt.md`

Current expected behavior:

- No ServiceNow delete operations are exposed or implemented by MCP tools.
- Partial ATF create failures return manual cleanup guidance instead of destructive rollback.
- ServiceNow artifact creation should follow naming and governance conventions.
- The artifact-bundle prompt standardizes Script Include, Ajax wrapper, UI Page, UI Action, and optional ATF scaffolding workflows.

## Install

```bash
uv sync
```

## Run

```bash
uv run python -m spie_mcp
```

This starts the MCP server over `stdio`. It is meant to be launched by an MCP host such as VS Code, Claude Desktop, or the MCP Inspector.

## Use From VS Code

The workspace already includes [.vscode/mcp.json](.vscode/mcp.json), so VS Code can launch the server as a local MCP process with:

```json
{
  "servers": {
    "spie": {
      "type": "stdio",
      "command": "uv",
      "args": ["run", "python", "-m", "spie_mcp"]
    }
  }
}
```

## Quick Start

This project does not currently expose a separate interactive command-line interface. For direct terminal usage, call the underlying Python functions with `uv run python`.

See [docs/cli-examples.md](docs/cli-examples.md) for the full set of runnable examples.

## Inspect Locally

```bash
uv run mcp dev src/spie_mcp/server.py
```

## Exposed MCP Tools

- `test_connection`
- `get_records`
- `get_record`
- `validate_permissions`
- `create_atf_test`
- `create_atf_test_step`
- `get_atf_step_config_inputs`
- `create_atf_step_input_value`
- `create_atf_test_bundle`
- `update_record`
- `update_atf_test`
- `update_atf_test_step`

For the full tool surface and payload shapes, see [docs/tool-reference.md](docs/tool-reference.md).

## Notes

- The server uses the ServiceNow Table API for reads and record creation.
- ATF step input values are stored through `sys_variable_value` records linked to `sys_atf_step`.
- Creating ATF step input values requires insert access to `sys_variable_value`.
- If an ATF bundle or step-input flow fails after creating parent artifacts, the server returns manual-cleanup details instead of issuing delete calls.
- Some ServiceNow instances may enforce additional required fields, scoped app constraints, or ACLs. If that happens, the API error details are returned by the tool.

## Configure API Key

### Create an Inbound Authentication Profile 
- Navigate to All > System Web Services > API Access Policies > Inbound Authentication Profile.
- Click New.
- Click Create API Key authentication profiles.
- Enter a Name.
- In the Auth Parameter field, choose how the third party will send the key: select Auth Header or Query Parameter for x-sn-apikey.
- Click Submit. 

### Generate the REST API Key 
- Navigate to System Web Services > API Access Policies > REST API Key.
- Click New.
- Provide a descriptive name and select the User account (e.g., a dedicated integration service account) whose roles and ACL permissions this key will inherit.
- Click Submit.
- Reopen the created record and click the Lock Icon next to the Token field.
- Copy the secret token immediately; you will not be able to view it again after navigating away. 


### Define the REST API Access Policy 
- Navigate to System Web Services > API Access Policies > REST API Access Policies.
- Click New.
- Select the targeted API (such as the Table API) you want to protect.
- Link it to the Inbound Authentication Profile you created in step 1.
- Save the record to enforce the policy. 
