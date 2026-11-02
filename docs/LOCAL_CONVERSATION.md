# Local conversation controller — 0.18 Mac increment

2026-11-01. The user selected local speech rather than GPT-Live, then asked to implement and test on the Mac before updating the calendar. This increment changes turn handling; speaker tracking and echo-aware spoken interruption remain later work. AND-10 remains open.

## Behaviour

- Capture, measured input levels and the local keyword detector remain responsive during recognition and project analysis. A fresh wake or Listen now replaces a read-only question. Generation/revision checks reject stale captions, answers and delayed audio; provider cancellation stops the old answer process.
- Automatic completion first checks after **560 ms** of candidate silence, using local Smart Turn on up to the last eight seconds. An early score must reach 0.9; a tentative result gets another check after **1.2 seconds** at the existing 0.65 threshold. These scores are model outputs, not calibrated accuracy percentages. An unfinished prediction retains the whole question. Resumed speech invalidates both an endpoint prediction and its transcript confirmation.
- A third check after **2 seconds** handles hesitant scores of at least 0.4 only when the checked English/Chinese transcript contains an explicit complete question/request. Dangling clauses and incomplete endings still hold. Punctuation alone never qualifies. This bounded text heuristic addresses the measured longer-question misses; it is not a learned semantic detector or proof against early interruptions.
- Local recognition retains **2.4 seconds** of in-memory audio around a detected wake, so a joined “Hey Motchi, how is…” does not lose its beginning when keyword inference finishes late. Pause, context changes and replacement discard this buffer. The optional cloud recognizer never receives this pre-activation buffer.
- When microphone listening starts, the already installed Qwen and endpoint workers preload without microphone audio or downloads. A caption taken just after speech pauses is reused only when its activation and voiced revision exactly match the final candidate; new words require a new transcription. This avoids repeating recognition after the endpoint decision. Unclear speech does not disable the pause model; a fresh wake can retry a transient endpoint failure.
- A conservative transcript guard holds explicit dangling clauses such as “especially…” and “尤其是…”. It supplements the acoustic model; it is not a separate learned semantic model or a guarantee against every early cutoff. Manual **Finish question** bypasses the guard.
- An automatically completed question reuses its checked transcript through an internal function argument. HTTP JSON cannot supply this argument. Partial captions never request an answer or update the project checklist.
- The buffer has a **60-second** hard cap, followed by a bounded opportunity to Finish or restart. It never silently splits a question into multiple requests. Missing/failed pause detection requires explicit Finish; missing keyword setup requires Listen now.
- A wake permits one question. For an automatically ended question, speech starting within two seconds of processing is checked as a possible continuation. Meaningful words cancel the premature answer and restore the original audio plus the continuation. Acknowledgments/thinking sounds release the pending answer. This repair is limited to the already addressed question, ends before playback, and is not speaker identification. Manual Finish closes it explicitly. Later background speech does not start another question. A fresh wake can retain an unresolved project choice; pause/project changes clear it.
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

`check_local_conversation.py` covers fast/confident versus tentative endpoints, a second check without resumed speech, retained pauses, the buffer limit, unfinished phrases in both languages, wake-buffer privacy, exact-revision transcription reuse, expiry, live levels/wake during delayed work, late partial/final suppression, retained project choices, older-client compatibility, answer-before-TTS and discarded obsolete audio. `check_smart_turn.py` covers checksum rejection, bounded input, warm reuse, nonfinite results, cancellation/recovery and no endpoint audio files. Project discussion regressions verify cancellation before adding follow-up history.

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

## Live Mac browser preview

Run `python3 plugins/progress-pet/android/preview.py --live` from the repository with the installed Mac companion running. Open the printed loopback URL to use the bundled dashboard with real projects and read-only questions. Tap **Talk** for the Mac microphone, use **Finish question** if needed, or explicitly enable wake listening. Captions and answers appear in the main character section. Opening the page alone does not start capture. The default preview without `--live` still uses sample data.

The preview pairs a temporary local device with the authenticated HTTPS service. Pair credentials stay in Python; browser requests require the exact loopback host, origin and a per-process nonce. It blocks work submissions, comments, checklist edits and approvals. The installed background checklist analyzer continues independently. Normal preview shutdown stops its microphone session and revokes the temporary device. Keep the preview on this Mac; it is not a calendar pairing or public service.

Verified: 26 loopback HTTP/voice/permission-boundary checks, JavaScript syntax, six real project groups in the browser, a completed typed progress question and live Mac microphone controls. The test capture was paused afterwards. Real bilingual speaking and endpoint acceptance still need human testing; AND-10 remains open. No calendar update was installed.

## Response-timing follow-up

The user reports that pauses and recognition starts remain unreliable. The live preview showed surrounding conversation keeping an activated question open to the 60-second cap. The speech detector does not identify a primary speaker; do not describe the timing patch as speaker filtering or reliable suppression of nearby voices.

The changed controller uses the earlier conditional endpoint, local wake buffer, preloading and exact-caption reuse described above. The main character section now shows **Thinking** when the completed question reaches project analysis. Private diagnostic snapshots include stage timings without audio or transcript storage.

`evaluate_local_conversation.py --run --joined` additionally feeds paced, public synthetic English/Chinese wake-and-question phrases through the actual keyword detector, Qwen and controller. Both woke and submitted the complete question in this run, with exact trailing-caption reuse. Candidate VAD silence was 580 ms for English and 1220 ms for Chinese; warm ASR took about 321/372 ms and endpoint checks 47/55 ms. The answer was a local routing fixture, so this does **not** measure real answer-provider latency, human speech accuracy or speaker discrimination. The original four synthetic endpoint fixtures still pass; cold ASR took roughly 2.5–2.9 seconds versus approximately 0.2–0.6 seconds warm.

The three updated Mac modules are installed with a local app backup and verified signing. Desktop control reports the Mac locked, so restart and live preview verification of this patch await unlocking. The calendar and its staged APK are not updated. AND-10 remains open.

On 2026-11-02 the user unlocked the Mac and allowed its Documents prompt. The installed app/project service restarted and the browser reconnected with six project groups. Installed source matches the committed voice patch. Startup inspection found a synchronous native receipt-file read waiting for macOS access; consent cleared it. This does not fix future locked startup.

The live packaging check found Python rewriting bundled `.pyc` files after signing. `dog_bridge.py` now disables local bytecode writes before its imports and propagates that setting to speech child processes. The installed app was re-signed and the service restarted; its seal remained valid after the real speech workers loaded. Seventeen hub and 43 conversation checks pass.

The calendar kept ownership of the microphone. Separate preview/diagnostic clients were correctly refused and their temporary access revoked. The user chose to finish without switching the microphone, so the calendar session remains intact and the preview is paused. No fresh human speech/latency measurement was made. No calendar APK was installed; AND-10 stays open.

## Locally paused microphone and isolated test — 2026-11-02

The user subsequently requested stopping all Motchi recording and performing an exclusive Mac test. A private, owner-only `microphone-policy.json` now blocks paired clients from restarting Mac capture or submitting speech for recognition. Capture, publication and the watchdog enforce it, including late answers. Project discovery and typed discussion remain available. Invalid local policy fails closed. This controls Motchi's Mac helper and backend speech processing; it does not claim to disable other applications' microphones or a disconnected Android device's physical recorder.

`microphone_policy.py --pause` persists the stop. Explicit local `--resume` restores the existing paired controls. For a bounded test, `android/preview.py --live --voice-test` permits only its exact temporary paired device for at most five minutes from the first explicit listening action, retaining the global pause. Normal exit revokes that device and clears its exception; expiry stops capture and updates the preview to paused even if the browser keeps polling. Opening the page does not itself start recording or the exception timer. Test reports and credentials remain private and outside Git.

The extended synthetic check exposed two failures: longer completed questions received hesitant acoustic scores (0.44119 English / 0.49015 Chinese), and “progressing” could miss the progress-intent route when a project name was misheard. The third endpoint check and inflection routing correct these cases. Both paced English/Chinese fixtures now wait through an unfinished one-second pause, then submit exactly one complete question without Finish. Processing began about **2.85–2.92 seconds** after the final voiced frame, including the two-second fallback and recognition. Shorter joined questions measured about **0.76 seconds English / 1.51 seconds Chinese** in the earlier run. Fixture answers are routing stubs, not real-provider latency or human acceptance.

A separate real read-only question explicitly scoped to Motchi returned a concise, source-backed answer in **12.39 seconds**. An earlier unscoped synthetic question timed out at about 51 seconds and returned an unavailable-summary result; no successful answer is claimed for that attempt. Project analysis is additional latency after endpoint detection. No calendar update, cloud ASR or speaker identification was added.

The live retry exposed an audio-startup problem: the helper could remain alive on a main-thread authorization semaphore without delivering PCM. It now services the run loop during a bounded authorization wait. The controller reports waiting rather than listening until PCM arrives, and stops a missing/stalled stream. The installed signed helper subsequently delivered a changing meter; a real Chinese greeting/answer appeared in the main section. That is not a verified spoken progress answer. The user still reported sound without visible words and slow understanding, so human acceptance remains failed/pending.

The checked final transcript now reaches protocol-2 clients immediately at processing, before the project answer. Chinese wake-only greetings tolerate ASR-inserted punctuation and respond locally. Both are regression-verified and installed on the Mac; the updated bundled page is used by the preview, not installed on the calendar. Live speaker-loop attempts made while macOS output was muted cannot establish recognition or endpoint success. System Settings showed the physical input selected at roughly 25%; its volume control could be read but not operated by desktop control. The user was asked to adjust input/output before a further live test. Keep these observations separate from the passing synthetic cases.

After the user raised input and unmuted the speakers, the real microphone recognized a public spoken progress question, with “Motchi” transcribed as “Machi.” This exposed a routing problem: topic overlap could override an already selected project's follow-up. Explicit project progress follow-ups now retain that selection; named project switches still work. No guessed proper-name replacement was added.

Discussion requests now select relevant, unfinished and recent task details within a character budget, with a maximum of 64, and reduce selected-history input size. Full checklist counts and the full history reconciliation pipeline are unchanged; omitted task details are disclosed. A real read-only exact-project answer then completed in 20.19 seconds. This is one measured request, not a guaranteed response-time improvement.

The final Mac-speaker-to-physical-microphone test recognized **“What still needs attention in this project?”** and automatically returned a real Motchi project answer in the main character section without Finish. The transcript was visible during Thinking. Its last detected voiced frame to processing measured **1,292 ms**, local recognition **672 ms**, and the answer phase **30,404 ms** (about **31.7 seconds** from the last detected voiced frame). Earlier unclear segments/retries are outside that final-voiced-frame metric; it is not total recording duration or human pause timing. This remains too slow for instant conversation. These are public synthetic speaker-loop observations, not human bilingual accuracy or main-speaker acceptance. The answer describes the history available when requested, including the preceding failed test.

Recording was stopped, its scoped exception removed, and the private local policy returned to `paused: true`. The preview displays **Mac microphone paused**; no Motchi microphone helper remains. Speaker mute was restored after testing; the user's raised input level was retained. The calendar APK remains unchanged.

Targeted checks pass: 54 conversation, 22 Mac microphone, 16 local pause, 30 preview, 32 wake/privacy, 41 discussion, 42 portal, 17 paired wake and 17 hub cases, plus 26 Android core and 24 appearance checks. Swift compilation, JavaScript syntax and installed app signing pass. Broad human bilingual accuracy, main-speaker selection, echo-aware interruption and conversational latency acceptance remain open.


## Combined turn signals and repair — 2026-11-02

The two user-supplied articles recommend combining acoustic completion, grammatical completeness, conversational context, visible captions and recoverable interruptions. They are explanatory/product articles, not published evaluation datasets or source code. Their product latency claims are not Motchi measurements:

- [The interruption problem](https://www.eecommerceai.com/post/the-interruption-problem-how-voice-ai-learns-when-to-speak-and-when-to-listen) distinguishes premature interruption, delayed response, prosody, incomplete clauses and meaningful interruption versus acknowledgment.
- [Detecting interview questions](https://copilotinterview.com/blog/how-ai-detects-interview-questions) describes silence plus question/request shape, indirect requests, stacked questions, prior context, separate speaker streams, captions and manual recovery.

Applied changes:

- `turn_text()` combines inspectable English/Chinese grammar cues with Smart Turn. An unfinished “How would you scale…” or “Walk me through…” holds even when the acoustic model is very confident. Complete short questions (“Why that database?”), instructions and multipart questions qualify. Unknown statements need the patient acoustic threshold; punctuation is not completion evidence. These bounded rules are not a universal learned semantic parser.
- Low-score candidates still receive a caption. Resumed speech invalidates the old snapshot after recognition without killing/reloading Qwen. A genuine pause, revocation or replacement still cancels the worker. Fixed English/Chinese choices are now honored by Qwen; automatic bilingual mode remains available.
- Before an answer, a two-second same-question repair window checks new speech. It briefly withholds publication/history saving while deciding, cancels the old answer when meaningful continuation is recognized, and recombines the question. Pure “yeah”, “um” and “好的” do not become another question. Old text, audio and worker cleanup cannot overwrite the replacement. The window never enables unaddressed later follow-ups, remote actions or approvals.
- Spoken project answers request one or two sentences, at most 45 English words or 100 Chinese characters. They still review the exact project's history and validate quoted references. Voice input uses a smaller disclosed selection of task/history detail; full counts and checklist reconciliation are preserved. This reduces input/output, but does not guarantee provider latency.

Verified with the real installed local models on public synthetic speech: **11/11** selected sentence endpoint cases, with zero normalized token differences in these fixtures. Notably Smart Turn gave incomplete “How would you scale” a 0.98486 score and “Walk me through” 0.97855; the text guard correctly held both. This illustrates why acoustic confidence alone is insufficient; it is not a human accuracy score.

Paced joined English/Chinese questions returned one answer each, entering processing about **0.77/1.54 seconds** after the last detected voiced frame. English and Chinese unfinished one-second pauses were retained, with final processing about **2.52/2.55 seconds** after the last voiced frame. In the two repair fixtures, an initially complete question was followed by another clause after a 1.2-second pause: each cancelled its first speculative answer attempt, retained both clauses and emitted **one final answer**. Their answer provider was a delayed local fixture, not the real project model.

A separate exact-project request to the installed configured answer provider returned a valid concise assessment with three checked history references in **11.33 seconds**. This one request cannot establish a general latency improvement; it is still slower than natural conversation. No human speech result, main-speaker filtering, echo-aware voice interruption, full duplex or GPT-Live/Doubao equivalence is established. AND-10 remains open. The Mac modules are installed with a backup and verified app signing; no calendar APK rollout.

Reproduce without opening a microphone:

```sh
python3 plugins/progress-pet/tests/check_turn_recovery.py
python3 plugins/progress-pet/tests/evaluate_local_conversation.py --run --joined --pause-cases --conversation-cases
```

The first command checks race/privacy/control behavior with fixtures. The second explicitly uses already installed local speech models and temporary synthesized audio, deletes audio on exit, and fails if the selected scenarios fail. No raw test audio belongs in Git. Synthetic input exhaustion is a normal harness end, not a microphone failure.


### Human failure and capture diagnosis

The user then reported **words missing/no answer**, while speaking close to the MacBook. Keep this failed human acceptance above any synthetic success claim. At one inspection the microphone was receiving PCM but had no activation event: it was waiting for a keyword, not transcribing a question. A later explicitly activated segment returned no clear speech. These are distinct states; a moving meter alone does not prove an addressed question was recognized.

A separate bounded direct-microphone diagnostic bypassed wake and endpoint logic, retained audio only in memory/temporary recognizer files and removed it afterwards. Both installed Qwen and Whisper engines recognized repeated English/Chinese greetings. This establishes capture and basic transcription for those greetings, not accuracy on a project question. It also exposed an approximately **8.7-second delay before the first PCM** in that fresh helper launch (36.3 seconds of PCM received during a 45-second wall-clock window). This is one startup observation, not a fixed delay on every launch.

Corrections applied to the Mac/preview:

- Talk queues its activation until the first actual PCM frame. The character says **Preparing microphone**, then acknowledges **I'm listening** once capture is real; microphone initialization must not invite speech too early.
- The local keyword vocabulary now includes Hello/Hi Motchi and a Chinese pronunciation variant, matching greetings the direct diagnostic heard. Addressed-text handling includes the corresponding recognized name variants. Bare background mentions are not new keyword phrases.
- A short unrecognized name alone cannot automatically become a model question unless a project-choice answer is pending. This avoids a misheard wake name becoming an unrelated discussion. Finish still provides explicit recovery.
- When a local test expires, polling keeps it paused. An explicit Talk/Enable click can start another exact-device test capped at five minutes; polling and ordinary heartbeats cannot renew it. Other paired microphones remain blocked. The earlier frozen-test behavior and misleading restart instruction are fixed.

The user’s latest screenshot showed the paused state. Speaker identity is not implemented; it is not the cause of a paused recorder. Wake activation, audio readiness, ASR wording and answer latency must be assessed separately. Human project-question/wake acceptance remains open, and no calendar update was installed.

The final model evaluation also woke on two quiet synthetic greeting variants and rejected two unaddressed English/Chinese speech fixtures. These selected cases do not establish real-world wake accuracy or speaker filtering. The preview visibly transitions through Preparing before PCM readiness. After testing, global recording is paused with no temporary device exception and no microphone helper running; the preview stays open with **Mac microphone paused**.
