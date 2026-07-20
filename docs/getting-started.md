# Getting Started

## Requirements

- Python 3.10+
- `uv` installed locally
- A ServiceNow instance with credentials or a bearer token that can read and create records in the target tables

## Configuration

The server auto-loads a local `.env` file if present. You can also provide these values through your shell or VS Code environment.

Set these environment variables before running the server:

- `SERVICENOW_INSTANCE_URL` - Base instance URL such as `https://example.service-now.com`
- `SERVICENOW_USERNAME` - Username for basic authentication
- `SERVICENOW_PASSWORD` - Password for basic authentication
- `SERVICENOW_BEARER_TOKEN` - Optional bearer token. If set, it is used instead of username/password
- `SERVICENOW_OAUTH_CLIENT_ID` - Optional OAuth client ID for client-credentials authentication
- `SERVICENOW_OAUTH_CLIENT_SECRET` - Optional OAuth client secret for client-credentials authentication
- `SERVICENOW_OAUTH_GRANT_TYPE` - Optional OAuth grant type. Defaults to `client_credentials`
- `SERVICENOW_OAUTH_TOKEN_URL` - Optional token endpoint. Defaults to `<instance_url>/oauth_token.do`
- `SERVICENOW_OAUTH_SCOPE` - Optional OAuth scope value if your registry requires it
- `SERVICENOW_TIMEOUT` - Optional HTTP timeout in seconds. Defaults to `30`

Supported authentication modes:

- bearer token
- OAuth client credentials
- username and password

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

The workspace already includes [.vscode/mcp.json](../.vscode/mcp.json), so VS Code can launch the server as a local MCP process with:

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

## Inspect Locally

```bash
uv run mcp dev src/spie_mcp/server.py
```