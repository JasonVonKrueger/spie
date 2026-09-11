<p align="center">
  <img src="docs/logo.png" alt="SPIE" style="width: 400px; height: auto;"/>
</p>

# ServiceNow MCP Server

Node.js stdio MCP server for querying a ServiceNow instance with OAuth 2.0 authentication.

## Requirements

- Node.js 18+
- A ServiceNow OAuth application with:
  - Client ID
  - Client secret
  - A supported grant type (`client_credentials`, `password`, `authorization_code`, or `refresh_token`)

## Setup

1. Install dependencies:

   ```bash
   npm install
   ```

2. Copy the example environment file and fill in your ServiceNow values:

   ```bash
   cp .env.example .env
   ```

3. Register or configure a ServiceNow OAuth application.

### ServiceNow app registration steps

1. In ServiceNow, open **System OAuth > Application Registry**.
2. Create an OAuth client application for external access.
3. Copy the generated client ID and client secret into `.env`.
4. Enable the grant type you want the server to use.
5. If you use `authorization_code`, configure the same redirect URI in ServiceNow and in `SERVICENOW_REDIRECT_URI`.
6. Make sure the OAuth user or integration principal has access to the tables you plan to query.

## ServiceNow OAuth configuration

At minimum, configure:

- `SERVICENOW_INSTANCE_URL`
- `SERVICENOW_CLIENT_ID`
- `SERVICENOW_CLIENT_SECRET`
- `SERVICENOW_OAUTH_GRANT_TYPE`

Grant-specific variables:

- `client_credentials`: no additional variables
- `password`: `SERVICENOW_USERNAME`, `SERVICENOW_PASSWORD`
- `authorization_code`: `SERVICENOW_AUTHORIZATION_CODE`, `SERVICENOW_REDIRECT_URI`
- `refresh_token`: `SERVICENOW_REFRESH_TOKEN`

For `authorization_code`, the code is exchanged on the first authenticated call. If the access token later expires, the server uses the refresh token returned by ServiceNow for transparent renewal.

## Running the server

```bash
npm start
```

The server starts on stdio and exposes two example tools:

- `query_table_records`
- `get_record_by_sys_id`
- `create_record`
- `update_record`

The `create_record` and `update_record` tools only modify records in tables listed in `src/tools/allowed-crud-tables.js`. If a caller requests any other table, the tool returns an error with the current allowed table list.

When creating or updating a Script Include (`sys_script_include`) that defines a function, the tool first searches existing Script Includes for whole function names that are exact or very similar matches. If it finds possible duplicates, it returns an MCP error with a markdown table listing the existing Script Include, API name, possible duplicate function, and direct ServiceNow link. ServiceNow is not modified when possible duplicates are found.

## Connecting with Claude Desktop

Claude Desktop can launch stdio MCP servers from its local configuration file. On macOS, open or create:

```text
~/Library/Application Support/Claude/claude_desktop_config.json
```

Add this server under `mcpServers`, replacing `/Users/rogerpoore/Dev/xyzzy` with the absolute path to this project if it is different:

```json
{
   "mcpServers": {
      "servicenow": {
         "command": "sh",
         "args": [
            "-c",
            "cd /Users/rogerpoore/Dev/xyzzy && npm start"
         ]
      }
   }
}
```

The `cd` is important because the server loads `.env` from the current working directory. After saving the file, fully quit and reopen Claude Desktop. The ServiceNow tools should then appear in Claude's MCP tools list.

## Runtime behavior

- The server does **not** fail at process startup if `.env` is missing.
- On the **first tool call**, it checks whether `.env` exists and validates all required variables for the configured grant type.
- If configuration is valid, it performs a lightweight authenticated ServiceNow request to confirm connectivity.
- Successful validation is cached for the life of the process.
- If a later request fails with an authentication error, the server clears its cached auth state, revalidates, and retries once.

## Testing

```bash
npm test
```
