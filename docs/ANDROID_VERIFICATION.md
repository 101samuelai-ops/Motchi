# Android rollout verification — 2026-10-27

Target: Allwinner 10A1 calendar, Android 11 / API 30, 32-bit ARM, 1280 × 800 physical panel. Its installed WebView is Chrome 83.0.4103.120. No Android speech-recognition or TTS service is available, so the app records locally and uses the Mac engine.

## Verified

- A minimal locally signed compatibility APK installed successfully through the existing authorized wireless ADB connection. Rendering, touch input, microphone start/stop, pinned HTTPS pairing and network requests worked before dashboard development. Installation required no restriction changes. The existing calendar was retained.
- Dashboard and project detail rendered on the actual device in portrait and landscape. Cards group local chats by canonical folder, use one shared checklist, retain unknown progress and rank input/active/recent projects. The discovered local catalog appeared after Mac file access became available.
- The software keyboard accepted a real progress question. Motchi returned a source-backed checklist answer from the Mac; no implementation request was sent.
- A timestamped rollout comment was saved through the calendar UI and appeared in its notebook after refresh. It did not create a Codex task.
- The tracked-only Send action displayed a visible confirmation for starting a connected chat in the same project. After explicit confirmation, the benign instruction asked Codex to reply with a verification phrase without editing files or running commands. The original created Codex chat returned **“Android integration verified.”** It then became idle. The app followed the returned chat identity.
- Push-to-talk displayed its indicator and elapsed time. Cancel stopped recording without submitting text. Stop sent a recording over the paired local connection, ran the Mac engine, and displayed an editable transcript. Ambiguous/unnamed text opened a seven-project choice list. Editing and choosing text did not automatically submit it.
- Runtime microphone denial displayed **“Microphone access denied. You can still type.”** Access was restored through the normal Android permission dialog; a subsequent recording and cancellation worked.
- The local whisper.cpp CPU/Accelerate engine and small multilingual model are installed outside Git. A clean synthesized question was transcribed exactly in 5.4 seconds. Its official OpenAI checkpoint matched the published SHA-256 before local GGML conversion. Temporary transcription files were removed.
- Stopping the idle Mac companion disconnected the app. The Android UI showed **Offline · cached** and retained seven project cards. After the desktop-session Mac launch, the signed release reconnected and showed seven live project cards, the saved comment and the connected test-chat identity. Reconnection checks receipts and does not replay instructions.
- The signed 0.13.0 release APK is installed. Android reports it as non-debuggable and its process has no WebView inspection socket. Release build and lint passed. Debug inspection was used only during device development; its ADB forwarding was removed. Automatic device rotation was restored. The existing calendar package remains installed. The Gradle distribution and locally downloaded build dependencies were checked before use. Private signing material stays outside Git.
- The actual Android native transport rejected a pairing ticket with the wrong certificate pin, preserving the existing paired connection and cached projects.

Compatibility fixes found on-device: Chrome 83 ignores CSS `inset`; dialogs now set top/right/bottom/left explicitly. Flex spacing has fallbacks. Incoming checklist questions live in a collapsed attention list so refreshes do not continually push the composer down. The folder checklist stays independently scrollable on larger screens.

## Automated checks

- 39 Android portal cases use an actual local HTTPS server and isolated project directories. They cover authentication, origin rejection, one-time/expired pairing, grouped counts, unknown progress, selection isolation, comments without execution, stable operation IDs, duplicate submissions, tracked-only work rejection, new-chat confirmation, unsupported remote approvals, result privacy, service ownership, checkbox validation, local WAV transcription/cleanup, quiet audio rejection, revocation during slow identity resolution, interrupted jobs and stalled file-access advice.
- 16 Android UI core cases cover possessive names, short project aliases, English/Chinese project references, ambiguity, duplicate names, unknown counts, offline freshness and operation identities.
- All 13 Python regression suites pass, including the portal suite; 19 native shortcut/placement/answer/announcement checks pass. Release Android lint passes; the deliberately pinned self-signed trust manager and bundled JavaScript require reviewed lint warnings rather than removing their security checks.

## Remaining field checks and limits

The actual calendar microphone picked up weak/ambient audio during one test and Whisper produced an unreliable transcript. The editable review step prevented submission. Quiet audio is now rejected before inference. Clean-file accuracy does not establish accuracy for conversational speech at a distance or in noise; multilingual and far-field usage still need testing with the user speaking to the calendar. This build makes no speech-quality score claim.

A normal Mac app launch while the Mac was locked waited while opening a project checklist. Launching in the development session restored access and the live flows above passed. The Mac must be unlocked once to complete any file-access prompt before relying on unattended startup. The Android UI keeps its cached data and now advises checking Mac file-access prompts if initial loading stalls. This is not evidence that every future Mac login/startup is verified.

Physical Mac sleep/wake, router roaming/address changes, long unattended operation and power-cycle recovery have not been forced during this coding session. Transport loss/restart, expiry, revocation and uncertain delivery have automated coverage; server shutdown has on-device coverage. Re-pair when the Mac address or certificate changes. No device restrictions, root access, calendar removal, launcher replacement or away-from-home endpoint were introduced.
