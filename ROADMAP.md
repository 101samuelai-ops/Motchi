# Motchi product roadmap

Agreed on 2026-10-25. This is a future-work checklist, not a claim that these features are implemented. Existing source provides partial foundations; each item remains unchecked until its acceptance criteria and relevant checks pass.

The canonical planning checklist is this file. `.progress-pet.json` contains the same stable task IDs for the Motchi progress panel. Keep their completion states synchronized when work is actually verified. New ideas and optional experiments should be recorded outside the active milestone until agreed.

## Android calendar companion — approved 2026-10-27

The separate Android app uses the Mac over the same Wi-Fi. See [setup](docs/ANDROID.md) and [verified rollout and remaining checks](docs/ANDROID_VERIFICATION.md). No remote approvals or launcher replacement in this release. Optional wake-name listening and Mac microphone fallback are implemented in 0.17 with free local Qwen3-ASR and streaming keyword detection; optional Doubao Speech needs separate API setup. AND-10 remains open for human speech and field validation. See [voice controls and verification limits](docs/ANDROID_VOICE.md).

- [x] **AND-01: Verify the signed Android compatibility app** — Done when: Installation, rendering, touch, microphone and pinned local networking pass on the calendar before dashboard development.
- [x] **AND-02: Add the paired HTTPS Mac project service** — Done when: Share the desktop bridge, group projects once per canonical folder, authenticate/pin devices, revoke credentials and preserve stable asynchronous operation receipts.
- [x] **AND-03: Build the Android project dashboard and discussion** — Done when: Show unknown/count progress, activity, source coverage and freshness; retain project context, drafts, explicit actions and cached offline progress on the older WebView.
- [x] **AND-04: Add local push-to-talk transcription** — Done when: Record only after Start with Stop/Cancel and a 60-second cap; use a separately installed small multilingual whisper.cpp model, clean temporary audio and require editable transcript review.
- [x] **AND-05: Verify private comments and explicit Codex work** — Done when: Save comments without execution; confirm connected/new-chat work, preserve duplicate clarification, exact identities and failed/uncertain delivery without automatic replay.
- [ ] **AND-06: Package and install the Android release** — Done when: Install the signed release with debugging disabled, preserve the calendar, and verify a real progress question, comment and explicit task.
- [ ] **AND-07: Complete calendar and Mac field validation** — Done when: Complete normal Mac startup file-access setup and real sleep/wake, Wi-Fi roaming, power-cycle, multilingual and far-field microphone checks; record limits without claiming a speech accuracy score.
- [x] **AND-08: Offer the three approved Android home designs** — Done when: Settings selects or cycles Companion canvas, Sidekick studio and Bubble lounge; design, colours and primary project choices persist; unknown progress and project drafts remain intact; the signed update installs and layout switching is verified on the calendar.
- [x] **AND-09: Provide easy calendar access over WLAN** — Done when: Install the signed update over WLAN without clearing pairing; provide a quiet Open Motchi notification button, Easy access settings and conditional home-screen shortcut support; verify the button opens the dashboard with the Mac connected.

- [ ] **AND-10: Add optional local wake-name listening** — Done when: An explicit opt-in listens locally for Motchi, shows microphone state and provides pause/disable controls; false activations, project routing, privacy, battery and real calendar microphone behaviour are verified. Push-to-talk remains available.
- [x] **AND-11: Match the pictured dark calendar design** — Done when: The installed app uses the dark Companion canvas, serif speech bubble, compact composer, larger progress circles and stacked Primary/Secondary sections; previous appearance is restorable, all three designs remain selectable, and project pins, pairing and discussions survive the update.


- [ ] **AND-12: Add and validate Doubao speech recognition** — Done when: Official two-pass Doubao ASR is selectable with private Mac API setup, ambient wake detection stays local, corrected transcripts reach the right project, and real English/Chinese speech, pause timing and answer delivery are verified on the calendar.

- [x] **AND-13: Add free local bilingual speech recognition** — Done when: Install selectable Qwen3-ASR on the Mac without speech API credentials, validate English/Chinese synthetic transcription, and use a local streaming keyword detector to activate questions; record real speech acceptance separately under AND-10.
- [x] **UI-01: Show discussion in the main animated character section** — Done when: Render typed and voiced replies with question, scope and source coverage beside the character across the three retained layouts, keep that section on project pages, and verify the installed calendar reply without an automatic communication popup.

AND-12 partial verification: source/protocol/privacy tests, signed 0.16 APK installation and the updated Mac companion pass. The user has the consumer Doubao app only; a Volcengine Speech API key and real speech test remain required. See [setup and limits](docs/DOUBAO_SPEECH.md).

AND-06 rollout: the signed release and live flows are installed/verified. The calendar's userdebug firmware forces WebView inspection on despite the app requesting it off, so the debugging criterion remains open. See the rollout record before treating this device as a hardened release target.

AND-07 partial verification: after user-approved file access, a normal unlocked Mac restart reconnected the calendar and answered a live progress question. Locked startup/login, sleep/wake, roaming, power cycling and real multilingual/far-field speech remain unverified.

## Character customization — requested 2026-10-25

This requirement supersedes dog-only presentation. The proposed build sequence is in [next milestone](docs/NEXT_MILESTONE.md); the initial character roster remains to be decided.

- [ ] **CHAR-01: Separate character assets from project behavior** — Done when: A character registry supplies each character's identity, transparent artwork and supported animation states; the existing dog remains the default; project, checklist and approval behavior share one unchanged controller.
- [ ] **CHAR-02: Add a persistent character picker** — Done when: Users can preview and select bundled characters, the selection survives restart, and switching preserves the selected project, drafts, checklist and pending requests; invalid selections fall back to the default.
- [ ] **CHAR-03: Verify animation and interaction across characters** — Done when: Every bundled character supports entrance, idle, waiting, celebration and dismissal, follows Reduce Motion, stays transparent and uses the existing top-right placement and announcement timing without disrupting replies.

## P1 — Trustworthy project understanding

- [ ] **MEM-01: Remember user preferences** — Done when: Persist language, explanation length, notification preferences and desired initiative; explicit settings take precedence over inferred preferences.
- [ ] **MEM-02: Remember project goals and completion criteria** — Done when: Persist audience, goal, milestone, priorities, constraints and an agreed definition of done separately for each project.
- [ ] **MEM-03: Remember project decisions and their reasons** — Done when: Record accepted, rejected, deferred and superseded decisions with sources; retrieve the current decision without resurrecting an abandoned approach.
- [ ] **MEM-04: Let users inspect and correct memory** — Done when: Provide conversational and visible controls to review, edit, forget and scope memories; changes survive restart and remain isolated by project.
- [ ] **CHK-01: Classify instructions, ideas and open decisions** — Done when: Explicit work becomes committed tasks; maybe-statements become ideas; questions become decisions; quoted and rejected suggestions do not become commitments.
- [ ] **CHK-02: Reconcile replacements, deferrals, bugs and reopened work** — Done when: Handle changed requirements and regressions without losing task identity or history; deferred and superseded work is outside the active milestone denominator.
- [ ] **CHK-03: Resolve semantic overlap with expand, replace or separate** — Done when: Clear duplicates reuse task IDs; overlap is classified automatically as expand, replace, keep separate or skip, with reviewable reasons and persistent corrections.
- [x] **CHK-05: Match tasks and check off completion automatically** — Done when: Compare conversation outcomes to existing tasks without same/different questions, retain distinct scope and match reasons, prioritize recent completion evidence without skipping older history, protect manual corrections, and deliver a signed Android update with review status and Undo.
- [x] **CHK-04: Explain automatic checklist changes and support Undo** — Done when: Show the source conversation and reason for every automatic task change; preserve manual corrections and allow reversible changes.
- [x] **SYNC-01: Process conversation changes incrementally** — Done when: Persist event cursors and compact task/decision history; handle restart, repeated events and partial history without duplicates; show freshness, coverage and sync failures.
- [ ] **PRG-01: Track milestone scope and explain progress changes** — Done when: Show completed and total agreed tasks for a named milestone, preserve scope-change history, explain denominator changes and distinguish unknown from zero progress.
- [ ] **QA-01: Evaluate checklist accuracy and evidence quality** — Done when: Create representative conversation cases and track false additions, missed commitments, duplicates, correction frequency and unsupported completion claims.

## P2 — Natural project discussion and changes

- [ ] **CHAT-01: Route natural discussion to the right intent** — Done when: Distinguish status questions, brainstorming, new commitments, changed priorities and deferrals without requiring a mode picker; clarify ambiguous execution intent.
- [ ] **CHAT-02: Discuss the impact of proposed work** — Done when: Explain which milestone, dependencies and scope a proposed change affects before commitment; avoid inventing deadlines or effort estimates.
- [ ] **CHAT-03: Show checklist and instruction delivery outcomes** — Done when: Distinguish saved-only, sending, accepted, queued, failed and uncertain instructions; route to the exact connected chat/turn and never retry uncertain deliveries blindly.
- [ ] **CHAT-04: Keep project identity and connection capability visible** — Done when: Show the selected project beside the composer and its available actions; preserve topic during a discussion and ask when project references are ambiguous.
- [ ] **PRG-02: Separate implemented, verified and accepted completion** — Done when: Apply project-specific completion criteria, attach suitable evidence, reopen contradicted work and avoid equating a finished turn with a finished project.
- [ ] **CHAT-05: Give source-backed progress and blocker answers** — Done when: Answer what changed, what remains and what needs the user using recorded facts, source links, current milestone and last-update time; identify unavailable information.
- [ ] **QA-02: Verify project routing and instruction delivery** — Done when: Test multiple projects, active-turn races, disconnects, stale requests and failed/uncertain sends; measure wrong-project and lost-instruction incidents.

- [x] **CHAT-06: Analyze AI history for project and overview discussion** — Done when: Route named/topic questions, clarify ambiguity, support general and cross-project discussion, retrieve exact-project AI history and requirements before answers, expose bounded coverage, and verify a real read-only provider and calendar overview without silent work.

## P3 — Returning to work and managing multiple projects

- [ ] **RETURN-01: Provide a where-we-left-off summary** — Done when: On request, summarize completed work, current work, postponed scope and the next unresolved decision since the user last checked the project.
- [ ] **PROJECT-01: Group related chats under projects and releases** — Done when: Allow several chats per project with separate milestones/releases and user-correctable membership; retain source chat identities and avoid merging unrelated work.
- [ ] **ATTN-01: Create a cross-project attention inbox** — Done when: Collect unresolved questions, supported approvals, blockers and work ready for review; show what needs the user and keep dismissed items discoverable.
- [ ] **ATTN-02: Prioritize actionable blockers and dependencies** — Done when: Distinguish running, waiting for the user, blocked and ready for review from actual evidence; suggest the next useful action without treating inactivity as failure.
- [ ] **ATTN-03: Add quiet hours and selective notifications** — Done when: Support only-interrupt-when-I-need-to-act, project muting, batching and quiet hours; deduplicate notices, retain a history, and keep actionable requests available.
- [ ] **QA-03: Measure usefulness and interruption cost** — Done when: Measure time to understand project state, actionable decisions resolved, notification dismiss/mute rates and whether short notices remain recoverable.

## P4 — Deeper personalization and optional enhancements

- [ ] **PERS-01: Learn preferences cautiously with user control** — Done when: Suggest preferences from repeated corrections; show what was learned, allow rejection and reset, and never override explicit project instructions.
- [ ] **PERS-02: Customize character identity and conversational style** — Done when: Beyond the character picker, offer a name, temperament, concise/detailed tone and animation intensity while respecting Reduce Motion and keeping product states understandable.
- [ ] **PERS-03: Express meaningful states through character behavior** — Done when: Use consistent listening, working, waiting and celebrating behavior; preserve transparent top-right presentation and avoid decorative interruption loops.
- [ ] **PRG-03: Offer optional effort-weighted progress** — Done when: Keep equal task counts as a clear default; allow reviewed weights, avoid double-counting parent/subtasks and explain weighted progress separately.
- [ ] **PRG-04: Offer completion forecasts only with sufficient history** — Done when: Treat forecasting as optional, show its assumptions and uncertainty, account for scope changes and withhold dates when historical evidence is insufficient.

## Working example

> “How is the website doing? Also add tablet support.”

Motchi explains the current milestone and blocker, checks whether tablet support expands an existing layout task, updates the checklist using its automatic scope match, and reports whether the instruction reached the connected chat. Its answer exposes its sources and any uncertainty.

## Research

See [research sources](docs/RESEARCH.md). Research informs the design; the user-approved roadmap determines scope.


## Reliability milestone evidence — 2026-10-27

CHK-04 and SYNC-01 are implemented in source 0.12 and verified by the history-review regressions and isolated browser controls. See [review implementation and checks](docs/CHECKLIST_REVIEW.md). The installed app was not restarted. CHK-01, CHAT-05 and QA-01 have supporting improvements but remain unchecked: separate idea/decision storage, named milestone context and live model accuracy evaluation still need completion.

## Automatic checklist evidence — 2026-10-28

The user now prefers Motchi to decide same/different itself, superseding that question requirement in CHK-03. CHK-05 implements automatic same/different matching and evidence-backed completion. Broader expand/replace lifecycle handling in CHK-03 remains planned. See [0.14 checks and release limits](docs/AUTOMATIC_CHECKLISTS.md). The signed 0.14 APK is installed on the calendar over WLAN; Calendar Mirror confirms the connected dashboard with seven projects. A new task completion on-device remains unexercised.


## Bilingual voice and history discussion evidence — 2026-10-29

AND-13, CHAT-06 and UI-01 are verified in 0.17. The signed calendar and Mac updates are installed, a real all-project question displayed its source-backed answer in the main stage, and the user confirmed “It wakes and answers” after the streaming keyword detector replaced ambient full-ASR wake matching. Twenty Python suites, Android routing/appearance checks, Kotlin tests, lint and signing pass. Broader real bilingual accuracy, false activations, battery and field checks remain AND-10/AND-07; this is not proof of Doubao parity. Milestone/lifecycle/memory criteria in CHAT-05 and other broader tasks remain open. See [speech setup and verification](docs/QWEN_SPEECH.md), [discussion limits](docs/PROJECT_DISCUSSION.md) and [rollout](docs/ANDROID_VERIFICATION.md).
