# Natural voice conversation — implementation plan

2026-10-29. The user reports that recognition and pause timing remain unreliable despite the successful wake/answer check. AND-10 stays open. Version 0.17.1 changes answer synthesis and presentation; it does not implement this voice architecture or establish improved speech accuracy.

## Diagnosis of the current implementation

- `mac_voice.Segmenter` ends a segment after 42 quiet 20 ms frames: about 0.84 seconds. A thinking pause and the end of a question look the same to this rule. The segment is capped at 20 seconds.
- Qwen receives accumulated audio for recognition; live text is periodic partial re-recognition, not a continuously streaming decoder. A final segment triggers recognition, history review and answer generation in one request. `MacVoice.capture` discards captured frames while that final request is busy. This prevents conversational interruption and can lose a correction.
- The calendar has no installed TTS service. Current voice replies principally appear as text; a complete spoken conversation also needs streaming speech output, playback acknowledgements and echo control.
- The calendar microphone remains near-silent/unconfirmed. Mac input quality, distance, background noise and language mixing still need real recordings evaluated with user consent. An input meter and synthetic tests do not establish recognition accuracy.
- Each answer deliberately closes the activation window. The user's wake-only preference remains in force: do not enable unrestricted follow-up listening as a side effect of improving turn-taking.

## Recommended design

Keep a local wake detector. After the name or Talk button, show an explicit active conversation session in the main character section, with a visible End/Pause control and inactivity timeout. An optional continuing conversation should be an explicit user setting; default to one question per activation until the user chooses otherwise.

Separate the voice interface from project analysis. The conversation controller owns idle, listening, possible end, processing, speaking and interrupted states. The project backend owns routing, exact-project retrieval, evidence reconciliation and a compact assessment. Slow history work must not prevent the interface from hearing a correction. Cancel or supersede the old reply when its question changes, using turn IDs; never let an obsolete answer overwrite a newer question.

Use speech activity plus a turn-completion estimate. Silence is evidence, not a definitive command to reply. A short pause should retain buffered speech; an unfinished phrase should wait longer, with an explicit Finish question escape hatch. Resume listening when speech restarts. Do not treat an English/Chinese punctuation heuristic as a measured semantic turn model.

For interruptions, distinguish microphone input from speaker playback with acoustic echo cancellation and playback state. Stop or duck spoken output when the user interrupts; retain only what was actually played in conversation context. Explicit read-only questions may be corrected, while work submissions and approval decisions still require their separate controls. Do not interpret a recognition guess as authorization.

## Selected direction — 2026-10-30

The user declined GPT-Live and wants similar conversational behaviour in Motchi. Keep the existing local wake detector and Qwen recognition, and build a separate conversation controller. Do not add a GPT-Live dependency, configure API credentials or start a billable voice session. The earlier GPT-Live comparison below is research context, not the selected implementation.

Local speech processing does not mean the whole product works offline: submitted text and retrieved project history still use the existing configured answer provider. Live progress also requires the awake Mac and its paired calendar connection. This direction does not establish GPT-Live or Doubao quality equivalence.

## Proposed local implementation

### 1. Separate capture, turn management and project analysis

Refactor `mac_voice.py` so a slow recognition or discussion request does not discard microphone input. A bounded in-memory audio buffer and a conversation controller should own idle, listening, possible-end, processing, speaking and interrupted states. Separate worker queues should give capture/wake detection priority over partial recognition and history analysis. Stamp every event with session generation, turn identity and request revision; cancel or supersede obsolete read-only requests, and reject late captions, results and playback.

Preserve one question per activation. Continuing capture allows a correction during the active turn and an addressed interruption; it must not open unrestricted follow-up questions or turn ambient speech into a new backend request. Pause, revocation, disconnect and timeout clear the activation and pending audio.

### 2. Replace the fixed silence cutoff with a tested endpoint model

Prototype a direct ONNX adapter for [Smart Turn v3.2](https://github.com/pipecat-ai/smart-turn), alongside the existing speech activity detector. Its publisher lists Chinese and English among 23 supported languages, 16 kHz mono PCM input and an 8 MB int8 CPU model. That input matches the Mac capture format. The weight size is not the full runtime memory footprint, and publisher timing is not a benchmark on this Mac.

Run endpoint estimation after candidate silence using up to the last eight seconds of the current question, as documented upstream. If it predicts an unfinished turn, retain the full question buffer and keep listening. Speech resumption invalidates an in-flight endpoint decision. Keep explicit Finish question, a bounded maximum recording length and an understandable timeout. Missing-model/error behaviour should remain visible and fall back to the existing manual finish path, not silently claim semantic turn detection.

The endpoint model assesses completion; it does not improve transcription, identify the speaker or decide whether the person is addressing Motchi. Keep Qwen final recognition initially, coalesce partial work rather than queuing stale snapshots, and compare a streaming bilingual recognizer only if measured caption latency or transcription errors justify it. Download pinned/checksummed model data separately from source control during implementation; research has not installed the model.

### 3. Add session speaker tracking and addressed-speech checks

Evaluate a speaker-embedding model through the existing [sherpa-onnx runtime](https://k2-fsa.github.io/sherpa/onnx/speaker-identification/index.html). Select the actual checkpoint only after checking its license, runtime footprint and English/Chinese performance. Establish a temporary reference from sufficient clear activated speech; a short or mixed wake phrase alone is not a reliable reference. Keep it in memory for the active interaction, without persistent identity registration by default.

Combine match confidence with conversation context. A matching voice can still be addressing another person. Use the existing answer provider only for bounded, activated-text intent checks where needed; retain uncertain speech for clarification rather than silently rejecting a legitimate short answer or treating every utterance as a command. Speaker embeddings do not separate overlapping voices. Heavy overlap or weak reference audio should lead to a request to repeat, not a claim that background speech was removed.

### 4. Add speech output and controlled interruption

Start by hardening the existing Mac `spoken_wav` path and paired-calendar playback before adding another large model. Generate/play coherent short sentences, acknowledge actual playback and stop queued audio on an addressed interruption. Show captions and the response in the existing main character section across all three layouts. Local Kokoro is a candidate later voice-quality comparison, not an installed dependency or a selected voice.

Echo handling must be measured on the actual Mac-microphone/calendar-speaker arrangement. The previous native voice-processing path suppressed microphone input, so do not enable it blindly. Validate a reference-aware echo-cancellation path and input levels before claiming simultaneous listening/speaking; retain a visible manual interrupt or half-duplex fallback if necessary.

### 5. Keep verified project knowledge and actions in the backend

`voice_companion.py` and `project_discussion.py` remain responsible for exact-project routing, current checklist/history retrieval, source-backed assessments and uncertainty. Pass only completed, addressed questions to them. Do not add/check off tasks from partial captions, speaker scores or an assumed successful answer. Existing evidence-backed checklist reconciliation, manual corrections and Undo remain intact. Voice discussion stays read-only; work instructions and approvals retain their explicit supported controls.

## Delivery order

1. Controller, bounded continuous capture and Smart Turn benchmark; verify pauses, resumed speech, late results, cancellation and project isolation.
2. Temporary speaker reference plus addressed-speech classification; verify two speakers, same-speaker side conversations, short utterances, weak/overlapping audio and both languages.
3. Reliable sentence playback, captions and echo-aware interruption on the real calendar; verify what the user actually heard separately from backend completion.

These are proposed increments under the existing open AND-10 acceptance work. No voice feature or roadmap checkbox is completed by this plan update.

## Implementation progress — 2026-11-01

The first Mac increment is implemented: bounded continuous capture, live wake/meter during analysis, generation/revision cancellation, Smart Turn v3.2, a 1.2-second minimum thinking pause, transcript confirmation and a conservative unfinished-clause guard. Missing dependencies retain explicit Finish/Listen now controls. Protocol-2 text precedes optional TTS, with compatibility for the older installed calendar. See [implementation and measured limits](LOCAL_CONVERSATION.md).

The user explicitly requested Mac implementation/testing before a calendar update. The signed 0.18 APK is built and staged, not installed. Speaker reference/intent filtering and echo-aware voice interruption are still pending; microphone accuracy and natural turn timing need human tests. This does not complete AND-10 or establish GPT-Live/Doubao equivalence. Earlier diagnosis/research sections describe the baseline and selection process, not the current implemented status.

## Acceptance checks

Use consented, temporary English, Chinese and mixed-language samples, including project names, hesitations, restarts and corrections. Measure transcription word/character errors, early cutoffs, missed turn ends, false wakes, final-word-to-first-reply delay, echo-triggered replies, interruptions and wrong-project routing. Include a one-second mid-sentence pause, a later correction while analysis runs, Mac/calendar disconnection and noisy/far-field input. Delete raw samples after the agreed test; never commit recordings or transcripts.

Compare candidate paths on the same samples. Set an explicit latency/error target after measuring the baseline. Do not claim GPT-Live or Doubao equivalence from an SDK integration or a single successful answer.

## Open-source sources checked — 2026-10-30

- [Smart Turn repository](https://github.com/pipecat-ai/smart-turn): v3.2, BSD-2-Clause, Chinese/English support, local CPU inference, PCM input format and eight-second current-turn context. Model/runtime choice still needs a measured prototype.
- [sherpa-onnx speaker identification](https://k2-fsa.github.io/sherpa/onnx/speaker-identification/index.html): local speaker identification, published model releases and Python examples. This does not establish target-speaker extraction or robust same-person side-conversation detection.

## Earlier OpenAI comparison sources

- [Getting started with GPT-Live](https://developers.openai.com/api/docs/guides/live): full-duplex conversation, independent backend/client delegation, server-held API key, duration billing and separate backend usage.
- [Voice activity detection](https://developers.openai.com/api/docs/guides/realtime-vad): silence-based server VAD versus semantic completion, configurable eagerness and interruption settings for supported Realtime sessions. This is Realtime guidance; it is not proof that the same settings apply to every GPT-Live session.

These describe public API behavior, not the internal implementation of the ChatGPT app's voice experience.
