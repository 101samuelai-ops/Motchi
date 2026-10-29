"""Optional local streaming keyword detector; ambient PCM is never archived."""
import json
import os
from pathlib import Path
import queue
import subprocess
import threading


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

    def start(self):
        if self.process and self.process.poll() is None:return
        python,model=configuration(self.root)
        self.ready=False;self.issue=None
        self.process=subprocess.Popen([str(python),'-u',str(Path(__file__).with_name('wake_worker.py')),str(model)],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
        os.set_blocking(self.process.stdin.fileno(),False)
        process=self.process
        def receive():
            try:
                for line in process.stdout:
                    if len(line)>2048:break
                    value=json.loads(line)
                    if self.process is not process:return
                    if value.get('ready'):self.ready=True
                    if value.get('keyword'):
                        try:self.events.put_nowait(value['keyword'])
                        except queue.Full:pass
            except (OSError,ValueError):pass
            finally:
                if self.process is process:self.ready=False;self.issue='Wake detector stopped. Tap Talk or restart listening.'
        threading.Thread(target=receive,daemon=True,name='motchi-wake-detector').start()

    def feed(self,frame):
        if not self.process or self.process.poll() is not None:return None
        if self.ready:
            try:
                if os.write(self.process.stdin.fileno(),frame)!=len(frame):raise OSError('Short wake input')
            except (BlockingIOError,BrokenPipeError,OSError):
                self.issue='Wake detector input interrupted. Tap Talk or restart listening.'
                return None
        try:return self.events.get_nowait()
        except queue.Empty:return None

    def clear(self):
        while not self.events.empty():
            try:self.events.get_nowait()
            except queue.Empty:break

    def close(self):
        process,self.process=self.process,None;self.ready=False;self.clear()
        if process:
            try:process.terminate();process.wait(timeout=2)
            except (OSError,subprocess.TimeoutExpired):
                try:process.kill();process.wait(timeout=2)
                except OSError:pass
