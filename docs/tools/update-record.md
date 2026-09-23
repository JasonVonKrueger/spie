# update_record

Update a record in an allowed ServiceNow table by `sys_id`. Only the fields you pass are changed.

## Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `table` | string | Yes | Table containing the record. Must be on the allowlist. |
| `sysId` | string | Yes | The `sys_id` of the record to update. |
| `fields` | object | Yes | Field names and new values. Must contain at least one field. |
| `requestedFunctionNames` | string[] | No | Extra function names to check for duplicates when updating a Script Include script. |

## Table allowlist

Only tables listed in [allowed-crud-tables.js](../../src/tools/allowed-crud-tables.js) can be written. For any other table the tool returns an error that includes the current allowed list, and it does not authenticate or contact ServiceNow.

## Script Include duplicate detection

When the table is `sys_script_include` **and** `fields.script` is being set, the tool runs the same duplicate check as [create_record](create-record.md#script-include-duplicate-detection). The record being edited is excluded from the comparison, so a Script Include is never flagged as a duplicate of itself. If possible duplicates are found, the tool returns an error with a markdown table and **does not update the record**. Updates that do not touch `script` skip the check.

## Result

JSON containing `table`, `sysId`, and `result` (the updated record).
