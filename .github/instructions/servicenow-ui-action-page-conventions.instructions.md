---
applyTo: "src/spie_mcp/server.py,README.md,docs/**/*.md,.github/**/*.md"
description: "Use when creating or modifying ServiceNow UI Actions or UI Pages; enforce naming, single-purpose actions, restrained UI Page usage, and client/server separation."
---
# ServiceNow UI Action And UI Page Conventions

- Name UI Actions with a clear user-facing label and a stable snake_case action_name.
- Name UI Pages with a concise purpose-driven name tied to the workflow they support.
- UI Actions should do one user-facing thing.
- UI Pages should be used sparingly and only when standard UI options are insufficient.
- Keep server-side processing and client-side rendering separate.
