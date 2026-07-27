---
applyTo: "**"
description: "Use when creating or modifying ServiceNow MCP tools/flows; enforce read/create/update-only behavior and prohibit record deletion."
---
# ServiceNow No-Delete Policy

- Treat ServiceNow deletion as prohibited in this repository.
- Never add or expose delete-capable tools, wrappers, or helper functions for ServiceNow records.
- Never issue HTTP DELETE calls to ServiceNow Table API from this codebase.
- Avoid rollback logic that deletes records after partial failures; return clear manual-cleanup guidance instead.
- For validation and probe flows, use read/create/update checks only; do not create-then-delete test records.
- If a user asks to delete records, refuse to implement deletion in SPIE and recommend controlled cleanup via approved ServiceNow admin process.
