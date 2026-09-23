# get_record_by_sys_id

Fetch a single record from a ServiceNow table by its `sys_id`. Read-only, and not limited to the write allowlist.

## Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `table` | string | Yes | Table name, for example `sys_script_include`. |
| `sysId` | string | Yes | The record's `sys_id`. |
| `fields` | string[] | No | Fields to return. Omit to return all fields. |

## Result

JSON containing `table`, `sysId`, and `result` (the record).

## Notes

- A `sys_id` that does not exist, or that the signed-in user cannot read, returns a ServiceNow API error.
