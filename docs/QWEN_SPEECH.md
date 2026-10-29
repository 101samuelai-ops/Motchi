# Free bilingual speech recognition — 0.17

Motchi supports **Qwen3-ASR through MLX-Audio**, running locally on an Apple Silicon Mac. This is a speech engine integration, rather than a prompt-only skill: a skill by itself cannot improve the microphone signal or recognition model.

## Choice and evidence

| Option | English / Chinese | Practical tradeoff |
| --- | --- | --- |
| [Qwen3-ASR](https://github.com/QwenLM/Qwen3-ASR) | Both; publisher lists 30 languages and 22 Chinese dialects | Apache-2.0; 0.6B and 1.7B models. The publisher reports competitive multilingual results for 1.7B. Those results do not establish parity with Doubao on this device. |
| [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx) | Bilingual local wake phrases | Apache-2.0; a small CPU streaming keyword model activates Qwen without running full ASR on background speech. |
| [MLX-Audio](https://github.com/Blaizzy/mlx-audio) | Runs the Qwen recognizer | MIT runtime optimized for Apple Silicon. Selected here to avoid a server or paid speech API. |
| [FireRedASR](https://github.com/FireRedTeam/FireRedASR) | Chinese and English | Apache-2.0 alternative worth a later recorded-speech comparison; not installed or benchmarked here. |
| [whisper.cpp](https://github.com/ggml-org/whisper.cpp) | Multilingual models | Existing fallback. The user's previous microphone test was inaccurate; that does not establish the relative quality of every Whisper model. |

The current M2 Mac has 8 GB RAM. This installation uses the smaller **Qwen3-ASR-0.6B 8-bit** model for responsiveness while Codex is running. A larger 1.7B comparison is a future option, not an automatic model upgrade. No subscription, speech API key or per-minute API fee is required. Hardware, electricity and model downloads still use local resources.

Setup downloads the public [MLX model](https://huggingface.co/mlx-community/Qwen3-ASR-0.6B-8bit) at revision `89e96d92ba34aca20b3e29fb10cc284097d1219f` and `mlx-audio[stt]==0.6.3` from PyPI. Native certificate validation uses `truststore==0.10.5`. Model files, dependencies and private configuration remain outside Git.

## Setup

On an Apple Silicon Mac with Python 3.12, run from the repository:

```sh
python3 plugins/progress-pet/skills/completion-pet/scripts/configure_qwen.py --install
python3 plugins/progress-pet/skills/completion-pet/scripts/configure_wake.py --install
```

For an already configured installation, use `--select`. Calendar microphone settings offer **Qwen3-ASR · free local Mac**, **Whisper · local Mac**, and optional **Doubao Speech · cloud**. Qwen detects English/Chinese automatically; its language selector is disabled. A consumer Doubao app login is not Speech API access.

## Listening behaviour

With Mac wake listening enabled, the small streaming keyword detector runs locally. It recognizes “Hey Motchi” and “你好莫奇” without sending ambient speech through full ASR. Qwen transcribes the question after activation. Without the optional detector setup, the older ASR-based wake matcher remains a fallback. Motchi answers only an utterance beginning with its wake name or an explicitly tapped Talk/Listen now activation. A bare “Hey Motchi” acknowledges once and allows one next question for 20 seconds. After a final answer, the question window closes: say the name or tap again. Merely discussing a project near the microphone must not request an answer. Phrase-based detection can still misrecognize speech; use Pause whenever desired.

The calendar's built-in input remains near-silent/unconfirmed. Speak near the **Mac microphone**, the saved fallback source. Voice activity detection and Finish question control the end of the utterance; Qwen improves transcription but cannot repair unusable hardware input. Recognition updates are short chunks, not guaranteed word-by-word streaming.

Audio is sent only between the paired calendar and Mac when needed, and never to a cloud speech service with Qwen selected. The worker disables model-network downloads during recognition, keeps one model warm, uses private temporary WAV files and removes them on success, error or cancellation. Submitted final text and retrieved project history use the existing configured answer provider. Voice discussion cannot send Codex work or grant permissions.

## Verification boundary

Actual local synthetic English and Chinese sentences transcribed successfully. English: “Hey Motchi, how is the project dashboard progressing?” became “Hey Mochi, how is the project dashboard progressing?”; the wake matcher accepts both spellings. Chinese: “你好，莫奇，请告诉我所有项目的进度。” was transcribed as supplied. Warm recognition was about 0.29 seconds for that short English sample, excluding speech capture and answer generation. Cold load plus recognition was about 5–11 seconds in these runs.

These are synthesized samples, not an accuracy score for a person's voice. Human English/Chinese accuracy, accents, mixed language, false activations and end timing remain acceptance checks under AND-10. There is no verified Doubao-equivalence claim.

## Streaming wake correction and human check

The initial ASR-based wake path failed the user's 0.17 test: a moving meter did not produce a response. Background utterance recognition could keep the full engine busy while the call was missed. The corrected Mac path uses `sherpa-onnx==2.0.1` with the official bilingual 3M keyword model from [the sherpa-onnx release](https://github.com/k2-fsa/sherpa-onnx/releases/tag/kws-models). The installer verifies archive SHA-256 `68447f4fbc67e70eee3a93961f36e81e98f47aef73ce7e7ca00885c6cd3616a6`, extracts only fixed model data files, and keeps them outside Git. The runtime uses the int8 encoder/joiner, float decoder and two CPU threads. [Official model documentation](https://k2-fsa.github.io/sherpa/onnx/kws/pretrained_models/index.html) explains custom English phonemes and Chinese pinyin keywords.

Actual real-time PCM tests detected the English and Chinese synthetic wake phrases and did not activate on the corresponding non-wake speech. Mac regressions verify no full ASR submission during idle keyword listening, immediate wake acknowledgement, activated-only recognition and expiry back to keyword listening. The updated signed companion is installed, and Calendar Mirror shows “Listening for Hey Motchi · local keyword detector.” The user then confirmed **“It wakes and answers.”** This establishes a successful human wake/answer check, not a measured bilingual accuracy score or long-term false-positive rate. Broader AND-10 checks remain open.
