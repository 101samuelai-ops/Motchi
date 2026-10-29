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


class Segmenter:
    def __init__(self, vad=None):
        self.vad = vad
        self.noise = 25.0
        self.rms = 0.0
        self.reset()

    def reset(self):
        self.before, self.speech = deque(maxlen=15), None
        self.loud = self.voiced = self.quiet = 0

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
        self.speech.extend(frame)
        if voiced: self.voiced += 1; self.quiet = 0
        else: self.quiet += 1
        if self.quiet < 42 and len(self.speech) < 640000: return None
        data = bytes(self.speech[:640000]) if self.voiced >= 8 else None
        self.reset()
        return data

    def partial(self):
        return bytes(self.speech) if self.speech is not None and len(self.speech) >= 48000 else None

    def finish(self):
        data = bytes(self.speech[:640000]) if self.speech is not None and self.voiced>=8 else None
        self.reset(); return data


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
        self.active_until = self.muted_until = self.session_until = 0
        self.wake_detector = None
        if hasattr(portal,'root'):
            try:
                wake_configuration(portal.root)
                self.wake_detector=WakeDetector(portal.root)
            except ValueError:pass
        self.vad = None
        dependencies=Path(portal.root)/'speech-python' if hasattr(portal,'root') else None
        if dependencies and dependencies.is_dir():
            if str(dependencies) not in sys.path: sys.path.insert(0,str(dependencies))
            try:
                import webrtcvad
                self.vad = webrtcvad.Vad(2)
            except ImportError: pass
        self.events = deque(maxlen=8); self.segmenter = Segmenter(self.vad)
        self.language = 'en'
        self.status = 'Mac microphone paused'; self.issue = None
        self.busy = self.preview = False; self.recent = 0; self.last_wake = 0
        self.last_preview = 0
        self.worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix='motchi-mac-voice')

    def control(self, device, body):
        if body.get('enabled') is False:
            with self.lock:
                if self.owner == device: self.stop()
            return {'enabled': False, 'running': False, 'status': 'Mac microphone paused'}
        if body.get('enabled') is not True:
            raise ValueError('Choose whether to enable the Mac microphone.')
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
                self.issue = None; self.events.clear(); self.segmenter = Segmenter(self.vad)
                try:
                    if self.wake_detector:self.wake_detector.start()
                    self.process = subprocess.Popen([str(self.binary)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                except OSError:
                    self.owner = None; raise ValueError('The Mac microphone helper could not start.')
                threading.Thread(target=self.capture, args=(device,self.epoch,self.process), daemon=True).start()
                threading.Thread(target=self.watchdog, args=(self.process,), daemon=True).start()
            self.lease = self.clock()+25
            context = {k:body.get(k) or None for k in ('projectId','selection')}
            if context != self.context or self.language != language:
                self.portal.voice.cancel(device, self.epoch)
                self.epoch = str(uuid.uuid4()); self.session = None; self.context = context
                self.segmenter.reset()
                if self.wake_detector:self.wake_detector.clear()
            self.language = language
            if body.get('activate') is True:
                self.active_until = self.clock()+30
                self.status = "I'm listening · Mac microphone"
                self.events.append({'wake': True, 'partial': True, 'heard': '', 'text': "I'm listening. Go ahead."})
            if body.get('speaking') is True: self.muted_until = self.clock()+2
            if body.get('finish') is True and not self.busy:
                data=self.segmenter.finish()
                if data:
                    self.busy=True; self.worker.submit(self.recognize,device,self.epoch,data,False,True)
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
        return {'enabled':bool(self.owner), 'running':bool(self.process and self.process.poll() is None),
                'source':'mac', 'inputSource':'Mac microphone', 'rms':self.segmenter.rms,
                'recentRms':self.recent, 'busy':self.busy or self.preview,
                'detector':'WebRTC speech detector' if self.vad else 'Sound-level fallback',
                'utteranceSeconds':round(len(self.segmenter.speech or b'')/32000,1),
                'language':self.language,
                'wakeDetector':'Local bilingual keyword detector' if self.wake_detector else 'Local transcription wake matching',
                'wakeReady':self.wake_detector.ready if self.wake_detector else True,
                'status':self.status, 'issue':self.issue or (self.wake_detector.issue if self.wake_detector else None), 'lastWakeAt':self.last_wake,
                **(doubao_speech.info(self.portal.root) if hasattr(self.portal,'root') else {})}

    def publish_transcript(self, device, epoch, text):
        with self.lock:
            if self.owner==device and self.epoch==epoch:
                self.events.append({'wake':True,'partial':True,'heard':text,'transcript':text,'text':text,'provider':'doubao'})

    def watchdog(self, process):
        while True:
            time.sleep(1)
            with self.lock:
                if self.process is not process: return
                if self.clock() > self.lease or not self.portal.device_permitted(self.owner): self.stop(); return

    def capture(self, device, epoch, process):
        # Capture belongs to the process/device; question epochs can change
        # while the same microphone stream stays open.
        try:
            while True:
                data = process.stdout.read(640)
                if len(data) != 640: break
                with self.lock:
                    if self.process is not process or self.owner != device: return
                    if self.clock() > self.lease or not self.portal.device_permitted(device): self.stop(); return
                    if self.session and self.clock()>=self.session_until:self.session=None
                    if self.busy or self.clock() < self.muted_until:
                        self.segmenter.reset(); continue
                    if self.wake_detector:
                        keyword=self.wake_detector.feed(data)
                        if keyword and self.clock()>=self.active_until and not self.session:
                            self.active_until=self.clock()+20
                            self.segmenter.reset();self.last_wake=int(time.time()*1000)
                            self.events.append({'wake':True,'partial':True,'heard':'Hey Motchi','text':"I'm here. Ask your question."})
                        # Keep measuring audio for the waveform while idle. The
                        # small keyword model is independent of full ASR and
                        # cannot submit background speech to the answer provider.
                        if self.clock()>=self.active_until and not self.session:
                            self.segmenter.push(data);self.segmenter.reset()
                            self.recent=max(self.segmenter.rms,self.recent*.996)
                            self.status='Listening for Hey Motchi · local keyword detector' if self.wake_detector.ready else 'Starting local wake detector…'
                            continue
                    pcm = self.segmenter.push(data)
                    self.recent = max(self.segmenter.rms, self.recent*.996)
                    if self.status.startswith('Starting'): self.status = 'Listening for Hey Motchi · Mac microphone'
                    if pcm:
                        self.busy = True
                        self.worker.submit(self.recognize, device, self.epoch, pcm, False,self.clock()<self.active_until)
                    elif not self.preview and self.clock()-self.last_preview > 1.8:
                        partial = self.segmenter.partial()
                        if partial:
                            self.last_preview = self.clock()
                            self.preview = True
                            self.worker.submit(self.recognize, device, self.epoch, partial, True,self.clock()<self.active_until)
        except (OSError, ValueError): pass
        finally:
            with self.lock:
                if self.process is process:
                    message = process.stderr.read(2048).decode(errors='replace').strip() if process.poll() is not None else ''
                    self.issue = message[-400:] or 'Mac microphone stopped. Check microphone access, then try Listen now.'
                    self.status = 'Mac microphone needs attention'; self.process = None

    def recognize(self, device, epoch, pcm, preview, activated=None):
        try:
            with self.lock:
                if self.owner != device or self.epoch != epoch: return
                request = dict(self.context, operationId=str(uuid.uuid4()), generation=epoch, session=self.session,
                               action='listen', preview=preview, activated=self.clock()<self.active_until if activated is None else activated,language=self.language)
                cloud=hasattr(self.portal,'root') and doubao_speech.selected(self.portal.root)=='doubao'
                self.status = ('Recognizing with Doubao after activation…' if request['activated'] or request['session']
                               else 'Checking the wake name locally…') if cloud else 'Recognizing your speech locally…'
            job = self.portal.submit(device, request, wav_bytes(pcm))
            while job['status'] in ('queued','running'):
                time.sleep(.2)
                with self.lock:
                    if self.owner != device or self.epoch != epoch: return
                job = self.portal.job(device, request['operationId'])
            if job['status'] != 'done': raise ValueError(job.get('result',{}).get('error','Speech was not recognized. Try again.'))
            with self.lock:
                if self.owner != device or self.epoch != epoch: return
                result = job['result']
                self.issue = None
                if result.get('wake'):
                    self.session = result.get('session') if result.get('sessionSeconds',0)>0 or result.get('partial') else None
                    self.session_until=self.clock()+result.get('sessionSeconds',20) if self.session else 0
                    if not result.get('partial') and result.get('heard'):self.active_until=0
                    self.last_wake = int(time.time()*1000)
                    result['operationId'] = request['operationId']; self.events.append(result)
                    if result.get('projectId'): self.context = {k:result.get(k) for k in ('projectId','selection')}
                    # Give the calendar time to fetch/play the answer. Heartbeat
                    # renews the mute throughout playback to prevent feedback.
                    if result.get('spokenReply'): self.muted_until = self.clock()+4
        except Exception as error:
            with self.lock:
                if self.owner == device and self.epoch == epoch: self.issue = str(error)[:400]
        finally:
            with self.lock:
                if preview: self.preview = False
                else: self.busy = False; self.active_until = 0
                if self.owner == device:
                    self.status = 'Preparing your answer…' if self.busy else 'Listening for Hey Motchi · Mac microphone'

    def stop(self):
        with self.lock:
            if self.owner: self.portal.voice.cancel(self.owner,self.epoch)
            self.owner = None; self.session = None; self.context = {}; self.active_until = 0
            self.busy = self.preview = False; self.events.clear()
            if self.wake_detector:self.wake_detector.close()
            process,self.process = self.process,None
            self.status = 'Mac microphone paused'
            if process:
                process.terminate()
                try: process.wait(timeout=2)
                except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=2)

    def close(self):
        self.stop(); self.worker.shutdown(wait=False,cancel_futures=True)
