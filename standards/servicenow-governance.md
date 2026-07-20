# ServiceNow Governance Standards

## Purpose

These standards define naming, ownership, and delivery conventions for ServiceNow configuration and code artifacts.

## General Rules

- Use descriptive, consistent names across all artifacts.
- Prefer application scope over global scope unless a global artifact is required.
- Keep records small, focused, and reusable.
- Document the business purpose of every custom artifact.
- Avoid abbreviations unless they are widely understood by the team.
- Treat customizations as product code: version, review, test, and promote them deliberately.

## Update Sets

### Naming Convention

Use this pattern:

`<APP or DOMAIN> - <SHORT PURPOSE> - <ENV or TICKET>`

Examples:

- `HR - Onboarding Form Fix - INC12345`
- `ITSM - Catalog Cleanup - DEV`
- `FIN - Notification Rules - CHG67890`

### Rules

- Keep update sets small and scoped to one change theme.
- Do not mix unrelated work in the same update set.
- Add a clear description before marking an update set complete.
- Always review preview errors before promotion.
- Close or clone update sets only after validation is complete.
- Use a dedicated update set for hotfixes and emergency changes.

## Script Includes

### Naming Convention

Use one of these patterns:

- `CompanyPrefixFeatureHelper`
- `CompanyPrefixFeatureService`
- `CompanyPrefixFeatureValidator`

Examples:

- `ACMEIncidentHelper`
- `ACMECatalogService`
- `ACMEUserValidator`

### Rules

- Script Include names must describe the service or helper purpose.
- Put reusable logic in Script Includes instead of repeating it in Business Rules or UI Actions.
- Keep methods focused and single-purpose.
- Prefer server-side validation and business logic in Script Includes.
- Mark Script Includes as client callable only when client-side access is required.
- Add comments only where logic is non-obvious.

## System Properties

### Naming Convention

Use a reverse-domain or product-prefixed pattern:

`<company>.<product>.<area>.<setting>`

Examples:

- `acme.itsm.catalog.max_items`
- `acme.hr.onboarding.enable_notifications`
- `acme.platform.integration.timeout_seconds`

### Rules

- Use lowercase names with dots as separators.
- Keep property names stable once published.
- Store boolean values as `true` or `false`.
- Use short, clear values and document expected types.
- Group related properties by prefix.
- Avoid using properties as a substitute for good design.

## Business Rules

### Naming Convention

`<Table> - <Trigger or Outcome> - <Short Purpose>`

Examples:

- `Incident - Before Insert - Set Priority`
- `Task - After Update - Sync Assignment`
- `Catalog Item - Before Update - Validate Variables`

### Rules

- Prefer before rules for validation and field defaults.
- Use after rules for integration or downstream side effects.
- Avoid recursive updates.
- Keep script logic short and delegate to Script Includes when possible.

## Client Scripts and Catalog Client Scripts

### Naming Convention

`<Table or Item> - <Behavior> - <Purpose>`

Examples:

- `Incident - On Load - Hide Internal Fields`
- `Catalog Item - On Change - Validate Requested For`

### Rules

- Use client scripts only when the behavior must happen in the browser.
- Prefer UI Policies for simple visibility and mandatory logic.
- Keep client scripts fast and readable.

## Catalog Items

### Naming Convention

`<Category> - <Request Name>`

Examples:

- `Hardware - Laptop Request`
- `Access - VPN Request`
- `HR - Employee Onboarding`

### Rules

- Use consistent variable names across similar catalog items.
- Reuse variable sets when appropriate.
- Keep catalog UI policies and scripts minimal.
- Test fulfillment paths end to end before publishing.

## UI Actions and UI Pages

### Naming Convention

- UI Actions: `<Table> - <Action Name>`
- UI Pages: `<Purpose> Page`

Examples:

- `Incident - Escalate`
- `Request - Approve`
- `Approval Page`

### Rules

- UI Actions should do one user-facing thing.
- UI Pages should be used sparingly and only when standard UI options are insufficient.
- Keep server-side processing and client-side rendering separate.

## ATF Tests

### Naming Convention

`ATF - <App or Process> - <Scenario>`

Examples:

- `ATF - Catalog - Submit Laptop Request`
- `ATF - Incident - Validate Priority Logic`

### Rules

- Each ATF test should validate one business scenario.
- Keep test data deterministic.
- Clean up test-created records when possible.
- Reuse step configs and input variables where appropriate.

## Naming Conventions for Custom Fields

### Rules

- Use lowercase with underscores for field names.
- Keep field names business-oriented and unambiguous.
- Avoid duplicate meanings across tables.
- Document any field that is used in integrations or scripting.

## Governance and Review

- Review customizations for naming compliance before promotion.
- Require peer review for all code and configuration changes.
- Verify that updates include test coverage where practical.
- Maintain a changelog or release note for each promoted change.
- Periodically audit old update sets, unused properties, and orphaned artifacts.

## Quick Checklist

- Is the name descriptive and consistent?
- Is the artifact in the correct scope?
- Is logic reused instead of duplicated?
- Is the change tested in ATF or equivalent validation?
- Is the business purpose documented?
- Would another developer understand this in six months?
