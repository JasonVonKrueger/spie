---
applyTo: "src/spie_mcp/server.py,README.md,docs/**/*.md,.github/**/*.md"
description: "Use when creating or modifying ServiceNow client scripts or catalog client scripts; enforce naming, browser-only behavior, UI Policy preference, and script simplicity."
---
# ServiceNow Client Script Conventions

- Name client scripts and catalog client scripts with the pattern `<Table or Item> - <Behavior> - <Purpose>`.
- Use client scripts only when the behavior must happen in the browser.
- Prefer UI Policies for simple visibility and mandatory logic.
- Keep client scripts fast, readable, and narrowly scoped.
- Never use server-side APIs in client scripts; use GlideAjax and Script Includes for server-side logic.
