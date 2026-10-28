# Full Motchi checklist audit — 2026-10-28

Reviewed the agreed roadmap, source, release commits, verification records and historical workspace checklist at the user's request. The live checklist still held implementation promises as unchecked even after later releases verified them. This is evidence of missed reconciliation; automatic inference is not an accuracy guarantee.

Corrected 41 stale unchecked historical items using recorded evidence: Android project grouping and APIs, pairing/failure tests, local transcription controls, comments and explicit work, offline state, deployment/reconnection, the three designs, documentation and 0.14 checklist automation. Hook registration/activation is supported by the documented real shell Deny round trip; this does not establish coverage for arbitrary native permission cards.

Existing task IDs and original evidence are preserved. A private pre-audit snapshot and a detailed before/after audit record remain local. Updates use the same file lock as the running analyzer. Reviewed corrections are protected from model overwrites. Known repeated historical outcomes are annotated with their equivalent task IDs rather than deleting history or silently changing the denominator. This audit did not send implementation instructions or alter approval trust.

Missing roadmap entries were mirrored into the workspace checklist with their canonical acceptance states. Added AND-10 for the previously requested optional wake-name support and AND-11 for the verified reference appearance. The [full canonical checklist](../ROADMAP.md) and repository `.progress-pet.json` now contain **44 items: 11 complete and 33 open**.

| Area | Verified complete | Total |
| --- | ---: | ---: |
| Android calendar | 8 | 11 |
| Trustworthy understanding (P1) | 3 | 12 |
| Project discussion and delivery (P2) | 0 | 7 |
| Returning to work and attention (P3) | 0 | 6 |
| Personalization and forecasting (P4) | 0 | 5 |
| Character switching | 0 | 3 |

These are acceptance criteria, so existing partial foundations do not automatically check them off. The live workspace meter also includes historical development tasks and repeated outcomes; its percentage is not the roadmap's completion rate, an effort estimate or a shipping-readiness score.

## Work still open

- **Calendar hardening and field checks (AND-06/07):** signed installation and normal unlocked Mac reconnection work. Userdebug firmware still forces WebView inspection. Locked startup/login, sleep/wake, roaming, power-cycle and real multilingual/far-field microphone tests remain unverified.
- **Voice and access:** wake-name listening (AND-10) is not implemented; current recording is push-to-talk. The real microphone-level event path exists, but on-device amplitude responsiveness still needs independent verification. Notification access is verified; a pinned home-screen shortcut depends on launcher support and has not been confirmed.
- **Checklist understanding:** broader idea/decision classification, replacement/deferral/reopening, expand/replace matching, milestone scope and representative quality evaluation remain open (CHK-01/02/03, PRG-01, QA-01). Automatic matching, completion evidence, source history and Undo are implemented (CHK-04/05, SYNC-01). Review is asynchronous; instant updates and elimination of missed completions have not been demonstrated.
- **On-device checklist follow-through:** the connected dashboard visibly shows the reconciled live count. A fresh assistant completion flowing into an open calendar checklist has not been exercised; the historical device-detail verification item stays open. Browser/sample and automated evidence do not substitute for that field check.
- **Project discussion and memory:** richer natural intent routing, milestone-aware answers, delivery lifecycle/routing evaluation, inspectable persistent preferences/goals/decisions, returning summaries and a cross-project inbox remain open. Existing Android project identity, read-only questions and explicit send controls are partial foundations.
- **Personalization:** character registry/picker/animation checks, quiet hours, controlled preference learning, optional weighting and forecasting stay planned.
- **Desktop approval coverage:** supported hook replies work. Native filesystem/network cards can bypass the hook, and universal approval handling remains unverified. Android approval controls remain outside this release.

The reference design update is recorded in [the appearance verification](ANDROID_APPEARANCE.md). Source details and the limited model evaluation remain in [automatic checklist verification](AUTOMATIC_CHECKLISTS.md); this audit is not a new model accuracy study.
