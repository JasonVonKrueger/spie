---
applyTo: "**"
description: "Use when creating or modifying ServiceNow artifacts/tools; enforce naming, scope, and governance-safe payload conventions."
---
# ServiceNow Naming And Governance

- Use clear, purpose-driven names that describe behavior and target object.
- For ATF tests, require the prefix ATF - at the beginning of name.
- For Script Includes, prefer CompanyPrefixFeatureHelper, CompanyPrefixFeatureService, or CompanyPrefixFeatureValidator patterns.
- For UI Actions, use user-facing names as Title Case labels and stable snake_case action_name values.
- For UI Pages, use concise functional names tied to the workflow they support.
- Keep API names and record names aligned where platform conventions permit.
- Set active intentionally; default new automation artifacts to inactive unless immediate activation is explicitly requested.
- Include description text that states purpose, trigger surface, and expected behavior.
- Prefer scoped ownership and avoid creating global artifacts unless explicitly required by dependency/runtime constraints.
- Reject ambiguous names and require a clearer intent-bearing name before creation.
