# Alert Grouping Design Notes

## Goal

Reduce alert noise by grouping related issues and suppressing less useful child
alerts when a clearer parent/root-cause alert exists.

## Common Alerting Pattern

Monitoring systems such as Prometheus Alertmanager and Grafana Alerting commonly
use:

- Grouping: combine related alerts into one notification.
- Group wait: wait briefly before the first notification so related alerts can
  be batched.
- Group interval: wait before sending another notification when a group changes.
- Repeat interval: resend still-active alerts after a longer interval.
- Inhibition/suppression: hide lower-level alerts when a higher-level alert
  already explains the failure.

## Proposed Model

Keep individual issues in Redis, but add enough metadata for the alert service
to group and suppress them.

Suggested issue fields:

- `group_id`: node URL, app ID, or `system`.
- `issue_type`: stable issue kind, such as `node_state`, `receiver`,
  `scorer`, `node_version`, or `backup_service`.
- `severity`: for example `critical`, `warning`, or `info`.
- `updated_at`: last time the monitor touched the issue.
- `suppressed`: whether this issue is hidden by a parent issue.

Node-specific checks should use the node URL as `group_id`.
System-wide checks should use `system` or another stable group name.

## Notification Timing

Suggested config values:

```env
GROUP_WAIT=60
GROUP_INTERVAL=300
REPEAT_INTERVAL=21600
```

Meaning:

- `GROUP_WAIT`: wait 60 seconds before the first notification for a new group.
- `GROUP_INTERVAL`: wait 5 minutes before sending an update when the group
  changes.
- `REPEAT_INTERVAL`: repeat an unchanged active group every 6 hours.

Alert timing should eventually be tracked per group, not only per issue.

## Node Down Suppression

If a node stops responding, `node_state_down` should become the main alert for
that node.

While `node_state_down` is active for a node:

- Suppress child node alerts such as receiver, scorer, sender, version, updater,
  profile, and node balance issues.
- Do not mark child issues resolved only because the node is down.
- When the node comes back, run the child checks again and resolve or re-alert
  based on the current state.

Example:

```text
Node: node.brightid.org

Active alert:
- Node is not reporting its state.

Suppressed child alerts:
- Consensus receiver service is offline.
- Node version is outdated.
```

## Suggested Implementation Direction

1. Extend the shared `Issue` model with grouping fields.
2. Update monitor issue creation to pass `group_id` and `issue_type`.
3. Add group-level state in Redis for notification timing.
4. Update alert service to fetch issues, group them by `group_id`, apply
   suppression rules, and send one message per group.
5. Keep the existing per-issue alert behavior until group sending is ready, so
   the change can be rolled out safely.
