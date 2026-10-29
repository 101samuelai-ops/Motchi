# Doubao Speech setup — Motchi 0.16

Motchi supports the official Doubao streaming speech-recognition API, including its two-pass final correction. A Doubao chat-app account does **not** supply this API. You need a Volcengine account with streaming speech recognition enabled and an API key for that resource. No actual Doubao recognition or accuracy test has been performed on this installation yet.

## Set up on your Mac

1. Open the [Volcengine Speech API console](https://console.volcengine.com/speech/new/setting/apikeys?projectName=default). Create/sign in to your own account, enable streaming ASR and review its pricing/terms. Motchi does not purchase quota or create an account for you.
2. Obtain a Speech API key for your enabled resource. The new-console API key is preferred; legacy Speech App ID + Access Token are also supported. A consumer Doubao app login/token cannot be used here.
3. Run the private setup utility in a Mac terminal:

   ```sh
   python3 plugins/progress-pet/skills/completion-pet/scripts/configure_doubao.py
   ```

   This installation also provides **Set up Doubao.command** beside the built APK in the local ignored `outputs` directory. Double-click it to use the installed companion's utility.
4. Confirm cloud transcription locally, enter the key at its hidden prompt, and choose the matching resource. The default is **Doubao ASR 2.0 hours** (`volc.seedasr.sauc.duration`). Your account must have that resource enabled; selecting it does not enable or buy the service.
5. On the calendar, tap the round microphone beside **Mac connected**. Choose **Mac microphone**, **Doubao Speech · cloud**, then **Listen now**. Speak near the Mac. Pause when finished, or tap **Finish question**. The setup files reload automatically; a restart/re-pair is unnecessary.

Do not paste your key into a project chat, commit it or include it in a screenshot. The utility saves it in a private file in the Mac user's application-support directory with mode `0600`. Android receives only provider readiness and sanitized errors. To check status without revealing the key:

```sh
python3 plugins/progress-pet/skills/completion-pet/scripts/configure_doubao.py --status
```

“Ready” means credentials/dependencies are configured; it does not prove the remote account accepts the key or has quota. The first live recording verifies that.

## Microphone and privacy

The calendar's own input has been nearly silent, so the selected fallback is the Mac's physical microphone. Stand near the Mac. The updated helper uses raw physical input; the previous native voice-processing mode suppressed its signal. Input level and speech quality need separate verification.

Wake-name detection stays **local** using Whisper. After a locally recognized wake name, an explicit **Listen now**, or a validated follow-up window, the addressed audio goes from the Mac to Doubao over verified WSS. Background audio is not continuously uploaded. A local false wake detection can still activate transcription; Pause stops capture and cancels queued questions. API usage can incur your Volcengine service charges.

Doubao supplies bilingual recognition, punctuation and corrected final text. Motchi sends only the audio and a small generic Motchi/Mochi/Codex vocabulary; project history and credentials are not part of the audio payload. The provider's own retention and billing policies apply. Motchi keeps no ambient audio archive and cleans temporary local audio/transcription files. Submitted text uses your existing configured answer provider.

Interim text arrives in bounded recognition updates, not guaranteed instantaneous word-by-word streaming. Preview text does not enter project chat or trigger answers. Only an addressed final question calls the read-only answer provider. Voice cannot submit implementation work or approve permissions.

## Problems and fallback

- **API setup needed:** run the Mac setup utility. Selecting Doubao on Android cannot create a key.
- **Access rejected / quota error:** check the key, enabled streaming ASR resource and quota in Volcengine. Motchi never echoes provider error bodies or credentials.
- **Very quiet input:** select Mac microphone, check its normal macOS permission and speak near the computer. Software gain cannot create missing microphone signal.
- **Question does not finish:** tap Finish question. Natural end detection uses the local WebRTC speech detector; a slower pause may split a sentence. Verify actual speech before trusting this hands-free.
- **Want local-only:** choose **Whisper · local Mac** in the live panel, or run setup with `--local`. Local recognition retains its existing quality limitations. Doubao errors do not silently switch providers.

## Implementation evidence and limits

The adapter follows the [official streaming ASR protocol](https://www.volcengine.com/docs/6561/1354869), using the optimized `bigmodel_async` endpoint, 200 ms PCM packets, two-pass recognition and corrected final results. The two-pass endpoint selects language automatically; it does not accept a forced English/Chinese parameter. Credential fields, response parsing and cloud-activation boundaries have deterministic test coverage. These checks are not a measurement of real recognition quality.

Before accepting this feature, test multiple real English and Chinese questions, names, short pauses and background noise; compare the final transcript with what was said and verify a project answer. Wake reliability, pause timing, answer delivery and AND-10/AND-12 remain open until actual user speech succeeds.
