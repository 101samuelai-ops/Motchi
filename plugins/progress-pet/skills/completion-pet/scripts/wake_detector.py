"""Optional local streaming keyword detector; ambient PCM is never archived."""
import json
import hashlib
from pathlib import Path
import queue
import subprocess
import threading
import time

VAD_REVISION='bfdc0193023f121ea5b3cc7b176dbed570a68a59'
VAD_SHA256='1a153a22f4509e292a94e67d6f9b85e8deb25b4988682b7e174c65279d8788e3'


def configuration(root):
    try:
        value=json.loads((Path(root)/'wake.json').read_text())
        python,model=Path(value['python']),Path(value['model'])
        if not python.is_absolute() or not python.is_file() or not model.is_absolute():raise ValueError()
        for name in ('encoder-epoch-13-avg-2-chunk-16-left-64.int8.onnx','decoder-epoch-13-avg-2-chunk-16-left-64.onnx','joiner-epoch-13-avg-2-chunk-16-left-64.int8.onnx','tokens.txt','motchi-keywords.txt'):
            if not (model/name).is_file():raise ValueError()
        return python,model
    except (OSError,KeyError,TypeError,ValueError):
        raise ValueError('Local wake detector is not configured.') from None


class WakeDetector:
    def __init__(self,root):
        self.root=Path(root);self.process=None;self.ready=False;self.issue=None
        self.events=queue.Queue(maxsize=2)
        self.frames=queue.Queue(maxsize=120)  # At most 2.4 seconds, RAM only.
        self.started=threading.Event()
        self.speech_ready=False;self.probability=None;self.probability_at=0

    def start(self):
        if self.process and self.process.poll() is None:return
        python,model=configuration(self.root)
        self.ready=False;self.issue=None
        self.speech_ready=False;self.probability=None;self.probability_at=0
        self.started=threading.Event()
        self.frames=queue.Queue(maxsize=120)
        command=[str(python),'-u',str(Path(__file__).with_name('wake_worker.py')),str(model)]
        settings=json.loads((self.root/'wake.json').read_text()) if (self.root/'wake.json').is_file() else {}
        if settings.get('vadModel'):
            vad=Path(settings['vadModel'])
            if not vad.is_absolute() or settings.get('vadSha256')!=VAD_SHA256 or hashlib.sha256(vad.read_bytes()).hexdigest()!=VAD_SHA256:
                raise ValueError('Local speech detector checksum does not match its pinned model.')
            command.append(str(vad))
        self.process=subprocess.Popen(command,
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
        process,frames,started=self.process,self.frames,self.started
        def receive():
            try:
                for line in process.stdout:
                    if len(line)>2048:break
                    value=json.loads(line)
                    if self.process is not process:return
                    if value.get('ready'):
                        self.ready=True;self.speech_ready=value.get('speechReady') is True;started.set()
                    probability=value.get('speechProbability')
                    if type(probability) in (int,float) and 0<=probability<=1:
                        self.probability=probability;self.probability_at=time.monotonic()
                    if value.get('keyword'):
                        try:self.events.put_nowait(value['keyword'])
                        except queue.Full:pass
            except (OSError,ValueError):pass
            finally:
                if self.process is process:self.ready=False;self.issue='Wake detector stopped. Tap Talk or restart listening.'
        threading.Thread(target=receive,daemon=True,name='motchi-wake-detector').start()
        def send():
            # Model loading must not discard the wake spoken during startup,
            # and pipe pressure must never block the microphone's audio reader.
            try:
                while self.process is process and process.poll() is None:
                    if not started.wait(.1):continue
                    try:frame=frames.get(timeout=.1)
                    except queue.Empty:continue
                    if self.process is not process:return
                    process.stdin.write(frame);process.stdin.flush()
            except (BrokenPipeError,OSError,ValueError):
                if self.process is process:self.issue='Wake detector input interrupted. Tap Talk or restart listening.'
        threading.Thread(target=send,daemon=True,name='motchi-wake-audio').start()

    def feed(self,frame):
        if not self.process or self.process.poll() is not None:return None
        try:self.frames.put_nowait(frame)
        except queue.Full:
            try:self.frames.get_nowait()
            except queue.Empty:pass
            try:self.frames.put_nowait(frame)
            except queue.Full:pass
        try:return self.events.get_nowait()
        except queue.Empty:return None

    def clear(self):
        while not self.frames.empty():
            try:self.frames.get_nowait()
            except queue.Empty:break
        while not self.events.empty():
            try:self.events.get_nowait()
            except queue.Empty:break

    def speech(self):
        if self.speech_ready and self.probability is not None and time.monotonic()-self.probability_at<.3:
            return self.probability>=.55
        return None  # Never trust a stalled detector's last speech decision.

    def close(self):
        process,self.process=self.process,None;self.ready=False;self.speech_ready=False;self.probability=None;self.clear()
        self.started.set()
        if process:
            try:process.terminate();process.wait(timeout=2)
            except (OSError,subprocess.TimeoutExpired):
                try:process.kill();process.wait(timeout=2)
                except OSError:pass
