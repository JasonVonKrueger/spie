---
applyTo: "src/spie_mcp/**/*.py,README.md,docs/**/*.md"
description: "Use when creating or modifying ATF records and ATF helper flows; enforce consistent naming, safety, and validation conventions."
---
# ServiceNow ATF Conventions

- Name ATF tests with the prefix ATF - followed by a concise behavior statement.
- Include a description that documents test intent, data assumptions, and expected outcome.
- Default new ATF tests to active=false unless explicitly requested otherwise.
- Prefer deterministic ATF steps with explicit inputs over environment-dependent behavior.
- Validate required step configuration and input variables before creating ATF step input values.
- Return actionable error messages that include missing parameters and affected artifacts.
- Never rely on destructive rollback for ATF helper errors; report manual cleanup details when partial creation occurs.
- Keep ATF helper functions idempotent where practical, and avoid duplicate-step creation on retries.
- For ATF bundle creation, surface created test and step sys_ids in responses to support auditability.
- When updating ATF artifacts, modify only specified fields and preserve unspecified behavior.
