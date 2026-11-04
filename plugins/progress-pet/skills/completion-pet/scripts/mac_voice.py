"""Opt-in Mac microphone for one paired calendar, with an expiring heartbeat.

Only in-memory, bounded PCM is retained. A silent or disconnected calendar
cannot keep the Mac microphone on indefinitely. No work/approval actions.
"""
from array import array
from collections import deque
from concurrent.futures import ThreadPoolExecutor
import io
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
import uuid
import wave
import doubao_speech
from wake_detector import WakeDetector, configuration as wake_configuration
from smart_turn import Endpoint, configuration as turn_configuration
from voice_companion import turn_text, continues_question
import microphone_policy

ENDPOINT_QUIET_FRAMES = 28  # 560 ms; early completion needs stronger model confidence.
ENDPOINT_PATIENT_FRAMES = 60  # 1.2 s for less certain complete turns.
ENDPOINT_TEXT_FRAMES = 100  # 2 s; complete text can recover an uncertain acoustic score.
ENDPOINT_STATEMENT_FRAMES = 150  # 3 s; an addressed standalone statement can be a turn too.
WAKE_BUFFER_FRAMES = 120  # 2.4 s in memory, shared only after a local wake.
CONTINUATION_SECONDS = 2.0  # Repair the same question before its answer, not a follow-up lease.
FOLLOWUP_SECONDS = 20
PLAYBACK_TAIL_SECONDS = .18  # Legacy clients without an exact playback-end receipt.

class InputLevel:
    """Bounded input gain before VAD/wake detection, not only before ASR.

    The Mac fallback can deliver quiet, valid speech. Boosting only the final
    WAV is too late if VAD or the keyword detector discarded those words.
    Never attenuate loud input or amplify by more than eight times.
    """
    def __init__(self):
        self.rms = 0
        self.gain = 1
        self.envelope = 200

    def apply(self, frame):
        samples = array('h', frame)
        if sys.byteorder != 'little': samples.byteswap()
        self.rms = math.sqrt(sum(n*n for n in samples)/max(1,len(samples)))
        self.envelope = max(self.rms, self.envelope*.985)
        peak = max((abs(n) for n in samples), default=0)
        self.gain = max(1, min(8, 1600/max(200,self.envelope), 30000/max(1,peak)))
        amplified = array('h', (max(-32768,min(32767,round(n*self.gain))) for n in samples))
        if sys.byteorder != 'little': amplified.byteswap()
        return amplified.tobytes()

class Segmenter:
    def __init__(self, vad=None, automatic=True):
        self.vad = vad
        self.automatic = automatic
        self.noise = 25.0
        self.rms = 0.0
        self.reset()

    def reset(self):
        self.before, self.speech = deque(maxlen=15), None
        self.loud = self.voiced = self.quiet = 0
        self.version = 0
        self.full = False

    def push(self, frame, voiced=None):
        samples = array('h', frame)
        if sys.byteorder != 'little': samples.byteswap()
        self.rms = math.sqrt(sum(n*n for n in samples)/max(1, len(samples)))
        if voiced is None:
            voiced = self.vad.is_speech(frame,16000) if self.vad else self.rms >= max(35, self.noise*3)
        if self.speech is None:
            self.before.append(frame)
            if not voiced: self.noise = self.noise*.98 + self.rms*.02
            self.loud = self.loud+1 if voiced else 0
            if self.loud >= 3:
                self.speech = bytearray(b''.join(self.before)); self.before.clear()
                self.voiced, self.quiet = 3, 0
            return None
        limit = 640000 if self.automatic else 1920000
        if len(self.speech) < limit:
            self.speech.extend(frame[:limit-len(self.speech)])
        self.full = len(self.speech) >= limit
        if voiced:
            self.voiced += 1; self.quiet = 0; self.version += 1
        else: self.quiet += 1
        if not self.automatic:
            return None
        if self.quiet < 42 and len(self.speech) < 640000: return None
        data = bytes(self.speech[:640000]) if self.voiced >= 8 else None
        self.reset()
        return data

    def partial(self):
        return bytes(self.speech) if self.speech is not None and len(self.speech) >= 48000 else None

    def finish(self):
        data = bytes(self.speech) if self.speech is not None and self.voiced>=8 else None
        self.reset(); return data

    def endpoint_audio(self):
        if self.speech is None or self.voiced < 8 or self.quiet < ENDPOINT_QUIET_FRAMES:
            return None
        # Excess trailing silence cannot push meaningful speech out of the
        # endpoint model's eight-second context.
        end = len(self.speech) - max(0, self.quiet-30)*640
        return bytes(self.speech[max(0,end-256000):end])


def wav_bytes(pcm):
    samples = array('h', pcm)
    if sys.byteorder != 'little': samples.byteswap()
    rms = math.sqrt(sum(n*n for n in samples)/max(1, len(samples)))
    gain = max(1, min(30, 1600/max(1, rms)))
    boosted = array('h', (max(-32768, min(32767, int(n*gain))) for n in samples))
    if sys.byteorder != 'little': boosted.byteswap()
    data = io.BytesIO()
    with wave.open(data, 'wb') as out:
        out.setnchannels(1); out.setsampwidth(2); out.setframerate(16000); out.writeframes(boosted.tobytes())
    return data.getvalue()


class MacVoice:
    def __init__(self, portal, binary=None, clock=time.monotonic):
        self.portal, self.clock = portal, clock
        self.binary = Path(binary) if binary else Path(__file__).with_name('MacMicrophone')
        self.lock = threading.RLock()
        self.owner = None; self.lease = 0; self.epoch = ''
        self.process = None; self.context = {}; self.session = None
        self.input_started_at = self.last_frame_at = None
        self.waiting_activation = False
        self.input_level = InputLevel()
        self.first_audio_ms = None
        self.speech_signal = None
        self.native_phase = None
        self.helper_error = ''
        self.active_until = self.muted_until = self.session_until = 0
        self.wake_detector = None
        self.endpoint = None
        self.endpoint_issue = None
        self.endpoint_pending = False
        self.endpoint_checked = None
        self.endpoint_score = None
        self.pre_roll = deque(maxlen=WAKE_BUFFER_FRAMES)
        self.transcript_lock = threading.Lock()
        self.checked_transcript = None
        self.preview_stamp = None
        self.timings = {}
        self.turn_id = ''
        self.last_result = None
        self.stage = 'idle'
        self.last_activity = 0
        self.activated_at = float('-inf')
        self.capped_until = 0
        self.question_revision = 0
        self.pending_audio = None
        self.continuation = None
        self.continuation_until = 0
        self.answer_gate = threading.Event(); self.answer_gate.set()
        self.text_decision = None
        self.conversation_version = 2
        self.followup_until = 0
        self.playback_ticket = None
        self.playback_active = self.playback_done = False
        if hasattr(portal,'root'):
            try:
                wake_configuration(portal.root)
                self.wake_detector=WakeDetector(portal.root)
            except ValueError:pass
            try:
                turn_configuration(portal.root)
                self.endpoint = Endpoint(portal.root)
            except ValueError as error:
                self.endpoint_issue = str(error)
        self.vad = None
        dependencies=Path(portal.root)/'speech-python' if hasattr(portal,'root') else None
        if dependencies and dependencies.is_dir():
            if str(dependencies) not in sys.path: sys.path.insert(0,str(dependencies))
            try:
                import webrtcvad
                self.vad = webrtcvad.Vad(2)
            except ImportError: pass
        self.events = deque(maxlen=8); self.segmenter = Segmenter(self.vad, automatic=False)
        self.language = 'auto'
        self.status = 'Mac microphone paused'; self.issue = None
        self.busy = self.preview = False; self.recent = 0; self.last_wake = 0
        self.last_preview = 0
        self.worker = ThreadPoolExecutor(max_workers=2, thread_name_prefix='motchi-mac-voice')
        self.endpoint_worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix='motchi-endpoint')

    def invalidate(self, preserve_choice=False):
        """Replace a turn without replacing the microphone or its heartbeat."""
        replacement = str(uuid.uuid4())
        if self.owner:
            if preserve_choice and hasattr(self.portal.voice, 'replace'):
                self.portal.voice.replace(self.owner, self.epoch, replacement)
            else:
                self.portal.voice.cancel(self.owner, self.epoch)
        self.epoch = replacement
        self.turn_id = str(uuid.uuid4())
        self.last_result = None
        self.session = None
        self.active_until = self.session_until = 0
        self.busy = self.preview = False
        self.endpoint_pending = False
        self.endpoint_checked = None
        self.endpoint_score = None
        self.pre_roll.clear()
        self.checked_transcript = None
        self.preview_stamp = None
        self.last_preview = 0
        self.timings = {}
        self.capped_until = 0
        self.question_revision += 1
        self.segmenter.reset()
        self.events.clear()
        self.pending_audio = self.continuation = None
        self.continuation_until = 0
        self.answer_gate.set()
        self.text_decision = None
        self.waiting_activation = False
        self.followup_until = 0
        self.playback_ticket = None
        self.playback_active = self.playback_done = False

    def activate(self, pre_roll=(), keyword='', followup=False):
        self.invalidate(preserve_choice=not self.busy)
        self.activated_at = self.clock()
        self.muted_until = 0
        self.active_until = self.clock()+30
        self.last_activity = self.clock()
        self.stage = 'listening'
        # Keyword inference can finish after the next words have begun. Replay
        # only the bounded local wake context so those words are not clipped.
        for frame in pre_roll:
            self.segmenter.push(frame)
        self.issue = None
        if self.endpoint:
            self.endpoint_issue = None  # Retry transient worker failure on a fresh wake.
        self.last_wake = int(time.time()*1000)
        chinese = self.language == 'zh' or bool(re.search(r'[\u3400-\u9fff]',keyword))
        text = '我在听，请说。' if chinese else "I'm listening. Go ahead."
        self.events.append({'wake': True, 'partial': True, 'heard': '',
                            'text': text, 'stage': 'listening',
                            'followup': followup,
                            'turnId': self.turn_id, 'stopPlayback': True, 'ready': True})
        self.status = "I'm listening · Mac microphone"

    def followup_status(self):
        self.stage = 'follow-up'
        chinese = self.language == 'zh' or bool(re.search(r'[\u3400-\u9fff]',
                    (self.last_result or {}).get('transcript','')))
        self.status = ('可以继续问，我在听。' if chinese else
                       'Ready for your next question · no wake name needed')

    def playback(self, body):
        """Exact playback receipts release echo suppression once, not per poll."""
        ticket = (body.get('playbackTurnId'), body.get('playbackOperationId'))
        if ticket != self.playback_ticket or self.playback_done:
            return False
        if body.get('speaking') is True:
            self.playback_active = True
            self.muted_until = self.clock()+2
            self.segmenter.reset(); self.pre_roll.clear()
        elif body.get('speaking') is False:
            self.playback_active = False; self.playback_done = True
            # The exact player has finished. Accept the next PCM frame rather
            # than dropping the start of a prompt reply in an extra mute tail.
            self.muted_until = self.clock()
            self.segmenter.reset(); self.pre_roll.clear()
            if self.last_result and not self.busy and self.conversation_version >= 2:
                self.followup_until = self.clock()+FOLLOWUP_SECONDS
                self.followup_status()
        return True

    def control(self, device, body):
        if body.get('enabled') is False:
            with self.lock:
                if self.owner == device: self.stop()
            return {'enabled': False, 'running': False, 'status': 'Mac microphone paused'}
        if body.get('enabled') is not True:
            raise ValueError('Choose whether to enable the Mac microphone.')
        with self.lock:
            if body.get('heartbeat') is True and (self.owner != device or not self.process or self.process.poll() is not None):
                return self.snapshot() if self.owner in (None,device) else {'enabled':False,'running':False,'status':'Mac microphone paused'}
        if hasattr(self.portal, 'root') and not microphone_policy.allowed(self.portal.root, device):
            raise ValueError('Microphone paused locally on the Mac. Paired devices cannot restart it.')
        language=body.get('language') or 'auto'
        if language not in ('en','zh','auto'): raise ValueError('Choose a supported speech language.')
        with self.lock:
            if self.owner and self.owner != device:
                raise ValueError('Another paired device is using the Mac microphone. Pause it first.')
            if self.owner and (not self.process or self.process.poll() is not None): self.stop()
            if not self.owner:
                if not self.binary.is_file(): raise ValueError('Update the Mac companion to install its microphone helper.')
                self.owner = device; self.epoch = str(uuid.uuid4()); self.session = None
                self.status = 'Starting Mac microphone · allow the macOS prompt if shown'
                self.issue = None; self.events.clear(); self.segmenter = Segmenter(self.vad, automatic=False)
                try:
                    self.input_started_at = self.clock(); self.last_frame_at = None
                    self.first_audio_ms = None; self.input_level = InputLevel()
                    self.native_phase = None; self.helper_error = ''
                    self.process = subprocess.Popen([str(self.binary)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    if self.wake_detector:self.wake_detector.start()
                except (OSError, ValueError) as error:
                    # A failed optional model starts after the PCM child. Do
                    # not leave that child recording before watchdog setup.
                    self.stop()
                    raise ValueError(str(error) if isinstance(error, ValueError) else
                                     'The Mac microphone helper could not start.') from None
                threading.Thread(target=self.capture, args=(device,self.epoch,self.process), daemon=True).start()
                threading.Thread(target=self.helper_status,args=(self.process,),daemon=True).start()
                threading.Thread(target=self.watchdog, args=(self.process,), daemon=True).start()
                if hasattr(self.portal, 'warm_mac_voice'):
                    self.worker.submit(self.portal.warm_mac_voice)
            self.lease = self.clock()+25
            context = {k:body.get(k) or None for k in ('projectId','selection')}
            if context != self.context or self.language != language:
                # An automatically routed reply tells the UI which project to
                # open. Adopting that exact result is not a new user question:
                # retain its queued text and asynchronous spoken reply.
                result = self.last_result or {}
                adopting_reply = (self.language == language and
                                  result.get('projectId') and not result.get('failed') and
                                  result.get('turnId') == self.turn_id and
                                  context == {k:result.get(k) or None for k in ('projectId','selection')})
                if not adopting_reply:
                    self.invalidate(); self.stage = 'idle'
                    if self.wake_detector:self.wake_detector.clear()
                self.context = context
            self.language = language
            self.conversation_version = 2 if body.get('conversationVersion') == 2 else 1
            if body.get('activate') is True:
                if self.last_frame_at is None:
                    self.waiting_activation = True
                    self.stage = 'starting'
                else:
                    self.activate()
            if body.get('activate') is not True:
                handled = self.playback(body) if body.get('playbackOperationId') else False
                if not handled and not body.get('playbackOperationId'):
                    if body.get('speaking') is True:
                        self.playback_active = True; self.muted_until = self.clock()+2
                    elif self.playback_active and body.get('speaking') is False:
                        self.playback_active = False
                        self.muted_until = self.clock()+PLAYBACK_TAIL_SECONDS
                        self.segmenter.reset(); self.pre_roll.clear()
                        if self.last_result and not self.busy and self.conversation_version >= 2:
                            self.followup_until = self.clock()+FOLLOWUP_SECONDS
                            self.followup_status()
            if body.get('finish') is True and not self.busy and self.clock() < self.active_until:
                data=self.segmenter.finish()
                if data:
                    self.finalize(data, resumable=False)
                else:
                    self.issue='No speech has been captured yet. Tap Listen now and speak near your Mac.'
            return self.snapshot()

    def poll(self, device):
        with self.lock:
            if self.owner != device:
                return {**(self.snapshot() if self.owner is None else {'enabled':False,'running':False,'status':'Mac microphone paused'}),'events':[]}
            self.lease = self.clock()+25
            result = self.snapshot(); result['events'] = list(self.events); self.events.clear()
            return result

    def snapshot(self):
        alive = bool(self.process and self.process.poll() is None)
        starting = alive and self.last_frame_at is None
        status = 'Starting Mac microphone · wait for “I’m listening” before speaking' if starting else self.status
        return {'enabled':bool(self.owner), 'running':alive and not starting, 'starting':starting,
                'source':'mac', 'inputSource':'Mac microphone', 'rms':self.segmenter.rms,
                'recentRms':self.recent, 'busy':self.busy or self.preview,
                'rawRms':round(self.input_level.rms), 'inputGain':round(self.input_level.gain,2),
                'firstAudioMs':self.first_audio_ms,
                'nativePhase':self.native_phase,
                'audioAgeMs':round(max(0,self.clock()-self.last_frame_at)*1000) if self.last_frame_at is not None else None,
                'speechDetector':'Silero · local speech/noise' if getattr(self.wake_detector,'speech_ready',False) else 'WebRTC' if self.vad else 'Sound level',
                'speechProbability':getattr(self.wake_detector,'probability',None),
                'quietMs':self.segmenter.quiet*20, 'voicedMs':self.segmenter.voiced*20,
                'detector':'WebRTC speech detector' if self.vad else 'Sound-level fallback',
                'utteranceSeconds':round(len(self.segmenter.speech or b'')/32000,1),
                'language':self.language,
                'stage':self.stage, 'turnId':self.turn_id,
                'followupSeconds':round(max(0,self.followup_until-self.clock()),1)
                    if not self.playback_active and not self.busy else 0,
                'turnDetector':'Smart Turn v3.2 · local' if self.endpoint else 'Manual Finish question',
                'turnIssue':self.endpoint_issue, 'endpointProbability':self.endpoint_score,
                'timings':dict(self.timings),
                'textDecision':self.text_decision,
                'wakeDetector':'Local bilingual keyword detector' if self.wake_detector else 'Unavailable · use Listen now',
                'wakeReady':self.wake_detector.ready if self.wake_detector else False,
                'status':status, 'issue':self.issue or (self.wake_detector.issue if self.wake_detector else None), 'lastWakeAt':self.last_wake,
                **(doubao_speech.info(self.portal.root) if hasattr(self.portal,'root') else {})}

    def publish_transcript(self, device, epoch, text):
        with self.lock:
            if self.owner==device and self.epoch==epoch:
                self.valid(device, epoch)
                self.events.append({'wake':True,'partial':True,'heard':text,'transcript':text,'text':text,'provider':'doubao','turnId':self.turn_id})

    def valid(self, device, epoch):
        if (self.owner != device or self.epoch != epoch or not self.portal.device_permitted(device)
                or hasattr(self.portal, 'root') and not microphone_policy.allowed(self.portal.root, device)):
            raise ValueError('Voice turn was superseded or paused.')

    def finalize(self, data, transcript=None, resumable=True):
        self.timings['finishMode'] = 'automatic' if resumable else 'manual'
        self.timings['processingAfterSpeechMs'] = round(max(0, self.clock()-self.last_activity)*1000)
        self.question_revision += 1
        self.checked_transcript = None
        self.preview_stamp = self.endpoint_checked = None
        self.busy = True
        self.active_until = 0
        self.stage = 'processing'
        self.status = 'Checking your question · say Hey Motchi to change it'
        self.pending_audio = data if resumable else None
        self.continuation = {'buffer': Segmenter(self.vad, automatic=False), 'pending': False, 'checked': None} if resumable else None
        self.continuation_until = self.clock()+CONTINUATION_SECONDS if resumable else 0
        self.answer_gate.set()
        if transcript and self.conversation_version >= 2:
            self.events.append({'wake': True, 'partial': True, 'processing': True,
                                'heard': transcript, 'transcript': transcript, 'turnId': self.turn_id})
        if self.conversation_version >= 2 and hasattr(self.portal, 'synthesize_mac_reply'):
            threading.Thread(target=self.processing_notices,
                args=(self.owner,self.epoch,self.question_revision,transcript or ''),
                daemon=True,name='motchi-reply-feedback').start()
        self.worker.submit(self.recognize, self.owner, self.epoch, data, False, True, transcript)

    def processing_notice(self, device, epoch, revision, transcript):
        """Short reassurance, never an answer or a new user conversation."""
        with self.lock:
            self.valid(device, epoch)
            if not self.busy or self.last_result is not None or self.stage!='processing' or revision!=self.question_revision or not self.answer_gate.is_set():
                return None
            chinese=self.language=='zh' or bool(re.search(r'[\u3400-\u9fff]',transcript))
            return {'wake':True,'processing':True,'processingNotice':True,
                    'text':'我还在整理回答，请稍等。' if chinese else 'I’m still preparing your answer. One moment.',
                    'operationId':str(uuid.uuid4()),'turnId':self.turn_id,'noticeRevision':revision}

    def processing_notices(self, device, epoch, revision, transcript):
        # Speech synthesis runs on this separate daemon, never on the answer
        # worker. A completion, continuation, pause or new turn invalidates it.
        interval=4
        while True:
            threading.Event().wait(interval)
            try:
                notice=self.processing_notice(device,epoch,revision,transcript)
                if notice is None:return
                self.portal.synthesize_mac_reply(device,epoch,notice)
            except Exception:return
            interval=8

    def await_continuation(self, device, epoch):
        """Do not publish/save an answer over a possible resumed sentence."""
        deadline = time.monotonic()+4
        while True:
            with self.lock:
                self.valid(device, epoch)
                if self.answer_gate.is_set(): return
            if time.monotonic() >= deadline:
                raise ValueError('I heard more speech but could not confirm it. Tap Talk to retry your complete question.')
            self.answer_gate.wait(.05)

    def processing_frame(self, device, data):
        """Inspect only a bounded continuation of this already addressed turn.

        No speaker identity is inferred. Playback never enters this path. Pure
        acknowledgments and thinking sounds do not replace the pending answer.
        """
        candidate = self.continuation
        if not candidate or not self.pending_audio: return
        buffer = candidate['buffer']
        if self.clock() >= self.continuation_until and buffer.speech is None:
            return
        if self.clock() >= self.continuation_until+4:
            self.answer_gate.set(); return
        buffer.push(data,voiced=self.speech_signal)
        if buffer.voiced >= 8 and (candidate['pending'] or candidate['checked'] != buffer.version):
            self.answer_gate.clear()
        if (not candidate['pending'] and buffer.voiced >= 8 and
                (buffer.quiet >= 8 or buffer.voiced >= 30) and candidate['checked'] != buffer.version):
            candidate.update(pending=True, checked=buffer.version)
            self.worker.submit(self.check_continuation, device, self.epoch, candidate,
                               buffer.version, bytes(buffer.speech))

    def check_continuation(self, device, epoch, candidate, version, pcm):
        def permitted():
            with self.lock:
                self.valid(device, epoch)
                if not self.busy or self.continuation is not candidate:
                    raise ValueError('Continuation expired.')
        try:
            if not hasattr(self.portal, 'voice_transcribe'): return
            with self.transcript_lock:
                permitted()
                text = self.portal.voice_transcribe(wav_bytes(pcm),
                    {'generation': epoch, '_device': device, '_addressed': True,
                     '_permitted': permitted, 'language': self.language})
            with self.lock:
                permitted()
                if continues_question(text):
                    original = self.pending_audio
                    extra = bytes(candidate['buffer'].speech or b'')
                    combined = (original+extra)[:1920000]
                    self.activate()
                    # Keep the original question and every newly captured word.
                    # activate() cancels the old provider and invalidates its TTS.
                    for offset in range(0, len(combined)-639, 640):
                        self.segmenter.push(combined[offset:offset+640])
                    self.last_activity = self.clock()
                    self.timings['resumedQuestion'] = True
                    self.status = 'Go on · I’m listening to the rest of your question'
                    self.events[-1].update(resumed=True, text='Go on. I’m listening to the rest of your question.')
                elif candidate['buffer'].version == version:
                    self.answer_gate.set()
        except Exception:
            with self.lock:
                if self.epoch == epoch and self.continuation is candidate:
                    self.answer_gate.set()
        finally:
            with self.lock:
                if self.epoch == epoch and self.continuation is candidate:
                    candidate['pending'] = False

    def transcribe_candidate(self, device, epoch, version, pcm, permitted):
        """Reuse only the exact voiced revision; never a guessed partial text."""
        with self.transcript_lock:
            permitted()
            with self.lock:
                cached = self.checked_transcript
                if cached and cached[:2] == (epoch, version):
                    self.timings['transcriptReused'] = True
                    return cached[2]
                language = self.language
            start = self.clock()
            def audio_permitted():
                with self.lock:
                    self.valid(device, epoch)
                    if self.busy or self.clock() >= self.active_until:
                        raise ValueError('Question capture was replaced or expired.')
            request = {'generation': epoch, '_device': device, '_addressed': True,
                       '_permitted': audio_permitted, 'language': language}
            # Resumed words obsolete this snapshot, not the shared model. Let
            # inference finish warm, then reject its stale revision below. A
            # pause/revoke/new activation still cancels the recognizer promptly.
            text = self.portal.voice_transcribe(wav_bytes(pcm), request)
            permitted()
            with self.lock:
                self.valid(device, epoch)
                self.timings['recognitionMs'] = round((self.clock()-start)*1000)
                if self.segmenter.version == version:
                    self.checked_transcript = (epoch, version, text)
            return text

    def assess_endpoint(self, device, epoch, version, pcm):
        model_checked = False
        try:
            def permitted():
                with self.lock:
                    self.valid(device, epoch)
                    if self.segmenter.version != version or self.clock() >= self.active_until:
                        raise ValueError('Speech resumed or activation expired.')
            start = self.clock()
            score = self.endpoint.predict(pcm, permitted)
            model_checked = True
            with self.lock:
                self.valid(device, epoch)
                if self.segmenter.version != version or self.segmenter.quiet < ENDPOINT_QUIET_FRAMES or self.busy or self.clock() >= self.active_until:
                    return
                self.endpoint_score = score
                self.timings['endpointMs'] = round((self.clock()-start)*1000)
                quiet = self.segmenter.quiet
                self.timings['candidateSilenceMs'] = quiet*20
                candidate = bytes(self.segmenter.speech or b'')
            # A fast, high-confidence complete sentence can proceed early. A
            # tentative score waits for a longer pause instead of cutting in.
            transcript = None
            if hasattr(self.portal, 'voice_transcribe'):
                # Also caption uncertain/unfinished candidates. A low acoustic
                # score must not leave a finished speaker staring at no words.
                transcript = self.transcribe_candidate(device, epoch, version, candidate, permitted)
            cue = turn_text(transcript) if transcript is not None else {'state': 'unavailable'}
            with self.lock:
                permitted()
                self.text_decision = cue
                if transcript:
                    self.events.append({'wake': True, 'partial': True, 'heard': transcript,
                                        'transcript': transcript, 'turnId': self.turn_id})
            acoustic_complete = score >= (.9 if quiet < ENDPOINT_PATIENT_FRAMES else .65)
            text_candidate = (cue['state'] == 'request' and quiet >= ENDPOINT_PATIENT_FRAMES and
                              (score >= .4 or quiet >= ENDPOINT_TEXT_FRAMES))
            meaningful = (len(re.findall(r'\b[a-z]+\b', transcript or '', re.I)) >= 3 or
                          len(re.findall(r'[\u3400-\u9fff]', transcript or '')) >= 5)
            # Explicit activation already grants one conversational turn. An
            # otherwise complete statement need not contain a question word,
            # or wait forever because the acoustic model is uncertain.
            patient_statement = cue['state'] == 'unknown' and meaningful and quiet >= ENDPOINT_STATEMENT_FRAMES
            text_holds = cue['state'] in ('unfinished', 'filler', 'acknowledgment')
            if cue['state'] == 'unknown' and len(re.findall(r'\b[a-z]+\b', transcript, re.I)) < 3 and len(re.findall(r'[\u3400-\u9fff]', transcript)) < 5:
                # A wake name is often misheard as a short proper noun. Do not
                # manufacture a question from it. A pending project choice is
                # the explicit context in which a short name is sufficient.
                pending = getattr(self.portal.voice, 'choice_pending', lambda *_: False)(device, epoch)
                text_holds = not pending
            # Unknown statements/short project choices may finish after the
            # patient pause, but an early answer requires an explicit request.
            early_unknown = quiet < ENDPOINT_PATIENT_FRAMES and cue['state'] == 'unknown'
            if (acoustic_complete or text_candidate or patient_statement) and not text_holds and not early_unknown:
                with self.lock:
                    permitted()
                    if self.busy or self.segmenter.quiet < ENDPOINT_QUIET_FRAMES:
                        return
                    data = self.segmenter.finish()
                    if data:
                        self.finalize(data, transcript)
            else:
                with self.lock:
                    permitted()
                    self.stage = 'listening'
                    self.status = 'Take your time · I’m still listening'
        except Exception:
            with self.lock:
                if self.owner == device and self.epoch == epoch and self.segmenter.version == version and self.clock() < self.active_until and not self.busy:
                    if model_checked:
                        self.issue = 'I couldn’t hear that clearly. Try Talk again or use Finish question.'
                    else:
                        self.endpoint_issue = 'Pause detector unavailable. Tap Finish question when ready.'
                    self.stage = 'listening'
        finally:
            with self.lock:
                if self.epoch == epoch:
                    self.endpoint_pending = False

    def helper_status(self, process):
        try:
            for line in process.stderr:
                if len(line)>2048:break
                with self.lock:
                    if self.process is not process:return
                    try:
                        value=json.loads(line)
                        if value.get('phase') in ('inputCallback','pcmReady','engineStarted'):
                            self.native_phase=value['phase']
                    except (ValueError,TypeError):
                        self.helper_error=line.decode(errors='replace').strip()[:400]
        except OSError:pass

    def watchdog(self, process):
        while True:
            time.sleep(1)
            with self.lock:
                if self.process is not process: return
                if (self.clock() > self.lease or not self.portal.device_permitted(self.owner)
                        or hasattr(self.portal, 'root') and not microphone_policy.allowed(self.portal.root, self.owner)):
                    self.stop(); return
                waiting = self.last_frame_at is None and self.input_started_at is not None and self.clock()-self.input_started_at > 30
                stalled = self.last_frame_at is not None and self.clock()-self.last_frame_at > 5
                if waiting or stalled:
                    self.stop()
                    self.issue = 'Mac microphone delivered no audio. Unlock the Mac, check microphone access, then tap Talk again.'
                    return

    def capture(self, device, epoch, process):
        # The input pipe, meter and wake detector stay responsive while a
        # question is analyzed. A new explicit wake supersedes the old turn.
        try:
            while True:
                data = process.stdout.read(640)
                if len(data) != 640:
                    break
                with self.lock:
                    if self.process is not process or self.owner != device:
                        return
                    if (self.clock() > self.lease or not self.portal.device_permitted(device)
                            or hasattr(self.portal, 'root') and not microphone_policy.allowed(self.portal.root, device)):
                        self.stop(); return
                    self.last_frame_at = self.clock()
                    if self.first_audio_ms is None and self.input_started_at is not None:
                        self.first_audio_ms = round(max(0,self.last_frame_at-self.input_started_at)*1000)
                    data = self.input_level.apply(data)
                    if self.waiting_activation:
                        self.waiting_activation = False
                        self.activate()
                    if self.session and self.clock() >= self.session_until:
                        self.session = None
                    keyword = (self.wake_detector.feed(data)
                               if self.wake_detector and not self.playback_active and self.clock() >= self.muted_until else None)
                    self.speech_signal = getattr(self.wake_detector,'speech',lambda:None)()
                    if (keyword and self.clock() >= self.muted_until and self.clock()-self.activated_at >= 1.2
                            and (self.busy or self.clock() >= self.active_until)):
                        # Local providers can recover speech around the wake.
                        # Never extend a cloud provider's consent boundary to
                        # audio captured before local activation.
                        cloud = hasattr(self.portal, 'root') and doubao_speech.selected(self.portal.root) == 'doubao'
                        self.activate(() if cloud else tuple(self.pre_roll),keyword=keyword)
                    if not self.playback_active and self.clock() >= self.muted_until:
                        self.pre_roll.append(data)
                    else:
                        self.pre_roll.clear()
                    if self.busy or self.playback_active or self.clock() < self.muted_until:
                        # Measure rather than blocking the pipe. During speaker
                        # playback, voice interruption is deliberately disabled
                        # until reference-aware echo handling is verified.
                        samples = array('h', data)
                        self.segmenter.rms = math.sqrt(sum(n*n for n in samples)/len(samples))
                        self.recent = max(self.segmenter.rms, self.recent*.996)
                        if self.busy and not self.playback_active and self.clock() >= self.muted_until:
                            self.processing_frame(device, data)
                        continue
                    active = self.clock() < self.active_until
                    if not active:
                        if self.clock() < self.followup_until:
                            self.segmenter.push(data, voiced=self.speech_signal)
                            self.recent = max(self.segmenter.rms, self.recent*.996)
                            if self.segmenter.speech is not None:
                                frames = bytes(self.segmenter.speech)
                                keyword = (self.last_result or {}).get('transcript','')
                                self.activate(tuple(frames[i:i+640] for i in range(0,len(frames),640)),
                                              keyword=keyword, followup=True)
                            else:
                                self.followup_status()
                            continue
                        self.segmenter.push(data,voiced=self.speech_signal); self.segmenter.reset()
                        self.recent = max(self.segmenter.rms, self.recent*.996)
                        self.stage = 'idle'
                        self.status = ('Ready · say Motchi / 莫奇 · English + 中文' if self.wake_detector.ready
                                       else 'Starting wake detector · use Talk until ready') if self.wake_detector else 'Tap Listen now to ask a question'
                        continue
                    version = self.segmenter.version
                    self.segmenter.push(data,voiced=self.speech_signal)
                    self.recent = max(self.segmenter.rms, self.recent*.996)
                    if self.segmenter.version != version:
                        self.last_activity = self.clock()
                        self.active_until = self.clock()+30
                        self.stage = 'listening'
                    if self.segmenter.full:
                        # Never silently cut a longer question into two requests.
                        self.issue = 'Question reached 60 seconds. Tap Finish question or Listen now to restart.'
                        if not self.capped_until:
                            self.capped_until = self.clock()+30
                        self.active_until = self.capped_until
                        continue
                    endpoint = self.segmenter.endpoint_audio()
                    if endpoint and self.endpoint and not self.endpoint_pending and not self.endpoint_issue:
                        # Reassess at each patience threshold even if nobody
                        # speaks again after an uncertain early assessment.
                        stamp = (self.epoch, self.segmenter.version,
                                 3 if self.segmenter.quiet >= ENDPOINT_STATEMENT_FRAMES else
                                 2 if self.segmenter.quiet >= ENDPOINT_TEXT_FRAMES else
                                 1 if self.segmenter.quiet >= ENDPOINT_PATIENT_FRAMES else 0)
                        if stamp != self.endpoint_checked:
                            self.endpoint_checked = stamp
                            self.endpoint_pending = True
                            self.stage = 'possible-end'
                            self.status = 'Understanding your question…'
                            self.endpoint_worker.submit(self.assess_endpoint, device, self.epoch, stamp[1], endpoint)
                    if self.segmenter.quiet >= 300:
                        self.status = 'Still listening · tap Finish question if you are done'
                    trailing = 8 <= self.segmenter.quiet < ENDPOINT_QUIET_FRAMES
                    stamp = (self.epoch, self.segmenter.version)
                    if not self.preview and stamp != self.preview_stamp and (trailing or self.clock()-self.last_preview > 1.2):
                        partial = self.segmenter.partial()
                        if partial and self.segmenter.quiet < ENDPOINT_QUIET_FRAMES:
                            self.last_preview = self.clock()
                            self.preview_stamp = stamp
                            self.preview = True
                            self.worker.submit(self.recognize, device, self.epoch, partial, True, True, None, stamp[1])
        except (OSError, ValueError):
            pass
        finally:
            with self.lock:
                if self.process is process:
                    self.issue = self.helper_error or 'Mac microphone stopped. Check microphone access, then try Listen now.'
                    self.status = 'Mac microphone needs attention'; self.process = None

    def recognize(self, device, epoch, pcm, preview, activated=None, transcript=None, version=None):
        revision = None
        try:
            with self.lock:
                if self.owner != device or self.epoch != epoch: return
                request = dict(self.context, operationId=str(uuid.uuid4()), generation=epoch, session=self.session,
                               action='listen', preview=preview, activated=self.clock()<self.active_until if activated is None else activated,language=self.language)
                revision = self.question_revision
                cloud=hasattr(self.portal,'root') and doubao_speech.selected(self.portal.root)=='doubao'
                if preview and self.busy:
                    return
                self.status = ('Recognizing with Doubao after activation…' if request['activated'] or request['session']
                               else 'Checking the wake name locally…') if cloud else 'Recognizing your speech locally…'
            if hasattr(self.portal, 'run_mac_voice'):
                if not preview:
                    request['_permitted'] = lambda: self.await_continuation(device, epoch)
                # Internal authenticated path avoids a long project lookup
                # occupying the only HTTP voice-segment slot. Preview and final
                # recognition still share the bounded local ASR worker.
                if preview and version is not None and hasattr(self.portal, 'voice_transcribe'):
                    def permitted():
                        with self.lock:
                            self.valid(device, epoch)
                            if self.busy or self.clock() >= self.active_until:
                                raise ValueError('Partial recognition was superseded.')
                    transcript = self.transcribe_candidate(device, epoch, version, pcm, permitted)
                start = self.clock()
                result = self.portal.run_mac_voice(device, request, wav_bytes(pcm),
                                                   **({'transcript': transcript} if transcript is not None else {}))
                with self.lock:
                    if self.owner == device and self.epoch == epoch and not preview:
                        self.timings['answerMs'] = round((self.clock()-start)*1000)
                        self.timings['answerAfterSpeechMs'] = round(max(0, self.clock()-self.last_activity)*1000)
                        breakdown = result.get('discussionTimings', {})
                        if isinstance(breakdown, dict):
                            self.timings['discussion'] = {k: v for k, v in breakdown.items()
                                if k in ('contextMs', 'providerMs', 'totalMs') and type(v) is int and v >= 0}
                if self.conversation_version < 2 and not preview and result.get('wake') and result.get('text') and hasattr(self.portal,'prepare_mac_reply'):
                    # Installed older clients expect audio on the original
                    # answer. Do not send them a second visible answer event.
                    result['operationId'] = request['operationId']
                    try:
                        result['spokenReply'] = self.portal.prepare_mac_reply(device, epoch, result)
                    except Exception:
                        result['speechIssue'] = 'Spoken reply unavailable. The answer is readable on screen.'
                job = {'status': 'done', 'result': result}
            else:
                job = self.portal.submit(device, request, wav_bytes(pcm))
                while job['status'] in ('queued','running'):
                    time.sleep(.2)
                    with self.lock:
                        if self.owner != device or self.epoch != epoch: return
                    job = self.portal.job(device, request['operationId'])
            if job['status'] != 'done': raise ValueError(job.get('result',{}).get('error','Speech was not recognized. Try again.'))
            if not preview: self.await_continuation(device, epoch)
            with self.lock:
                if self.owner != device or self.epoch != epoch: return
                self.valid(device, epoch)
                if preview and (self.busy or self.clock() >= self.active_until or revision != self.question_revision): return
                result = job['result']
                self.issue = None
                if result.get('wake'):
                    self.session = result.get('session') if result.get('sessionSeconds',0)>0 or result.get('partial') else None
                    self.session_until=self.clock()+result.get('sessionSeconds',20) if self.session else 0
                    if not result.get('partial') and result.get('heard'):self.active_until=0
                    self.last_wake = int(time.time()*1000)
                    result.update(operationId=request['operationId'], turnId=self.turn_id,
                                  stage='listening' if result.get('partial') or result.get('sessionSeconds',0)>0 else 'answered')
                    if not preview and not result.get('partial'):
                        self.last_result = dict(result)
                        if result.get('heard') and self.conversation_version >= 2:
                            self.segmenter.reset()
                            self.followup_until = self.clock()+FOLLOWUP_SECONDS
                    self.events.append(result)
                    # Keep the caller's context until it receives the reply.
                    # Mutating it here makes the next old-context heartbeat
                    # invalidate the generation and erase this very answer.
                    # Give the calendar time to fetch/play the answer. Heartbeat
                    # renews the mute throughout playback to prevent feedback.
                    if result.get('spokenReply'): self.muted_until = self.clock()+4
                    if not preview and result.get('sessionSeconds',0)>0:
                        self.active_until = self.clock()+result['sessionSeconds']
                    if not preview and self.conversation_version >= 2 and hasattr(self.portal, 'synthesize_mac_reply'):
                        self.portal.executor.submit(self.portal.synthesize_mac_reply, device, epoch, dict(result))
        except Exception as error:
            with self.lock:
                if self.owner == device and self.epoch == epoch and not (preview and (self.busy or revision != self.question_revision)):
                    try:
                        self.valid(device, epoch)
                    except ValueError:
                        return  # A local pause/revocation also suppresses error text.
                    self.issue = str(error)[:400]
                    if not preview:
                        self.active_until = 0
                        self.events.append({'wake':True, 'failed':True, 'text':self.issue,
                                            'transcript':transcript or '', 'turnId':self.turn_id,
                                            'operationId':request['operationId']})
        finally:
            with self.lock:
                if self.owner != device or self.epoch != epoch:
                    return
                if preview: self.preview = False
                else:
                    self.busy = False
                    self.pending_audio = self.continuation = None
                    self.answer_gate.set()
                    self.stage = 'listening' if self.clock()<self.active_until else 'idle'
                    if self.clock()<self.followup_until:
                        self.followup_status()
                if self.owner == device:
                    self.status = ('Checking your project history · say Hey Motchi to change it' if self.busy
                                   else "I'm listening · Mac microphone" if self.clock()<self.active_until
                                   else self.status if self.clock()<self.followup_until
                                   else 'Listening for Hey Motchi · Mac microphone')

    def audio_ready(self, device, epoch, result):
        with self.lock:
            self.valid(device, epoch)
            if result.get('processingNotice') and (not self.busy or self.last_result is not None or self.stage!='processing' or
                    result.get('noticeRevision')!=self.question_revision or result.get('turnId')!=self.turn_id):
                raise ValueError('The waiting notice is no longer needed.')
            # A text answer is already visible. This event only starts playback.
            self.events.append({**result, 'wake': True, 'audioOnly': True, 'spokenReply': True})
            self.playback_ticket = (result.get('turnId'), result.get('operationId'))
            self.playback_active = self.playback_done = False
            self.muted_until = self.clock()+4

    def stop(self):
        with self.lock:
            self.invalidate()
            self.owner = None; self.session = None; self.context = {}; self.active_until = 0
            self.busy = self.preview = False; self.events.clear()
            if self.wake_detector:self.wake_detector.close()
            process,self.process = self.process,None
            self.input_started_at = self.last_frame_at = None
            self.status = 'Mac microphone paused'
            self.stage = 'idle'; self.segmenter.reset()
            if process:
                process.terminate()
                try: process.wait(timeout=2)
                except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=2)

    def close(self):
        self.stop(); self.worker.shutdown(wait=False,cancel_futures=True)
        self.endpoint_worker.shutdown(wait=False,cancel_futures=True)
        if self.endpoint: self.endpoint.close()
