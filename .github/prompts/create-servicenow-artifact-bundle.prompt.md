---
mode: "agent"
description: "Create a ServiceNow artifact bundle for a workflow, including Script Include, client-callable wrapper, UI Action, UI Page modal, and optional ATF test scaffolding."
---
# Create ServiceNow Artifact Bundle

Create a cohesive ServiceNow bundle for a requested workflow.

## Required Inputs

- workflow_name: human-readable workflow label.
- target_table: table for the UI Action, for example sys_update_set.
- server_script_include_name: primary server-side Script Include to create or reuse.
- ajax_wrapper_name: client-callable Script Include used by GlideAjax.
- ui_action_name: form action label shown to users.
- ui_page_name: modal UI Page name.

## Optional Inputs

- atf_test_name: ATF test name; if omitted, skip ATF creation.
- activate_artifacts: true or false.
- action_order: integer order for UI Action.
- action_condition: condition script for UI Action visibility.
- modal_title: title shown in GlideModal.

## Output Requirements

- Create or update artifacts in an order that avoids broken references.
- Return each artifact name and sys_id.
- Return warnings for assumptions, naming deviations, or protected-table bypasses.
- Provide a test checklist for manual verification.

## Implementation Sequence

1. Validate naming and constraints against repository governance.
2. Create or update the server Script Include behavior.
3. Create or update the client-callable Ajax wrapper Script Include.
4. Create or update the UI Page with modal markup and client script.
5. Create or update the client-side UI Action wired to the UI Page and Ajax wrapper.
6. Optionally create ATF test scaffolding if atf_test_name is supplied.
7. Summarize created/updated records with sys_ids and next-step checks.

## Safety Rules

- Do not create deletion tools or deletion rollback paths.
- Prefer read/create/update-only patterns.
- If protected-table bypass is required, explain why and limit the change to the minimum required scope.
