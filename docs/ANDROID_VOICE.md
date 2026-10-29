# Voice on the Android calendar — 0.17.0

## Current hardware finding

Android enumerates a built-in microphone and grants capture access, but its stream is almost silent. The user confirmed that the recording meter did not respond to speech. Enumeration and a running service do not prove a working physical microphone. No firmware, restrictions or microphone permissions were bypassed.

The user chose the Mac microphone as the current fallback. The updated Android app defaults to **Mac microphone** unless a source has been explicitly saved. The Mac stream and calendar meter moved during earlier checks. Native voice processing later suppressed the signal, so 0.16 uses raw physical input and requires a fresh signal check. The first human test still reported inaccurate transcription and unreliable end detection; it is not a successful voice acceptance test.

## Calendar controls

Tap the round microphone icon beside **Mac connected** to open the live voice panel. It shows input source, recognition provider, language and measured meter. Live text, waveform and answers appear in the main animated character section; a wake event does not open the settings panel.

- Select **Mac microphone** and speak near the computer, with both devices on the paired Wi-Fi connection. The Mac must stay awake. macOS may ask for microphone access; use its normal consent interface.
- Choose **Qwen3-ASR · free local Mac** for automatic English/Chinese recognition without an API key; see [setup and limits](QWEN_SPEECH.md). Optional **Doubao Speech · cloud** for the requested API integration; see [private setup and limits](DOUBAO_SPEECH.md). Until a Speech API key is configured, Motchi displays setup needed. A Doubao app login is insufficient. **Whisper · local Mac** remains an explicit fallback.
- With Whisper selected, select **English** or **中文** to avoid unstable language guesses from short audio. **Automatic** remains available for mixed language use. English is the initial default.
- **Listen now** enables listening and opens a 30-second explicitly addressed question window. A wake name is not required in that window.
- Otherwise say **Hey Motchi**, wait for acknowledgement, then ask one question within 20 seconds. Say the wake name or tap Talk again for the next question; the final answer closes its listening session. Motchi/Mochi and documented Chinese name aliases are recognized at the start, rather than anywhere in a conversation.
- **Finish question** flushes captured speech immediately. Natural end detection waits about 0.84 seconds without detected speech. Background noise alone should not keep a WebRTC-detected utterance open.
- **Pause microphone** stops listening; the persistent Android notification also has Pause. Closing the panel only hides it. A disabled preference stays disabled across app updates.

Speech-to-text appears in short recognition updates, not guaranteed word-by-word streaming. Doubao replaces interim text with its corrected final result. The Doubao two-pass endpoint handles English/Chinese automatically, so the local language selector is disabled for it. Temporary recognition files are cleaned after each operation. In-progress preview text never calls the answer provider or enters project chat history. The final addressed question uses the existing read-only provider. Project answers retain the exact chat identity; ambiguous names ask for a project. No voice command sends implementation work or approves permissions.

When using **Calendar microphone**, the original one-recording, editable transcript workflow remains available. Its near-silent hardware input is not fixed by software gain. Mac mode's Talk button opens Listen now instead of recording the calendar.

## Mac capture and dependencies

The bundled `MacMicrophone.swift` helper uses AVAudioEngine with the physical input, without the native voice-processing mode that suppressed the signal in an earlier check. It writes mono 16 kHz PCM only to its parent process. Audio is bounded to 20-second utterances. It is not saved as an ambient audio archive. With the optional streaming wake model configured, Mac wake detection uses a small sherpa-onnx keyword detector and invokes Qwen only after activation. The older ASR-based wake matcher remains a setup fallback; see QWEN_SPEECH.md. When Doubao is selected and configured, only addressed speech goes to its official API; ambient wake detection stays local and is discarded. Final addressed text uses the configured answer provider. Spoken output uses locally installed macOS voices and temporary audio that expires from the portal after two minutes.

The speech detector is the optional, separately installed `webrtcvad-wheels==2.0.14` package in the private Android service state's `speech-python` directory. This install uses its published macOS ARM wheel. Other installations without that dependency explicitly report **Sound-level fallback**. Doubao additionally uses `websockets==15.0.1`, separately installed in the same private dependency directory; setup credentials are never source controlled. The waveform uses measured PCM levels and is never simulated in the installed app.

The helper is compiled and included by `completion_pet.py --prepare-app`; the app includes `NSMicrophoneUsageDescription`. Do not commit binaries, dependencies, models, recordings or transcripts. Updating the installed scripts requires restarting the idle desktop companion normally, retaining pairing credentials.

Only one paired calendar can own the Mac microphone. Another device cannot read its transcript or stop its capture. A 25-second heartbeat lease and revocation watchdog stop capture on connection loss, including a stalled input pipe. Pause cancels pending question generations and terminates capture. Project changes cancel the old question session. Wi-Fi reconnection can resume a previously enabled service; it does not replay implementation instructions.

## Verification and remaining work

Automated checks cover wake matching, ambient privacy, local partial transcripts without provider calls, final question routing, bounded activation expiry and closing the session after a final answer, generation cancellation, paired HTTPS, operation idempotency, revocation and private spoken output. Mac tests cover microphone ownership, heartbeat expiry, contextual cancellation, speech segmentation, noisy pause detection and explicit finishing. Kotlin tests cover bounded PCM, silence/click rejection, weak input, waveform levels and gain.

The signed APK and local helper compile successfully. On-device checks established the Mac input source and moving meter; the initial human speech test failed accuracy and end detection. Version 0.15.2 added WebRTC detection, fixed local speech language and Finish question. Version 0.16 removes the unsuccessful native voice-processing mode and adds the requested official Doubao two-pass integration. The user only has the consumer Doubao app; live Doubao recognition is blocked until they configure Speech API access. Its human speech acceptance, false activation behaviour, multilingual/far-field performance, long-term battery and sleep/roaming checks must be recorded separately. AND-10 and AND-12 remain open until their criteria pass. No real Doubao API result or accuracy score is claimed. Synthetic speech tests are not a human accuracy score.

Version 0.17 replaces the initial unsuccessful full-ASR wake loop with a local bilingual streaming keyword detector on the Mac. A recognized “Hey Motchi” or “你好莫奇” acknowledges in the main dog section immediately, then Qwen transcribes the question. After installation the user confirmed “It wakes and answers.” The earlier failed wake test and remaining accuracy/false-activation limits are preserved in QWEN_SPEECH.md; AND-10 remains open for broader acceptance.
