# Automatic checklist updates — 0.14

The user requested an Android APK with automatic same/different decisions and checkmarks as work completes, on 2026-10-28. The Mac remains the analysis host; update the APK and the Mac companion scripts together.

## Behavior

- Model extraction compares every supplied history section against existing task outcomes and acceptance criteria. Equivalent requests retain a task ID; distinct outcomes receive separate unchecked items. Word similarity alone cannot merge scope. Uncertain comparison stays separate. Reasons and source evidence remain inspectable.
- Old duplicate questions are reviewed automatically. Their saved instructions stay unsent; migration cannot invoke the delivery path. New explicit work still requires the existing Send confirmation and exact supported chat route.
- Completed bound plan steps update on the next observation. New assistant completion messages receive a bounded priority review before older backlog when a project already has tasks. A successful live review records its own cursor/time without advancing the historical checkpoint. Historical catch-up remains idempotent and continues reviewing every available section.
- Two workers serve projects, with one review per project. Failure preserves pending history and retries after at least 15 seconds. Concurrent checklist edits invalidate stale model analysis. This is automatic after observation/review, not zero-latency completion.
- Manual checkmarks and Undo corrections remain protected. Full-task completion needs assistant evidence or a completed recorded plan step; a finished turn, intent, partial work and a related task's completion are insufficient. Existing source quote, role, timestamp and task-ID validation remain in place.
- Android 0.14.0 (versionCode 4) refreshes approximately every three seconds. Project details show automatic-review status, missing-Mac-update advice, latest live-review time, reasons, source evidence and Undo. Offline progress stays readable. Three saved home layouts and the Open Motchi notification remain available.

## Checks

All 14 Python suites pass, including 13 focused automatic-checklist cases and the existing history transport, delivery, approval and portal checks. The Android suites pass 22 core/review-state cases and 20 appearance/isolation cases. The signed release build, Android lint, JavaScript syntax and APK signature verification pass.

Two optional live model smoke samples passed using the configured signed-in provider: 12 mixed-intent messages and eight automatic-matching messages. Each matched all three expected actions with no extra, duplicate, invalid-evidence or unsupported-completion actions in that sample. The matching sample distinguishes CSV/PDF scope and leaves partial dashboard/cache work and manually corrected work unchecked. These tiny synthetic samples do not establish an overall accuracy rate or guarantee future interpretations.

The loopback-only sample preview demonstrated an automatic completion moving 2/4 tasks (50%) to 3/4 (75%), retaining its evidence and Undo. Undo returned the task to unchecked with a protected manual correction. The preview's projects are illustrative; no live execution instructions were submitted through it.

The installed Mac companion scripts were updated in place and restarted, retaining the Android pairing data. The signed Android APK is prepared for download. The calendar is absent from the current wireless ADB inventory; **0.14 has not yet been installed or checked on that device**. The last device-verified version remains 0.13.2. Device field and firmware limits in ANDROID_VERIFICATION.md remain open.

## Boundaries

Available local project conversations only; no reconstruction of missing, remote-only or archived history. The Mac must be awake on the same network. Model review can fail, omit or misclassify items. Scope replacement/deferral, richer lifecycle and broad quality evaluation remain separate roadmap work. Approval handling and explicit execution controls are unchanged.
