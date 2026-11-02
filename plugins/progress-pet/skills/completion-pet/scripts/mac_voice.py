"""Opt-in Mac microphone for one paired calendar, with an expiring heartbeat.

Only in-memory, bounded PCM is retained. A silent or disconnected calendar
cannot keep the Mac microphone on indefinitely. No work/approval actions.
"""
from array import array
from collections import deque
from concurrent.futures import ThreadPoolExecutor
import io
import math
from pathlib import Path
import subprocess
import sys
import threading
import time
import uuid
import wave
import doubao_speech
from wake_detector import WakeDetector, configuration as wake_configuration
from smart_turn import Endpoint, configuration as turn_configuration
from voice_companion import unfinished, explicit_question
import microphone_policy

ENDPOINT_QUIET_FRAMES = 28  # 560 ms; early completion needs stronger model confidence.
ENDPOINT_PATIENT_FRAMES = 60  # 1.2 s for less certain complete turns.
ENDPOINT_TEXT_FRAMES = 100  # 2 s; a hesitant score also needs an explicit complete question.
WAKE_BUFFER_FRAMES = 120  # 2.4 s in memory, shared only after a local wake.

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

    def push(self, frame):
        samples = array('h', frame)
        if sys.byteorder != 'little': samples.byteswap()
        self.rms = math.sqrt(sum(n*n for n in samples)/max(1, len(samples)))
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
        self.stage = 'idle'
        self.last_activity = 0
        self.activated_at = float('-inf')
        self.capped_until = 0
        self.question_revision = 0
        self.conversation_version = 2
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
        self.language = 'en'
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
        self.session = None
        self.active_until = self.session_until = 0
        self.busy = self.preview = False
        self.endpoint_pending = False
        self.endpoint_checked = None
        self.endpoint_score = None
        self.pre_roll.clear()
        self.checked_transcript = None
        self.preview_stamp = None
        self.timings = {}
        self.capped_until = 0
        self.question_revision += 1
        self.segmenter.reset()
        self.events.clear()

    def activate(self, pre_roll=()):
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
        self.events.append({'wake': True, 'partial': True, 'heard': '',
                            'text': "I'm listening. Go ahead.", 'stage': 'listening',
                            'turnId': self.turn_id, 'stopPlayback': True})
        self.status = "I'm listening · Mac microphone"

    def control(self, device, body):
        if body.get('enabled') is False:
            with self.lock:
                if self.owner == device: self.stop()
            return {'enabled': False, 'running': False, 'status': 'Mac microphone paused'}
        if body.get('enabled') is not True:
            raise ValueError('Choose whether to enable the Mac microphone.')
        if hasattr(self.portal, 'root') and not microphone_policy.allowed(self.portal.root, device):
            raise ValueError('Microphone paused locally on the Mac. Paired devices cannot restart it.')
        language=body.get('language') or 'en'
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
                    if self.wake_detector:self.wake_detector.start()
                    self.input_started_at = self.clock(); self.last_frame_at = None
                    self.process = subprocess.Popen([str(self.binary)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                except OSError:
                    self.owner = None; raise ValueError('The Mac microphone helper could not start.')
                threading.Thread(target=self.capture, args=(device,self.epoch,self.process), daemon=True).start()
                threading.Thread(target=self.watchdog, args=(self.process,), daemon=True).start()
                if hasattr(self.portal, 'warm_mac_voice'):
                    self.worker.submit(self.portal.warm_mac_voice)
            self.lease = self.clock()+25
            context = {k:body.get(k) or None for k in ('projectId','selection')}
            if context != self.context or self.language != language:
                self.invalidate(); self.context = context; self.stage = 'idle'
                if self.wake_detector:self.wake_detector.clear()
            self.language = language
            self.conversation_version = 2 if body.get('conversationVersion') == 2 else 1
            if body.get('activate') is True:
                self.activate()
            if body.get('speaking') is True and body.get('activate') is not True: self.muted_until = self.clock()+2
            if body.get('finish') is True and not self.busy and self.clock() < self.active_until:
                data=self.segmenter.finish()
                if data:
                    self.finalize(data)
                else:
                    self.issue='No speech has been captured yet. Tap Listen now and speak near your Mac.'
            return self.snapshot()

    def poll(self, device):
        with self.lock:
            if self.owner != device: return {'enabled': False, 'running': False, 'status': 'Mac microphone paused', 'events': []}
            self.lease = self.clock()+25
            result = self.snapshot(); result['events'] = list(self.events); self.events.clear()
            return result

    def snapshot(self):
        alive = bool(self.process and self.process.poll() is None)
        starting = alive and self.last_frame_at is None
        status = 'Waiting for Mac microphone audio · unlock the Mac and allow microphone access if asked' if starting else self.status
        return {'enabled':bool(self.owner), 'running':alive and not starting, 'starting':starting,
                'source':'mac', 'inputSource':'Mac microphone', 'rms':self.segmenter.rms,
                'recentRms':self.recent, 'busy':self.busy or self.preview,
                'detector':'WebRTC speech detector' if self.vad else 'Sound-level fallback',
                'utteranceSeconds':round(len(self.segmenter.speech or b'')/32000,1),
                'language':self.language,
                'stage':self.stage, 'turnId':self.turn_id,
                'turnDetector':'Smart Turn v3.2 · local' if self.endpoint else 'Manual Finish question',
                'turnIssue':self.endpoint_issue, 'endpointProbability':self.endpoint_score,
                'timings':dict(self.timings),
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

    def finalize(self, data, transcript=None):
        self.timings['processingAfterSpeechMs'] = round(max(0, self.clock()-self.last_activity)*1000)
        self.question_revision += 1
        self.checked_transcript = None
        self.preview_stamp = self.endpoint_checked = None
        self.busy = True
        self.active_until = 0
        self.stage = 'processing'
        self.status = 'Checking your question · say Hey Motchi to change it'
        if transcript and self.conversation_version >= 2:
            self.events.append({'wake': True, 'partial': True, 'processing': True,
                                'heard': transcript, 'transcript': transcript, 'turnId': self.turn_id})
        self.worker.submit(self.recognize, self.owner, self.epoch, data, False, True, transcript)

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
            request = {'generation': epoch, '_device': device, '_addressed': True,
                       '_permitted': permitted, 'language': language}
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
            acoustic_complete = score >= (.9 if quiet < ENDPOINT_PATIENT_FRAMES else .65)
            text_candidate = quiet >= ENDPOINT_TEXT_FRAMES and score >= .4
            if acoustic_complete or text_candidate:
                transcript = None
                if hasattr(self.portal, 'voice_transcribe'):
                    # Keep capture live throughout this local check. New speech
                    # invalidates it before any project question can be sent.
                    transcript = self.transcribe_candidate(device, epoch, version, candidate, permitted)
                with self.lock:
                    permitted()
                    if self.busy or self.segmenter.quiet < ENDPOINT_QUIET_FRAMES:
                        return
                    if (transcript and unfinished(transcript)) or (not acoustic_complete and not explicit_question(transcript or '')):
                        self.stage = 'listening'
                        self.status = 'Take your time · I’m still listening'
                        self.events.append({'wake': True, 'partial': True, 'heard': transcript,
                                            'text': transcript, 'turnId': self.turn_id})
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
                    if self.session and self.clock() >= self.session_until:
                        self.session = None
                    keyword = self.wake_detector.feed(data) if self.wake_detector else None
                    if keyword and self.clock() >= self.muted_until and self.clock()-self.activated_at >= 1.2:
                        # Local providers can recover speech around the wake.
                        # Never extend a cloud provider's consent boundary to
                        # audio captured before local activation.
                        cloud = hasattr(self.portal, 'root') and doubao_speech.selected(self.portal.root) == 'doubao'
                        self.activate(() if cloud else tuple(self.pre_roll))
                    if self.clock() >= self.muted_until:
                        self.pre_roll.append(data)
                    else:
                        self.pre_roll.clear()
                    if self.busy or self.clock() < self.muted_until:
                        # Measure rather than blocking the pipe. During speaker
                        # playback, voice interruption is deliberately disabled
                        # until reference-aware echo handling is verified.
                        samples = array('h', data)
                        self.segmenter.rms = math.sqrt(sum(n*n for n in samples)/len(samples))
                        self.recent = max(self.segmenter.rms, self.recent*.996)
                        continue
                    active = self.clock() < self.active_until
                    if not active:
                        self.segmenter.push(data); self.segmenter.reset()
                        self.recent = max(self.segmenter.rms, self.recent*.996)
                        self.stage = 'idle'
                        self.status = ('Listening for Hey Motchi · local keyword detector' if self.wake_detector.ready
                                       else 'Starting wake detector · use Talk until ready') if self.wake_detector else 'Tap Listen now to ask a question'
                        continue
                    version = self.segmenter.version
                    self.segmenter.push(data)
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
                    message = process.stderr.read(2048).decode(errors='replace').strip() if process.poll() is not None else ''
                    self.issue = message[-400:] or 'Mac microphone stopped. Check microphone access, then try Listen now.'
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
                    self.events.append(result)
                    if result.get('projectId'): self.context = {k:result.get(k) for k in ('projectId','selection')}
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
                    self.issue = str(error)[:400]
        finally:
            with self.lock:
                if self.owner != device or self.epoch != epoch:
                    return
                if preview: self.preview = False
                else:
                    self.busy = False
                    self.stage = 'listening' if self.clock()<self.active_until else 'idle'
                if self.owner == device:
                    self.status = ('Checking your project history · say Hey Motchi to change it' if self.busy
                                   else "I'm listening · Mac microphone" if self.clock()<self.active_until
                                   else 'Listening for Hey Motchi · Mac microphone')

    def audio_ready(self, device, epoch, result):
        with self.lock:
            self.valid(device, epoch)
            # A text answer is already visible. This event only starts playback.
            self.events.append({**result, 'wake': True, 'audioOnly': True, 'spokenReply': True})
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
