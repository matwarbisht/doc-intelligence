# Northstar planning notes

> Fictional sample for development only.

## Decisions

- The team will release the reliability dashboard before the bulk-import tool.
- Priya owns the dashboard rollout and Marco owns the migration guide.
- The pilot date is October 14, 2026.

## Risks

The retry queue still loses progress when a worker restarts during a long export.
The team agreed to persist checkpoints before inviting the second pilot customer.

## Follow-up

Review error-budget data on September 28 and decide whether the pilot needs to be
limited to ten workspaces.
