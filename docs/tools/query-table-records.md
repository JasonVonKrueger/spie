# query_table_records

Query records from a ServiceNow table using the Table API. Read-only, and not limited to the write allowlist.

## Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `table` | string | Yes | Table name, for example `incident`. |
| `query` | string | No | ServiceNow encoded query, for example `active=true^priority=1`. |
| `fields` | string[] | No | Fields to return. Omit to return all fields. |
| `limit` | integer, 1 to 100 | No | Maximum records to return. Default 10. |
| `offset` | integer, 0 or more | No | Number of records to skip, for paging. Default 0. |

## Result

JSON containing `table`, `query`, `offset`, `limit`, and `result` (the matching records).

## Notes

- Results are subject to the signed-in user's read access to the table.
- To page through results, increase `offset` by `limit` until fewer than `limit` records come back.
