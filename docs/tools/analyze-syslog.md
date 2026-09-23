# analyze_syslog

Analyzes records in the `syslog` table between a start date and an end date, to look for potential problems in the platform.

**Read-only.** The tool only queries `syslog`. The table is fixed (it is not a parameter), no create, update, or delete call is ever made, and `syslog` is not in the [write allowlist](../../src/tools/allowed-crud-tables.js), so [create_record](create-record.md) and [update_record](update-record.md) cannot change it either.

## Parameters

| Name | Type | Required | Description |
| --- | --- | --- | --- |
| `startDate` | string | Yes* | First day to analyze. |
| `endDate` | string | Yes* | Last day to analyze, inclusive. |

\* If either is missing, the tool does not contact ServiceNow. It replies asking for the missing date, and the tool description tells the assistant to ask you for both dates first.

### Dates

Dates can be written naturally. When no year is given, the current year is assumed.

| Accepted | Examples |
| --- | --- |
| Numeric (month first) | `09/23/2026`, `9/23`, `9-23-2026` |
| ISO | `2026-09-23` |
| Month names | `Sept 23, 2026`, `September 23rd`, `Sep. 23` |
| Day first | `23 September 2026`, `23 Sep` |
| Relative | `today`, `yesterday` |

Unreadable dates, impossible dates such as `02/30`, and an end date before the start date are rejected with an explanation.

### Range limit

The range is inclusive, is interpreted in **UTC** (00:00:00 on the start date through 23:59:59 on the end date), and cannot exceed **14 days** (2 weeks). A longer range is rejected before ServiceNow is contacted.

## What it analyzes

Only **warning and error** records (`level` 1 and 2) are analyzed. They are fetched **one day at a time**, newest first, up to **1,500 records per day**, in pages of 500. A noisy day therefore cannot crowd out the other days. If a day reaches the cap, the report names the day and says its earliest hours are missing and its counts are minimums.

From those records the tool:

- **Merges duplicates.** `com.glide.ui.ServletErrorListener` re-logs many messages as `<source>: <message>: no thrown error`. Those copies are merged into the record logged under the real source, or re-attributed to their real source if there is no twin.
- **Groups recurring messages** into patterns, treating sys_ids, timestamps, hex values, and numbers as the same, then records the count, first seen, last seen, source, and a sample message.
- **Categorizes and rates** each pattern with keyword rules: Security, Database / resources, Performance, Integration, Scheduler / events, Script errors, or Other. Severity is `high`, `medium`, or `low` (errors rank above warnings, and high volume raises the rating).
- **Collapses known noise** into a single low-priority line instead of the problems table: ML / Predictive Intelligence not active or unreachable, and usage-analytics uploads or downloads refused with HTTP 403.
- **Flags volume spikes**: days with at least 20 warning/error records and at least twice the median day.
- **Lists the sources** with the most errors.

## Output

A markdown report with these sections:

1. A summary line: unique records analyzed, errors, warnings, distinct patterns, and duplicates merged.
2. A partial-coverage notice, if any day hit the per-day cap.
3. **Potential problems**: a table of the top 15 patterns (severity, category, level, count, source, first and last seen, sample), and how many lower-ranked patterns are not shown.
4. **Likely configuration or telemetry noise (low priority)**.
5. **What to check**: a hint for each category that appears.
6. **Volume spikes** and **Sources with the most errors**.

The structured result also includes the resolved date range, the per-day counts, and the truncated days.

## Requirements

- The signed-in user needs **read access to `syslog`**. By default that is typically the `admin` role, or a custom role with a read ACL on `syslog`.
- If you use an OAuth integration, its **Auth scope must include the Table API**. See [Creating the OAuth integration](../../README.md#creating-the-oauth-integration-for-interactive-sign-in).
- If access is denied, the tool returns a 403 error that explains both requirements.

## Limitations

- Category and severity are keyword-based heuristics. Treat findings as leads to investigate, not confirmed faults.
- Info and debug records are not analyzed.
- Message text with a space before the first colon (for example `DMJob DMTableCleaner: ...`) is not re-attributed from `ServletErrorListener`.
