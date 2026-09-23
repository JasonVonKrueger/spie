# SPIE tools

The tools SPIE exposes to MCP clients. Source lives in [src/tools/](../../src/tools/).

| Tool | Purpose | Writes to ServiceNow? |
| --- | --- | --- |
| [query_table_records](query-table-records.md) | Query records from any table | No |
| [get_record_by_sys_id](get-record-by-sys-id.md) | Fetch one record by `sys_id` | No |
| [create_record](create-record.md) | Create a record in an allowed table | Yes, allowlisted tables only |
| [update_record](update-record.md) | Update a record in an allowed table | Yes, allowlisted tables only |
| [analyze_syslog](analyze-syslog.md) | Look for potential platform problems in `syslog` | No (read-only) |

## Write guardrails

`create_record` and `update_record` only work on tables listed in [allowed-crud-tables.js](../../src/tools/allowed-crud-tables.js). The check happens before any authentication or network call, and a rejection returns the current allowed list. The read tools are not restricted by that list.

Everything a tool can do is also limited by the ServiceNow account SPIE signs in with. See [Interactive browser sign-in](../../README.md#interactive-browser-sign-in).
