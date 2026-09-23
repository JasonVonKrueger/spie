# ServiceNow Platform Intelligence Engine

<p align="center">
  <img src="docs/logo.png" alt="SPIE" style="width: 400px; height: auto;"/>
</p>

Node.js stdio MCP server for querying a ServiceNow instance with OAuth 2.0 authentication.

## Requirements

- Node.js 18+
- A ServiceNow OAuth application with:
  - Client ID
  - Client secret
  - A supported grant type (`client_credentials`, `password`, `authorization_code`, `refresh_token`, or `interactive`)

## Setup

1. Install dependencies:

   ```bash
   npm install
   ```

2. Copy the example environment file to `.env`, then edit `.env` and set the values for your instance (`.env.example` explains each variable):

   ```bash
   cp .env.example .env
   ```

3. Register or configure a ServiceNow OAuth application. For interactive browser sign-in (recommended), follow [Creating the OAuth integration](#creating-the-oauth-integration-for-interactive-sign-in) below.

### ServiceNow app registration steps (other grant types)

These steps apply to the `client_credentials`, `password`, `authorization_code`, and `refresh_token` grants.

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
- `interactive`: no additional variables (see below)

For `authorization_code`, the code is exchanged on the first authenticated call. If the access token later expires, the server uses the refresh token returned by ServiceNow for transparent renewal.

### Interactive browser sign-in

Set `SERVICENOW_OAUTH_GRANT_TYPE=interactive` to sign in as yourself instead of storing a shared credential in `.env`. Only `SERVICENOW_INSTANCE_URL` and `SERVICENOW_CLIENT_ID` are required (`SERVICENOW_CLIENT_SECRET` is optional and not needed for a public client).

#### Creating the OAuth integration for interactive sign-in

Create the integration once per instance. This needs an admin. Menu names and field labels vary slightly between ServiceNow releases.

1. In ServiceNow, open the **Inbound integrations** tab (the page with the tabs Overview, Inbound integrations, Security findings, Metrics, and Settings) and click **New integration**.
2. On **Select your application connection type**, choose **OAuth - Authorization code grant**.
3. Give the integration a name, for example `SPIE`.
4. Set the **Redirect URL** to exactly:

   ```text
   http://127.0.0.1:8765/callback
   ```

   SPIE listens on this local address to receive the sign-in response, and ServiceNow requires an exact match. To use a different port, register the new URL here and set `SERVICENOW_REDIRECT_URI` in `.env` to the same value. It must be an `http` loopback URL (`127.0.0.1`, `localhost`, or `[::1]`) with an explicit port.
5. Check **This is a public client**, so no client secret is needed. Leave **Active** checked.
6. Under **Auth scope**, select **Table API** and limit authorization to the **Table API**. Check **Allow access only to APIs in selected scope**.

   > **The Table API auth scope is required.** SPIE only calls the Table API (`/api/now/table/...`). Without it, sign-in succeeds but every tool call fails with `403 User Not Authorized`. It also keeps the token limited to what SPIE needs, instead of the broad `useraccount` scope.
7. Save the integration and copy its **Client ID** into `.env`:

   ```text
   SERVICENOW_INSTANCE_URL=https://your-instance.service-now.com
   SERVICENOW_CLIENT_ID=<client id from the integration>
   SERVICENOW_OAUTH_GRANT_TYPE=interactive
   ```

#### Signing in

1. On the first tool call SPIE opens your browser to the ServiceNow login page. If it does not open, the tool reply includes the URL. Sign in, then run the request again if the tool call had already returned.
2. Tokens are held in memory only and refreshed silently; they are not written to disk. Restarting the server means signing in again.

The token belongs to whichever ServiceNow account is signed in in your default browser, and ServiceNow applies that account's roles. For example, reading `syslog` requires a user that can read it (typically `admin`, or a custom role with a read ACL on `syslog`). To check who a token was issued to, look at **System OAuth > Manage Tokens**.

If your user lacks read access to `sys_user`, SPIE's connection check treats that 403 as connected and leaves authorization to each tool call.

#### Troubleshooting

- **`403 User Not Authorized` on every call after signing in:** the integration's Auth scope does not include the Table API, or the signed-in user lacks access to the table.
- **Port already in use:** another process is using port 8765. Close it, or choose another loopback port as described above.
- **`invalid redirect_uri` from ServiceNow:** the Redirect URL in the integration does not exactly match `SERVICENOW_REDIRECT_URI` (default `http://127.0.0.1:8765/callback`).

## Running the server

```bash
npm start
```

The server starts on stdio and exposes these tools. See [docs/tools/](docs/tools/) for the full documentation of each one.

- [`query_table_records`](docs/tools/query-table-records.md): query records from a table
- [`get_record_by_sys_id`](docs/tools/get-record-by-sys-id.md): fetch one record by `sys_id`
- [`create_record`](docs/tools/create-record.md): create a record in an allowed table
- [`update_record`](docs/tools/update-record.md): update a record in an allowed table
- [`analyze_syslog`](docs/tools/analyze-syslog.md): read-only analysis of `syslog` for potential platform problems

`create_record` and `update_record` only modify tables in `src/tools/allowed-crud-tables.js`; the read tools are not restricted.

## Connecting with Claude Desktop

Claude Desktop can launch stdio MCP servers from its local configuration file. On macOS, open or create:

```text
~/Library/Application Support/Claude/claude_desktop_config.json
```

Add this server under `mcpServers`, replacing `/Users/rogerpoore/Dev/spie` with the absolute path to this project if it is different:

```json
{
   "mcpServers": {
      "servicenow": {
         "command": "sh",
         "args": [
            "-c",
            "cd /Users/rogerpoore/Dev/spie && npm start"
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
