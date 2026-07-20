# ServiceNow Best Practices

## Platform Governance

- Define clear instance strategy across dev, test, and prod with formal promotion paths.
- Use update sets or source control consistently; avoid mixed deployment patterns.
- Maintain naming conventions for applications, tables, fields, scripts, and APIs.
- Keep app scope boundaries clear and avoid unnecessary global-scope customization.
- Document ownership for every app, integration, and major automation.

## Data Model and CMDB

- Reuse out-of-box tables and fields before creating custom schema.
- Use reference fields and related lists instead of duplicated text data.
- Add dictionary attributes deliberately and document why each one exists.
- Index high-volume query fields based on proven access patterns.
- Keep CMDB class hierarchy clean; avoid class proliferation without governance.

## Scripting and Code Quality

- Prefer Script Includes for reusable server-side logic.
- Keep Business Rules small and focused; route shared logic to Script Includes.
- Use async processing for non-blocking work where possible.
- Add guard conditions in Business Rules to prevent recursive updates.
- Avoid GlideRecord queries in loops when batching or prefetching can be used.
- Use GlideAggregate for counts and grouped metrics instead of row-by-row loops.
- Log with intent and context; avoid noisy logs in production.
- Add meaningful comments only for non-obvious logic or integration constraints.

## Client-Side Performance

- Minimize client scripts and UI policies on heavily used forms.
- Prefer UI Policies for simple field behavior over scripted logic.
- Avoid synchronous GlideAjax calls from client scripts.
- Keep catalog client scripts scoped and specific to necessary items/variables.
- Test form responsiveness on low-bandwidth and high-latency scenarios.

## Security and Access Control

- Enforce least-privilege roles for users, integrations, and automation accounts.
- Use ACLs over ad hoc script checks for record and field security.
- Validate impersonation behavior in all privileged workflows.
- Keep secrets out of scripts; use credential records and connection aliases.
- Review elevated privilege usage and expire temporary access quickly.
- Audit public processors and script endpoints for data exposure risks.

## Integrations and APIs

- Use connection & credential aliases and avoid hard-coded endpoints.
- Add timeout, retry, and error-handling strategies for outbound REST/SOAP calls.
- Version custom APIs and maintain backward compatibility where possible.
- Validate inbound payloads and sanitize all external input.
- Include correlation IDs for cross-system troubleshooting.

## Flow Designer and Automation

- Use subflows for reusable orchestration logic.
- Keep flow trigger conditions narrow to avoid accidental execution.
- Add explicit error branches and notification paths for failed actions.
- Avoid long-running synchronous actions when asynchronous alternatives exist.
- Monitor flow execution metrics and optimize frequent paths.

## ATF and Testing

- Create ATF coverage for critical business workflows and integrations.
- Keep test data deterministic and isolate environment dependencies.
- Add rollback/cleanup steps for test-created records.
- Run ATF suites in CI/CD gates before production promotion.
- Track flaky tests and remediate root causes quickly.

## Catalog and Request Management

- Standardize catalog item templates for consistency.
- Use variable sets to reduce duplication across similar items.
- Keep catalog UI policies and client scripts simple and purpose-specific.
- Validate request fulfillment paths end to end with realistic approvals.
- Monitor item analytics to retire low-value catalog complexity.

## Performance and Operations

- Establish performance baselines for key transactions.
- Review slow queries and long-running scripts regularly.
- Keep scheduled jobs lean and avoid overlapping heavy workloads.
- Use instance scan and health scan findings to drive remediation backlogs.
- Archive or purge stale data according to retention policy.

## Release and Change Management

- Use peer review for scripts, flows, and security-related configuration.
- Bundle related changes and avoid oversized release batches.
- Add rollback plans for high-risk changes.
- Validate clone strategy and post-clone task checklists.
- Record release notes with user impact and support guidance.

## Documentation and Knowledge Transfer

- Document design decisions, assumptions, and known constraints.
- Maintain runbooks for integrations, scheduled jobs, and support workflows.
- Keep admin and support troubleshooting guides current.
- Capture incident learnings and feed them back into standards.
- Review best practices quarterly and align to platform roadmap.
