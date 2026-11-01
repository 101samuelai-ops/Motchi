# Local conversation controller — 0.18 Mac increment

2026-11-01. The user selected local speech rather than GPT-Live, then asked to implement and test on the Mac before updating the calendar. This increment changes turn handling; speaker tracking and echo-aware spoken interruption remain later work. AND-10 remains open.

## Behaviour

- Capture, measured input levels and the local keyword detector remain responsive during recognition and project analysis. A fresh wake or Listen now replaces a read-only question. Generation/revision checks reject stale captions, answers and delayed audio; provider cancellation stops the old answer process.
- Automatic completion waits at least **1.2 seconds** of candidate silence, then runs local Smart Turn on up to the last eight seconds. An unfinished prediction retains the whole question. Resumed speech invalidates both an endpoint prediction and its transcript confirmation.
- A conservative transcript guard holds explicit dangling clauses such as “especially…” and “尤其是…”. It supplements the acoustic model; it is not a separate learned semantic model or a guarantee against every early cutoff. Manual **Finish question** bypasses the guard.
- An automatically completed question reuses its checked transcript through an internal function argument. HTTP JSON cannot supply this argument. Partial captions never request an answer or update the project checklist.
- The buffer has a **60-second** hard cap, followed by a bounded opportunity to Finish or restart. It never silently splits a question into multiple requests. Missing/failed pause detection requires explicit Finish; missing keyword setup requires Listen now.
- A wake permits one question. Ordinary background speech during analysis does not start another question. A fresh wake can retain an unresolved project choice, while pause/project changes clear it. This does not add unrestricted follow-ups.
- Protocol-2 clients receive visible text before optional speech synthesis, then a playback-only event. Older installed clients retain one combined answer/audio event. This compatibility path allows Mac rollout without installing the staged calendar APK.
- The staged new client’s Listen now explicitly stops playback. Voice interruption during speaker output remains disabled until reference-aware echo handling is measured on the actual microphone/speaker arrangement. Input level monitoring continues; this is not verified full duplex.

Exact-project retrieval, concise source-backed assessments, evidence-reviewed checklists, manual corrections, Undo and explicit work/approval controls remain in the existing backend. Speech guesses never authorize work or approval.

## Private setup

First configure the existing Qwen runtime, then run:

```sh
python3 plugins/progress-pet/skills/completion-pet/scripts/configure_smart_turn.py --install
```

The installer adds `onnxruntime==1.31.1` to the private Qwen environment and downloads the approximately 8.7 MB CPU checkpoint. Runtime RAM is larger than the weight file. The ONNX worker uses two CPU threads, an in-memory JSON-lines PCM pipe, offline feature extraction and no audio files. The existing ASR still uses short-lived private WAVs and removes them after recognition/cancellation. Model data, config and dependencies stay outside Git.

Source: [Smart Turn](https://github.com/pipecat-ai/smart-turn), BSD-2-Clause. Pinned model: [v3.2 CPU ONNX](https://huggingface.co/pipecat-ai/smart-turn-v3/tree/f766f81d3cfdf7737ac64aad813d91bbfd56bf93), revision `f766f81d3cfdf7737ac64aad813d91bbfd56bf93`; SHA-256 `2bb026316b14a660486a75b1733cd3fbab8c2fd0314dc9af7be49f8cca967e4f`. The runtime verifies the checksum before starting. A failed model/worker reports manual Finish rather than claiming working semantic completion.

## Verification

`check_local_conversation.py` covers one-second pauses, resumed speech, the buffer limit, unfinished phrases in both languages, expiry, live levels/wake during delayed work, late partial/final suppression, retained project choices, older-client compatibility, answer-before-TTS and discarded obsolete audio. `check_smart_turn.py` covers checksum rejection, bounded input, warm reuse, nonfinite results, cancellation/recovery and no endpoint audio files. Project discussion regressions verify cancellation before adding follow-up history.

The explicit `evaluate_local_conversation.py --run` smoke test uses locally synthesized public phrases, records no microphone audio and deletes its temporary WAVs. On this Mac:

| Fixture | Acoustic probability | Final controller decision |
| --- | ---: | --- |
| English complete question | 0.98704 | Finish |
| English ending “especially” | 0.90076 | Hold with transcript guard |
| Chinese complete question | 0.83947 | Finish |
| Chinese ending “尤其是” | 0.02701 | Hold |

The acoustic model alone got 3/4 fixture decisions right; adding the documented guard got 4/4. Qwen returned the four synthetic texts without normalized token differences. Warm endpoint calls took about 30–70 ms, with approximately 1.4–1.6 seconds for cold startup in these runs. ASR, the minimum silence and answer-provider time are additional latency. These four chosen samples are a smoke check, **not a human accuracy score or a representative evaluation set**.

The signed Android 0.18.0/versionCode 12 build, release lint and Kotlin tests pass. The APK is staged locally and has not been installed on the calendar. Human English/Chinese/mixed-language speech, speaker discrimination, same-person side conversations, overlap, echo, actual interruption and end-to-end latency remain acceptance work. The calendar microphone remains near-silent/unconfirmed; the Mac is the selected fallback.

All 22 Python regression suites pass, including 30 local-conversation and seven endpoint-process cases. The 19 native Mac interaction checks, 26 Android core checks, 24 appearance checks and APK/Mac signature verification also pass. Updated Mac modules are installed with a local backup and the existing app identity/pairing retained. Normal launch was requested; macOS reports the screen locked and the project service has not started yet. Live post-restart microphone/service verification awaits unlocking. Locked startup is not fixed by this increment.

After the user unlocked the Mac, the installed companion's authenticated HTTPS service resumed and loaded six project groups without a catalog issue. Installed module bytes match the committed source, Qwen remains selected, and Smart Turn configuration is available. A temporary paired diagnostic session confirmed a running AVAudioEngine capture, ready keyword detector and changing Mac microphone levels during a 30-second check (observed peak RMS about 151). The initial shorter check had returned zero input while starting; that was not treated as proof of working capture. The test microphone session was stopped and its temporary device access revoked. No calendar APK was installed. This verifies restart and microphone transport, not a person's transcription accuracy, endpoint behaviour or calendar reconnection. Locked startup remains unresolved.
