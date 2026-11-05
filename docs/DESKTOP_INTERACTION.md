# Desktop dog interaction and persistent listening

Updated 2026-11-05. This increment is installed on the Mac. Calendar installation remains deferred.

The user wants an animated dog, processing messages in its own speech bubble, wake-name activation of the existing double-right-click popup, and microphone capture throughout Motchi's running lifetime. The local preference is enabled on this Mac with the user's authorization. New installations remain opt-in.

## Behavior

- The installed companion maintains its microphone independently of browser polling. Closing the preview does not pause desktop listening. Quitting the companion closes capture.
- Explicit local Pause persists and blocks older paired clients from restarting Mac capture. Resume clears that local pause and claims the microphone when it is free. Existing active paired sessions are preserved during normal app startup.
- A failed microphone helper is retried with a bounded interval. Recovery preserves a paired session's project and language. macOS authorization, an unlocked session and an available input device are still required.
- Wake events call the same native `showReport()` path as double right-click. Follow-up questions do not replay the entrance. A final answer reopens a dismissed popup; pending questions and approvals keep their existing priority.
- Native and preview clients receive separate event queues. The native app owns playback for its local session and reports exact playback completion. The preview mirrors text without playing duplicate audio.
- Listening tilt, blink, tail movement, thinking motion, greeting bounce and speaking mouth movement follow actual conversation state. Reduce Motion disables decorative motion.
- First-person English/Chinese processing feedback rotates every four seconds inside the main speech bubble, then clears when the answer arrives. It does not enter saved answer history.

The local desktop control route still requires authentication and a connection originating on the Mac; paired LAN devices cannot use it to override the local pause policy. No microphone audio is written by the desktop controller, and it creates no network credential.

## Verification

Source checks pass: 20 desktop lifecycle/recovery/pause/event-isolation checks; 27 Mac voice, 30 follow-up, 56 local conversation, 48 preview, 16 microphone policy, 45 authenticated portal, 10 actual preview playback, 24 appearance, six native-caption UI and 21 Swift checks. Bilingual bubble-feedback cadence/cancellation checks, Python/JavaScript syntax and diff checks also pass.

The update is backed up, installed and signed under the existing app identity. After the user allowed microphone access, the installed service delivered fresh PCM with the local keyword detector ready. The final Resume check measured first PCM in 528 ms and an audio age of 53 ms; these are capture observations, not speech recognition or answer latency claims.

Live testing found and corrected two failures: a dead helper's retained owner prevented recovery, and an older calendar could restart capture after a local pause. After correction, two separate authenticated observations confirmed disabled capture following UI Pause. UI Resume restored live PCM. A real typed explanation displayed rotating first-person processing feedback and then its answer beside the dog, with the pending message hidden.

Capture remained active for 30 seconds with the preview server closed; four authenticated samples had fresh audio ages of 9–87 ms. Explicit activation reached the native top-right dialog, as recorded by its presentation log. The first human wake trial returned “No response,” and a bounded synthetic speaker-loop wake trial did not activate it; the later human retry confirmed that the popup appears, but reported no speech intake. Diagnostics confirmed fresh audio and recognition activity. Pending attention had suppressed native captions; this is corrected and installed, with a sound meter and Talk/Finish fallback controls. The user subsequently confirmed that both the native sound meter and recognized words appear. UI-02 is accepted for wake presentation and visible speech intake; this is not a new end-to-end answer-latency measurement. This increment does not establish speaker identification, full duplex, universal wake accuracy, Mac sleep/lock recovery or calendar voice acceptance. AND-10 and the broader PERS-03 acceptance criteria remain open.

## Development preview

With the configured Mac companion running, use `android/preview.py --live --desktop-voice --work-controls`. Preview credentials stay server-side and are revoked on normal close. The ordinary live/scoped-test preview retains its previous microphone lifecycle.

The failed human trial also prompted a native thread sample: repeated scans of an accumulating project snapshot occupied most UI-thread samples. JSON line framing now scans only each new chunk and decodes on a serial background queue. A fragmented 2 MB fixture plus the following voice event decoded in 94 ms, and a subsequent native thread sample no longer showed the scanning stall. This removes that measured UI bottleneck; it does not prove acoustic wake recognition.
