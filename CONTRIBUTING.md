# Contributing to SPIE

Thanks for your interest in contributing to the ServiceNow Platform Intelligence Engine (SPIE) project.

This guide explains how to set up your environment, make changes safely, and submit high-quality pull requests.

## Scope

SPIE is a Python MCP server for ServiceNow analysis and artifact automation.

Core code locations:

- `src/spie_mcp/server.py`: MCP tool definitions and orchestration
- `src/spie_mcp/client.py`: ServiceNow API transport and record operations
- `docs/`: user and operator documentation

## Prerequisites

- Python 3.10+
- `uv`
- Access to a ServiceNow instance (for integration testing)

## Local Setup

1. Install dependencies:

```bash
uv sync
```

2. Create a local `.env` file (optional but recommended), or export environment variables in your shell.

Common variables:

- `SERVICENOW_INSTANCE_URL`
- `SERVICENOW_USERNAME`
- `SERVICENOW_PASSWORD`
- `SERVICENOW_BEARER_TOKEN`
- `SERVICENOW_OAUTH_CLIENT_ID`
- `SERVICENOW_OAUTH_CLIENT_SECRET`
- `SERVICENOW_OAUTH_TOKEN_URL`
- `SERVICENOW_TIMEOUT`

3. Run the server:

```bash
uv run python -m spie_mcp
```

4. Optional local inspection:

```bash
uv run mcp dev src/spie_mcp/server.py
```

## Development Guidelines

- Keep changes focused and minimal.
- Prefer small, composable helper functions over large monolithic logic.
- Keep API payload handling explicit and defensive.
- Update docs when behavior, arguments, defaults, or output shapes change.

### ServiceNow Governance Rules

Contributions in this repo should follow these behavior constraints:

- Favor read/create/update-only flows for ServiceNow automation.
- Do not introduce delete operations in MCP tools.
- Keep naming and governance checks in place for ServiceNow artifacts.
- Return actionable, non-destructive failure details when partial creation fails.

For detailed conventions, review files in `.github/instructions/`.

## Testing and Validation

Before opening a pull request:

1. Verify the package installs and runs:

```bash
uv sync
uv run python -m spie_mcp
```

2. If your change affects MCP tool behavior, exercise impacted flows with representative inputs.

3. If your change affects docs, verify examples and command snippets still match actual behavior.

4. For logic that can be validated without credentials, use a fake or patched client in local snippets.

## Pull Request Checklist

- Clear title and summary of the change
- Why the change is needed
- What behavior changed (including any breaking change)
- Documentation updated where relevant
- Manual validation steps included
- No unrelated refactors bundled in the same PR

## Commit Guidance

- Use concise, descriptive commit messages.
- Group related changes into coherent commits.
- Avoid mixing behavior changes and broad formatting-only edits.

## Security and Secrets

- Never commit credentials, tokens, or `.env` files.
- Sanitize logs, screenshots, and examples before sharing.
- Use least-privilege ServiceNow credentials for testing.

## Questions

If you are unsure about naming, scope, or artifact strategy, open a draft PR with your proposal and assumptions. Early feedback is encouraged.
