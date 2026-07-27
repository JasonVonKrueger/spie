---
applyTo: "src/spie_mcp/server.py,src/spie_mcp/client.py,README.md,docs/**/*.md,.github/**/*.md"
description: "Use when creating or modifying ServiceNow artifacts; enforce shared governance rules for naming quality, scope choice, reuse, documentation, review, and testing."
---
# ServiceNow General Governance

- Use descriptive, consistent names across all artifacts.
- Prefer application scope over global scope unless a global artifact is required.
- Keep records small, focused, and reusable.
- Document the business purpose of every custom artifact.
- Avoid abbreviations unless they are widely understood by the team.
- Treat customizations as product code: version, review, test, and promote them deliberately.
- Review customizations for naming compliance before promotion.
- Require peer review for code and configuration changes when the delivery process supports it.
- Verify that updates include test coverage or equivalent validation where practical.
- Maintain change notes or release context for promoted changes.
- Periodically audit unused or orphaned artifacts and stale configuration.
