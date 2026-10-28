# Motchi Android companion

Version 0.13 adds a separate installed Android app for an Android 11 calendar. The existing calendar and launcher remain installed. The Mac performs project analysis, discussion and Codex execution; both devices must be on the same Wi-Fi. This is not an independent cloud execution client.

## Using the app

Version 0.13.1 adds **Settings → Appearance**. Choose **Companion canvas**, **Sidekick studio**, or **Bubble lounge**, or use **Previous design / Next design** to cycle through them. The choice is saved immediately on the calendar. Light/dark/device appearance, custom background and text colours, and rotating greetings are configurable there. Low-contrast text and status colours are adjusted for readability. **Use this design’s colours** restores the selected design’s palette.

The large Motchi and speech bubble sit beside a compact typing field and microphone action. **Primary projects** are your chosen focus; **Secondary projects** remain visible. Use **Pin / Primary** on a card to move it between sections. The first two discovered projects initially become primary; later refreshes preserve your choices. Needs-input items use amber, active projects blue, failures red, and completed checklists green. “Checklist complete” describes recorded scope, not shipping readiness. Project progress remains unknown when there is no checklist.

Changing the design does not reconnect, clear project conversations or drafts, or send instructions. Appearance preferences are stored separately from connection and project state. The voice waveform reflects microphone amplitude during an explicitly started recording. Wake-word listening remains a requested future addition; it is not active in this release.

Home groups discovered chats by their canonical project folder. It reads that folder’s shared checklist once, rather than adding together counts from its chats. Projects needing input appear first within their primary or secondary section. Missing or empty checklists show **Progress unknown**. Task counts describe recorded checklist scope, not effort, acceptance or shipping readiness.

Tap a project to discuss it. The selected project and exact chat stay visible. Checklists include source quotes, chat identities, history coverage, freshness and available Undo actions. The attention list holds Mac-only input alerts. A checkmark edit uses the current checklist revision; stale edits fail and require refresh.

- **Ask Motchi** discusses the selected project through the existing read-only answer provider. It does not start implementation.
- **Save comment** saves a timestamped private note for that project on the Mac. It sends no instruction to Codex.
- **Send to Codex** requires an explicit confirmation. Connected chats support instruction delivery with automatic task matching. Tracked-only chats offer to start a new connected chat in the same folder after confirmation. They never claim an instruction reached the original tracked chat.

Request receipts retain stable operation IDs. A lost response is uncertain until its receipt is checked. Reconnection and app restart check receipts; they never automatically replay a work instruction. An accepted request is not a claim that the project or task is finished.

Home voice questions match an explicitly named project. Multiple matches, duplicate names or an unnamed project open a choice list. Inside a project, follow-up text stays there. To switch projects, use All projects. A transcript opens an editable draft: choose Ask, Save comment or Send to Codex afterward.

## Opening Motchi on the calendar

Version 0.13.2 adds a quiet **Open Motchi** button in Android’s notification panel. Swipe down from the top of the calendar screen, then tap the Motchi notification or its **Open Motchi** action. This works with the calendar’s existing home-screen app. The button contains no project names or conversation text and does not record audio or run a background project service.

**Settings → Easy access** turns this button on or off. Where supported by the home-screen app, **Add Motchi to home screen** requests an Android shortcut; confirm Android’s Add prompt. Unsupported launchers explain the notification alternative. A requested shortcut is not reported as pinned until Android lists it as pinned.

The notification is restored after an app update and registered for normal device startup when enabled. The installed app remains available in Android’s app list. The launcher and calendar are retained. Live projects require the paired Mac to remain awake and on the same Wi-Fi; the button can open cached progress while the Mac is offline.

## Automatic checklist updates — 0.14

Android 0.14.1 aligns the calendar with the pictured dark Companion canvas. It retains the previous look for restoration, all three layouts and personal colours. See [appearance details](ANDROID_APPEARANCE.md) and [the full checklist audit](CHECKLIST_AUDIT.md).

Update both the Android APK and the Mac companion scripts. The Mac decides whether conversation requirements describe an existing task or a separate outcome. Equivalent work reuses the existing ID; different outcomes stay separate. Uncertain overlap is kept separate to preserve scope. Old similarity questions are reviewed automatically without sending any saved instructions.

Completed recorded plan steps check off their bound task on the next Mac observation. Assistant completion messages require model review and source evidence for the full task. Recent messages are reviewed ahead of older backlog when a project already has tasks; the older history still catches up independently. Android refreshes about every three seconds. This is automatic after review, not a zero-latency or guaranteed-perfect interpretation of every message. Manually corrected checkmarks remain protected.

Project details show automatic-review status, recent live review time, match decisions, evidence and Undo for applicable changes. An older Mac companion prompts for an update. Offline mode displays saved checkmarks. Same-Wi-Fi access, discovery limits and explicit work confirmation still apply.

For a local sample preview, run `python3 plugins/progress-pet/android/preview.py --apk /path/to/Motchi.apk` and open its printed loopback URL. **Try automatic completion** uses illustrative data only. This preview cannot inspect projects, send work or replace the paired app.

## Pairing and revocation

On the Mac, open Motchi’s dog menu and choose **Connect Android calendar…**. This opts into the LAN service and displays a one-time pairing ticket, valid for five minutes. Open Settings in the Android app and paste the complete ticket. Pair only with the ticket shown on your Mac.

The ticket contains the Mac’s private LAN endpoint, a random pairing secret and its SHA-256 certificate pin. HTTPS uses a separately generated private self-signed certificate and TLS 1.2 or newer. Android validates the exact certificate and its expiry, stores the device bearer token with Android Keystore encryption, and refuses redirects and non-local endpoints. Browser-origin requests and unauthenticated project requests are rejected. The preview server is never exposed.

The optional service binds to a local interface on port 47831. It shares the desktop’s exact bridge/controller and checklist state; it does not create a competing owner for managed chats. Its credentials, TLS key, device records, private comments and operation journal stay outside the source checkout in the user’s application-support folder. Credentials and keys must not be committed or shared.

The Android Settings action **Disconnect & erase cached data** revokes this device and clears its cache when connected. To revoke a lost or offline device, run these commands on the Mac, using the script in the installed app’s resources or the source checkout:

```sh
python3 plugins/progress-pet/skills/completion-pet/scripts/android_host.py --devices
python3 plugins/progress-pet/skills/completion-pet/scripts/android_host.py --revoke DEVICE_ID
```

Revocation blocks later requests and queued actions. A command already accepted by Codex is not undone by revocation. Generating a new pairing ticket invalidates an older unused ticket. A changed Mac address or certificate requires pairing again. Live host changes are not discovered automatically.

The CLI `--enable` opts in for the next desktop launch; `--pair` generates a new ticket for the configured running endpoint. Use the desktop menu for the normal setup. Do not run a second bridge against the same live task registry.

## Voice and privacy

Voice is push-to-talk, with a separate Start button, an indicator, Stop & transcribe, and Cancel. Each recording is limited to 60 seconds. Leaving the app cancels an active recording. Microphone denial leaves typing available.

Android records mono 16 kHz PCM audio. It travels only to the paired Mac over pinned HTTPS. The Mac runs `whisper.cpp` with the **small multilingual** model and automatic language detection. Temporary WAV and transcript files are removed after the local operation, including failures. Cancelling the transcript dialog never submits its text; a transcription already running on the Mac may finish before its temporary files are removed. Submitted text uses Motchi’s existing configured answer provider. There is no cloud audio transcription, wake word, background listening or text-to-speech dependency.

The speech executable and model are installed separately from source control. To configure an existing trusted `whisper-cli` build and multilingual GGML model, save a private `speech.json` beside the Android service state, containing absolute `binary` and `model` paths. A missing engine leaves typing available. Prefer building with an install RPATH of `@executable_path/../lib` on macOS so the installed CLI can locate its libraries.

Dependencies: [whisper.cpp](https://github.com/ggml-org/whisper.cpp), [Whisper small multilingual model](https://huggingface.co/ggerganov/whisper.cpp). The initial device rollout uses whisper.cpp v1.7.6 and an official OpenAI small checkpoint converted using its bundled converter. The source checkpoint was verified against OpenAI’s published SHA-256 before conversion. Neither models nor build dependencies belong in Git.

## Building and installing

Prerequisites: JDK 17 or newer, Android SDK platform 35 and build tools 35.0.0, Python 3, and an authorized ADB connection. Set `JAVA_HOME` and `ANDROID_HOME` to those local installations. The Gradle wrapper pins Gradle 8.10.2 and its distribution SHA-256; Android Gradle Plugin is 8.7.3 and Kotlin is 2.0.21.

Build and verify the compatibility app before the full dashboard:

```sh
python3 plugins/progress-pet/android/build.py --create-key --compatibility --output /tmp/Motchi-compatibility.apk
adb install -r /tmp/Motchi-compatibility.apk
```

The compatibility screen checks rendering, touch, pairing, networking and microphone start/stop. If installation is blocked by manufacturer policy, report the policy; do not alter restrictions, root the device, replace its launcher or remove its calendar.

Then build the full app with the same signing key:

```sh
python3 plugins/progress-pet/android/build.py --output /tmp/Motchi.apk
adb install -r /tmp/Motchi.apk
```

`--create-key` creates private signing material only if missing. **Back up this key securely**: future APK updates must use it. `--signing-config` selects an external JSON containing `file` and `password`; Gradle receives these via environment variables. APKs, private keys, local SDK paths and caches are ignored. `--gradle` may select an existing verified Gradle installation if distribution downloads are unavailable.

The app has bundled assets, no remotely loaded web content, no cleartext networking and no arbitrary navigation. Release builds are non-debuggable and explicitly request WebView debugging off. This calendar's userdebug firmware overrides that WebView request, so inspection remains available through authorized ADB; see the rollout record. The Android shell handles Keystore storage, certificate pinning, microphone permission/recording and networking. The UI supports this device’s Chrome 83 WebView; notably, dialogs use explicit edges instead of unsupported CSS `inset`. Larger screen layouts place checklist and discussion alongside each other; portrait places discussion first.

## Offline behavior and boundaries

The last successful dashboard and project discussion stay readable from private device storage. Offline/stale badges and a visible message describe disconnection. Questions, transcription, comments and work require the awake Mac. Cached data is an observation, not a live promise. Initial Mac discovery runs asynchronously; it cannot hold an Android request open indefinitely.

This release has no remote approval decisions, wake word, launcher replacement, calendar removal, public/away-from-home endpoint or automatic replay of uncertain work. Permission decisions stay on the Mac. Project discovery remains limited to the existing supported local Codex catalog and available history. The broader memory/classification/character roadmap remains separate.

## Verification

Automated service checks exercise real HTTPS plus isolated project fixtures: authentication, one-time/expired pairing, origin rejection, single-checklist grouping, unknown progress, exact project routing, comments without execution, duplicate operations, tracked-only rejection, explicit new-chat confirmation, private receipts, service ownership, WAV constraints, local speech invocation and cleanup, revocation and restart uncertainty. UI core checks cover possessive names, ambiguity, duplicate names, unknown progress and offline freshness. Existing Python and native interaction regressions remain required.

See [Android rollout record](ANDROID_VERIFICATION.md) for actual device results and remaining hardware checks. Automated fixtures do not establish a model accuracy score or universal device compatibility.
