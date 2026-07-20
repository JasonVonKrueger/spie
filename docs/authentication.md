# Authentication

The server supports three authentication modes, in order of preference when values are present:

- bearer token
- OAuth client credentials
- username and password

## Environment Variables

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

## OAuth Flow

For the client-credentials path, the server requests an access token from ServiceNow and then uses that token for subsequent API calls. A separate fix script is available at [fix_scripts/spie_oauth.js](../fix_scripts/spie_oauth.js) to create or update the matching OAuth application registry.

See [docs/oauth_flow.md](oauth_flow.md) for a simple visual of the request flow.