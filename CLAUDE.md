# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

SPIE (ServiceNow Platform Intelligence Engine) is a Node.js (>=18, ESM, plain JavaScript) stdio MCP server that exposes a ServiceNow instance's Table API to MCP clients (e.g. Claude Desktop) using OAuth 2.0. Dependencies: `@modelcontextprotocol/sdk`, `zod`, `dotenv`.

## Commands

- `npm install` — install dependencies
- `npm start` — run the server on stdio (`node src/index.js`); it is meant to be launched by an MCP client, not used interactively
- `npm test` — run all tests (`node --test`, built-in Node test runner)
- Single file: `node --test test/tools.test.js`
- Single test by name: `node --test --test-name-pattern="rejects tables outside" test/tools.test.js`

There is no linter or build step. `.env.example` is the template for `.env`; `.env` is gitignored and holds real credentials. Keep `.env.example` in sync when adding config variables.

## Architecture

Request flow: `src/index.js` (stdio transport) → `src/server.js` (`McpServer`) → `src/tools/index.js` (registers tools) → `runtime.execute()` → `ServiceNowClient` → `ServiceNowOAuthClient`.

- **Lazy config/validation ([src/runtime.js](src/runtime.js))**: the server deliberately does *not* read `.env` or contact ServiceNow at startup. On the first tool call, `runtime.validate()` loads config, builds the auth + API clients, and does a `testConnection()` (GET `sys_user` limit 1); the result is cached for the process lifetime and concurrent first calls share one in-flight promise. `execute(operation)` catches `AuthError` (raised on HTTP 401), invalidates cached tokens, revalidates, and retries the operation exactly once.
- **Config ([src/config.js](src/config.js))**: reads `.env` from `process.cwd()` (not the project dir — the Claude Desktop config does `cd <project> && npm start` for this reason), merged with `process.env` (`.env` values win). Required variables depend on `SERVICENOW_OAUTH_GRANT_TYPE` (`client_credentials`, `password`, `authorization_code`, `refresh_token`, `interactive`).
- **Auth ([src/auth.js](src/auth.js))**: caches token state in memory, refreshes 60s before expiry, and prefers a held refresh token over re-running the configured grant. Posts to `/oauth_token.do`. The `interactive` grant ([src/interactive-login.js](src/interactive-login.js)) does browser sign-in (authorization code + PKCE, loopback redirect listener, tokens in memory only). A sign-in still pending after ~45s throws `SignInRequiredError` (deliberately *not* an `AuthError`, so `runtime.execute` does not retry and re-open the browser); the pending login is reused on the next call.
- **API client ([src/servicenow-client.js](src/servicenow-client.js))**: thin wrapper over `/api/now/table/...` (query, get by sys_id, create via POST, update via PATCH). `fetch` is injectable for tests. 401 → `AuthError`; other non-2xx → `ServiceNowApiError`.
- **Errors ([src/errors.js](src/errors.js))**: `ConfigError`, `AuthError`, `ServiceNowApiError`, and `toToolErrorResult()`, which maps them to MCP `isError` results. Unknown errors are intentionally reduced to a generic message.
- **Tools ([src/tools/](src/tools/))**: one file per tool (`query_table_records`, `get_record_by_sys_id`, `create_record`, `update_record`), each exporting a `register*Tool(server, executeTool)` function using `server.tool(name, description, zodShape, handler)`. Handlers wrap work in the shared `executeTool` from `tools/index.js`, which runs it through the runtime and formats via `results.js` (`displayText` in a payload overrides the JSON text output; `isError: true` in a payload yields an MCP error result).

- **`analyze_syslog`** ([src/tools/analyze-syslog.js](src/tools/analyze-syslog.js)): read-only analysis of `syslog` warnings/errors. Dates are parsed by [syslog-date-range.js](src/tools/syslog-date-range.js) (natural language, US month-first, current year assumed, 14-day inclusive UTC cap enforced before any network call); [syslog-analysis.js](src/tools/syslog-analysis.js) holds the pure pattern/category/spike analysis. Records are fetched one day at a time (1,500 newest-first per day; days that hit the cap are reported), and a 403 is rethrown with a hint about read access and the Table API auth scope. The table is hardcoded and only `queryTableRecords` is called; keep `syslog` out of `ALLOWED_CRUD_TABLES`.

### Write-path guardrails

- **Table allowlist**: `create_record` and `update_record` refuse any table not in `ALLOWED_CRUD_TABLES` ([src/tools/allowed-crud-tables.js](src/tools/allowed-crud-tables.js)) and return the allowed list in the error. The check happens *before* `executeTool`, so no auth/network happens for rejected tables. Read tools are not restricted. Extend the allowlist there when adding a writable table (tests assert every allowlisted table appears in the rejection message).
- **Script Include duplicate detection** ([src/tools/script-include-recommendations.js](src/tools/script-include-recommendations.js)): for `sys_script_include` create (and update when `fields.script` is set), the tool extracts function names from the script (plus optional `requestedFunctionNames`), queries existing Script Includes with `scriptLIKE…` encoded queries, and scores names (exact 100, normalized 95, else edit-distance similarity; threshold 85). Any match returns an error result with a markdown table and **does not write** to ServiceNow. On update, the record being edited is excluded via `excludeSysIds`.

## Testing notes

Tests in `test/` use no network: tools are tested by passing a fake `server` (capturing the `server.tool` handler) and a stub `executeTool`/client; runtime and auth accept injected factories/`fetchImpl` (`configLoader`, `authFactory`, `clientFactory` options in `createServiceNowRuntime`).

## Other

- [docs/tools/](docs/tools/) has one markdown file per tool (parameters, behavior, requirements). Update the matching file when a tool's behavior changes.
- [docs/best-practices.md](docs/best-practices.md) is a generic ServiceNow best-practices reference, unrelated to the code.
- `.history/` holds editor local-history snapshots (listed in `.gitignore`, though a few files were committed before that); ignore it.
