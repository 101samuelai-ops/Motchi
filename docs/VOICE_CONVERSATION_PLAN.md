# Natural voice conversation — proposed next milestone

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

## Two implementation paths

| Path | Benefit | Limits / prerequisite |
| --- | --- | --- |
| Keep Qwen local; add a tested streaming recognizer or decoder, multilingual turn-completion model, separate controller and local TTS | No speech API key or metered speech service; retains local audio | More engineering and resource use on the 8 GB Mac; English/Chinese endpoint quality and latency must be measured on this microphone |
| Add GPT-Live as an opt-in conversation layer, using client delegation to the existing Motchi backend | Official design supports listening while speaking and backend work continuing during conversation | OpenAI project API access, network and paid session/backend usage; addressed audio goes to the service only after the user enables it; accuracy still needs testing |

Recommendation: prototype a small optional GPT-Live conversation path for comparison if the user accepts its API/cost/audio boundary. Keep the current local path available. Do not silently replace the free local provider, create a key, or start a billable session. If local-only is preferred, implement and benchmark the turn controller before replacing another ASR model.

## Acceptance checks

Use consented, temporary English, Chinese and mixed-language samples, including project names, hesitations, restarts and corrections. Measure transcription word/character errors, early cutoffs, missed turn ends, false wakes, final-word-to-first-reply delay, echo-triggered replies, interruptions and wrong-project routing. Include a one-second mid-sentence pause, a later correction while analysis runs, Mac/calendar disconnection and noisy/far-field input. Delete raw samples after the agreed test; never commit recordings or transcripts.

Compare candidate paths on the same samples. Set an explicit latency/error target after measuring the baseline. Do not claim GPT-Live or Doubao equivalence from an SDK integration or a single successful answer.

## Official sources checked

- [Getting started with GPT-Live](https://developers.openai.com/api/docs/guides/live): full-duplex conversation, independent backend/client delegation, server-held API key, duration billing and separate backend usage.
- [Voice activity detection](https://developers.openai.com/api/docs/guides/realtime-vad): silence-based server VAD versus semantic completion, configurable eagerness and interruption settings for supported Realtime sessions. This is Realtime guidance; it is not proof that the same settings apply to every GPT-Live session.

These describe public API behavior, not the internal implementation of the ChatGPT app's voice experience.
