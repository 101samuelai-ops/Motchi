# Persistent Motchi project memory

Updated: 2026-10-28. This file is durable project memory for future development sessions; it does not implement a user-facing memory engine by itself.

## Product intent

The user wants Motchi to analyze each project's progress, discuss status, accept additional work through conversation, and continually recognize checklist commitments and completion evidence in available project conversations. The experience should reduce manual project management while making corrections easy.

## Agreed next work

The user approved converting the preceding product analysis into the progress checklist in `../ROADMAP.md`. Priorities: P1 trustworthy understanding; P2 natural discussion and delivery; P3 returning to work and multiple projects; P4 deeper personalization and optional weighting/forecasting. Saving this roadmap is not authorization to implement every item in this setup turn.

## Existing user preferences

- Automatic checklist decisions (2026-10-28): the user explicitly wants Motchi to decide same/different tasks itself and check off finished work as completion is reported. This supersedes the earlier preference to ask about duplicate scope. Version 0.14 matches by outcomes/acceptance, keeps distinct or uncertain scope separate, prioritizes recent updates ahead of historical backlog, and retains evidence, Undo and protected manual corrections. The Mac companion scripts are updated in place. The signed Android 0.14.0 APK subsequently installed in place over WLAN; package inspection confirms versionCode 4, and Calendar Mirror shows Mac connected with seven live projects. Pairing and the Open Motchi notification were retained. A new completion arriving on the device was not exercised in this installation check. Do not claim zero-latency completion, universal history access or perfect classification. See AUTOMATIC_CHECKLISTS.md.
- Easy calendar access (2026-10-27): the user wants Motchi installed through WLAN and an accessible button on the calendar. Signed Android 0.13.2 is installed in place, preserving pairing. A quiet ongoing notification provides **Open Motchi**; Settings → Easy access controls it and offers a home-screen shortcut only when the launcher supports pinning. The user confirmed: **“Yes—Motchi opens and Mac is connected.”** Notification restoration is implemented for app replacement and normal boot; physical reboot restoration and actual shortcut pinning were not tested. The calendar launcher remains installed.
- Approved Android layouts (2026-10-27): retain all three final designs—Companion canvas, Sidekick studio and Bubble lounge—and allow selection/cycling in Settings. Source and installed Android 0.13.1 implement this with saved local appearance, background/text colours, primary/secondary project pinning, larger Motchi, rotating speech bubbles, compact typing and a microphone-level waveform during push-to-talk. The user confirmed all three designs work on the calendar. Wake-word support remains requested but unimplemented; this update does not enable continuous recording. See AND-08 and the Android verification record.
- Latest Android design refinement (2026-10-27): keep projects visible at a glance with distinct status colours, and allow user-selected primary and secondary project sections. Enlarge Motchi, replace the oversized heading/talk button with a speech bubble cycling through predefined prompts, keep typing compact, retain the curved voice waveform, and offer background/text colour personalisation. The user now requests seamless wake-word activation when Motchi is called, superseding the earlier no-wake-word preference for future design; the installed 0.13 app still uses push-to-talk. Companion canvas, Sidekick studio and Bubble lounge are the final three proposed front-page layouts awaiting selection. Wake-word behaviour in these previews is simulated; continuous microphone capture is not implemented or enabled by this design work.
- Android front-page design exploration (2026-10-27): combine Conversation first with Project studio. Put Motchi on the left of the opening section and “What’s on your mind?”, typing and Talk to Motchi on the right. One tap changes the talk button into a curved waveform, with greater vertical amplitude when receiving speech. Show clear circular project progress; complete is green, error is red, and needs-input items must stand out. Blue for in-progress and amber for needs-input are proposed in the three new previews. Companion desk, Signal studio and Focus lounge are design alternatives, not an implemented Android update or a final selection. Preview voice is simulated and does not record audio.
- Interchangeable characters, requested on 2026-10-25, supersede the earlier dog-only preference. Keep the current anime dog as the default and preserve transparent space around the selected character. The initial additional character roster is still to be decided.
- Popups at the primary screen's top right; ground line, leap, landing, then chat; animated return on dismissal.
- Double right-click opens the companion; click outside dismisses it.
- Routine tracking/completion announcements last 1.5 seconds. Questions, approvals and returned answers remain available for reading and action.
- If dismissed while answering, return the answer at the top right.
- Follow the appropriate project automatically and preserve project-specific conversations and drafts.
- Supported real approvals should be answerable in Motchi, with a way to ask about the request first. Never fabricate an approval path for unsupported native cards.
- Launch Motchi automatically when Codex desktop opens. The installed login helper was verified on 2026-10-24.

## Product decisions

- Capture commitments, ideas and unresolved decisions separately. Brainstorming alone does not add committed scope.
- Preserve stable task identities; resolve overlap as expand, replace, separate or skip.
- Keep source evidence, manual corrections and an undoable change history.
- Explain progress through milestone scope, blockers and freshness; task counts are not precise effort estimates.
- Separate implemented, verified and accepted states when the project requires them.
- Observing and extracting tasks must not silently instruct Codex to execute them. Work delivery follows an explicit user instruction and reports actual transport status.
- Memory must be inspectable, correctable, forgettable and scoped. Do not infer sensitive personal traits as preferences.
- Use incremental observations and persistent task/decision records; do not imply complete history coverage when only recent local chats are available.
- Keep routine updates quiet and aggregate nonurgent changes. Maintain an inbox for dismissed actionable items.

## Current limits to preserve in explanations

The existing source already has local project discovery, recent-history checklist inference, similarity clarification, read-only answers and additional-work delivery to Motchi-owned chats. These are foundations, not proof that the new roadmap acceptance criteria pass. Arbitrary existing desktop chats cannot universally be steered. Native filesystem/network cards still need their native approval interface when no supported live reply route exists. Do not modify Codex hook trust or weaken approval rules.

## Repository and maintenance

Requested GitHub account: the authenticated `101samuelai-ops` account. Canonical repository: https://github.com/101samuelai-ops/Motchi (public, created by the user). On 2026-10-25 the user chose the product name Motchi and this repository in place of the earlier private mochi repository. Preserve the user-created initial commit. Future commits go to Motchi. The initial commit records the roadmap and memory; the next imports the source baseline. Preserve project scope and integration limits in future changes. Follow `../AGENTS.md`; update memory only with actual user decisions and verified results.

The local canonical repository folder is `Motchi/` in the parent workspace. Legacy protocol/storage identifiers are retained for compatibility; product/display branding is Motchi. The 29 roadmap items are future feature work, not completed by this repository setup.

## Character customization update — 2026-10-25

The user wants changeable Motchi characters and is deciding the next implementation milestone and development model. Character selection should change presentation without losing project memory, checklists, pending questions or approvals. Added CHAR-01 through CHAR-03 as planned work; these bring the roadmap to 32 items. `NEXT_MILESTONE.md` contains a recommended sequence, not a user-approved implementation commitment. Dog/cat/robot are possible starting choices, not an agreed roster. This update does not change the current model settings or implement character switching.


## Selected reliability milestone — 2026-10-27

The user chose reliable checklist updates based on AI chat history and better project-progress discussion as the implementation priority. Character customization stays planned. Source version 0.12 adds a private durable visible-history queue, project review checkpoints, bounded review from the beginning of available local logs, coverage/freshness, exact-quote evidence, and revision-checked Undo for automatic additions/completions. Structured user question answers retain their context. Progress answers expose remaining work, recorded pending inputs, recent evidence and history limitations. Manual corrections remain protected; inference never sends work.

Verified: 12 Python suites, including 25 history-review cases; 19 native interaction checks; isolated browser Undo and coverage checks. The optional live synthetic model evaluation could not initialize Codex's in-process client inside the development sandbox. Do not claim a model accuracy score. See `CHECKLIST_REVIEW.md` for details and limitations. CHK-04 and SYNC-01 are implemented/verified; broader classification, lifecycle, milestone-aware discussion and model-quality evaluation remain incomplete. The installed companion, trusted hook registration and auto-launch target have not been replaced or restarted by this update.


## Android calendar companion — 2026-10-27

The user approved an installed, separate Android app with a project dashboard and project discussion. The Mac stays responsible for project analysis and Codex execution on the same Wi-Fi. Home groups chats by canonical folder, counts one shared checklist, preserves unknown progress and prioritizes user input. Project discussion keeps the exact project/chat visible and separates Ask, Save comment and explicitly confirmed Send to Codex. Tracked-only chats require confirmation to start a connected chat in the same project. No automatic execution from observation, questions or saved comments.

Source 0.13 adds the bundled Kotlin/WebView Android shell, optional pinned HTTPS portal sharing the desktop bridge, revocable paired devices, private comments, durable asynchronous operations and no replay of uncertain sends. Voice uses push-to-talk, a 60-second maximum, local Mac whisper.cpp small multilingual transcription and editable text review. Audio never goes to a cloud transcription provider. The model and executable are private runtime dependencies, not source-controlled assets. Cached progress remains available when disconnected; live actions require the awake Mac.

Verified on an Android 11 Allwinner calendar: signed compatibility installation, Chrome 83 rendering, touch, microphone start/stop and networking before full UI; portrait/landscape dashboard, real progress answer, private comment and an explicitly confirmed connected Codex test that returned “Android integration verified.” Microphone denial/cancel, editable transcription, ambiguity choice, and a server-offline cached dashboard also passed. CSS dialog positioning was adapted for Chrome 83. See AND-01 through AND-07 and docs/ANDROID_VERIFICATION.md for rollout state.

The signed 0.13.0 release is installed and is non-debuggable; the calendar remains installed and automatic rotation was restored. After a desktop-session Mac launch it reconnected with seven live project cards, the saved comment and connected test chat retained. The real native transport rejected a wrong certificate pin. All 13 Python suites, the final 39-case portal suite, 16 Android core checks, 19 native checks and release lint passed. A delayed check corrected an early inspection claim: this calendar runs userdebug firmware, and its Chrome 83 WebView ignores the public disable-debugging API. The APK explicitly requests inspection off, but inspection remains available through authorized ADB. No device policy/firmware changes were made. AND-06 stays open for this hardening criterion, and AND-07 remains open for field validation.

After the user allowed the Mac file-access prompts, a normal unlocked LaunchServices restart loaded projects and reconnected the calendar. An explicitly submitted live progress question completed with a current checklist answer; the stale-data guard blocked an initial attempt during reconnection. No implementation instruction was sent or replayed. The one-time consent and unlocked normal-launch check now passes; this does not verify future locked startup or login.

Keep these limits explicit: a clean synthetic question transcribed accurately, but weak actual calendar microphone audio produced an unreliable transcript; quiet-input rejection and mandatory review do not establish far-field or multilingual accuracy. Physical Mac sleep/router roaming/power cycling and later locked startup/login were not forced in this session. No remote approval controls, wake word, public endpoint, calendar removal or launcher replacement were added. Character customization and broader checklist classification/memory remain separate roadmap work.
