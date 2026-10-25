# Existing implementation baseline

Snapshot prepared on 2026-10-25 from the local Progress Dog / Mochi 0.11.0 source, including the later optional auto-launch helper.

Existing foundations documented by the project:

- Transparent Mac dog popup, animation, double right-click and short top-right announcements.
- Local project discovery and automatic topic selection; separate drafts and project histories.
- Project status answers and a shared checklist with source evidence and manual overrides.
- Structured-plan and recent-conversation checklist reconciliation; semantic same/different clarification.
- Additional instructions to Mochi-owned active/idle chats, with uncertain delivery handling.
- Direct clarification replies and supported real approvals via live owned tasks or a trusted synchronous PermissionRequest hook.
- Optional login helper that launches Mochi when Codex desktop opens; verified live on 2026-10-24.

Known limits:

- Existing desktop-only chats cannot universally receive injected instructions or approval replies.
- Native filesystem/network permission cards may bypass the hook and retain Review in Codex.
- Conversation extraction is limited to available recent local history and may fail; the current state has a visible sync-unavailable notice.
- Current task-count progress is not a verified measure of shipping readiness, task effort, or a completion forecast.
- The roadmap's persistent memory, richer task lifecycle, audit/undo, multi-project inbox and personalization still require development and acceptance checks.

This snapshot is documentation and source import. It is not a new end-to-end verification of every legacy feature. See the plugin README and tests for previous validation and integration details.
