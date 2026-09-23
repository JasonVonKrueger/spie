# create_record

Create a record in an allowed ServiceNow table.

## Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `table` | string | Yes | Table to create the record in. Must be on the allowlist. |
| `fields` | object | Yes | Field names and values for the new record. Must contain at least one field. |
| `requestedFunctionNames` | string[] | No | Extra function names to check for duplicates when creating a Script Include. |

## Table allowlist

Only tables listed in [allowed-crud-tables.js](../../src/tools/allowed-crud-tables.js) can be written. For any other table the tool returns an error that includes the current allowed list, and it does not authenticate or contact ServiceNow. To make another table writable, add it to that file.

## Script Include duplicate detection

When the table is `sys_script_include`, the tool checks for existing functions with the same or a very similar name before writing:

1. It extracts function names from `fields.script`, plus any `requestedFunctionNames`.
2. It searches existing Script Includes whose script contains those names.
3. It scores each name against the existing ones: an exact match scores 100, a match after normalization scores 95, and otherwise an edit-distance similarity is used. A score of 85 or more counts as a possible duplicate.

If any possible duplicates are found, the tool returns an error with a markdown table (existing Script Include, API name, possible duplicate function, and a direct ServiceNow link) and **does not create the record**. If none are found, the record is created.

## Result

JSON containing `table` and `result` (the created record).
