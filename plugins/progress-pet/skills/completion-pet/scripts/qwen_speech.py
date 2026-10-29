"""Offline Qwen3-ASR on Apple Silicon; no cloud audio or automatic downloads."""
import atexit
import json
import os
from pathlib import Path
import queue
import subprocess
import tempfile
import threading
import time
from doubao_speech import pcm_from_wav


def config(root):
    try:
        value=json.loads((Path(root)/'qwen.json').read_text())
        python,model=Path(value['python']),Path(value['model'])
        if not python.is_absolute() or not python.is_file() or not model.is_absolute() or not (model/'config.json').is_file() or not list(model.glob('*.safetensors')):
            raise ValueError()
        return python,model
    except (OSError,ValueError,KeyError,TypeError):
        raise ValueError('Install the free local Qwen3-ASR runtime and model on your Mac first.') from None


class Recognizer:
    def __init__(self,root):
        self.root=Path(root);self.lock=threading.Lock();self.process=None;self.responses=None
        atexit.register(self.close)

    def start(self):
        if self.process and self.process.poll() is None:return
        python,model=config(self.root)
        env={**os.environ,'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','TOKENIZERS_PARALLELISM':'false'}
        self.process=subprocess.Popen([str(python),'-u',str(Path(__file__).with_name('qwen_worker.py')),str(model)],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,env=env)
        self.responses=queue.Queue();process,responses=self.process,self.responses
        def receive():
            try:
                for line in process.stdout:
                    if len(line)>20000:break
                    responses.put(json.loads(line))
            except (OSError,ValueError):pass
            finally:responses.put({'error':'Local Qwen speech worker stopped.'})
        threading.Thread(target=receive,daemon=True,name='motchi-qwen-results').start()

    def recognize(self,audio,language='auto',permitted=lambda:None):
        pcm_from_wav(audio)
        if language not in ('en','zh','auto'):raise ValueError('Choose a supported speech language.')
        with self.lock:
            permitted();self.start()
            with tempfile.TemporaryDirectory(prefix='qwen-speech-',dir=self.root) as directory:
                source=Path(directory)/'question.wav';source.write_bytes(audio);source.chmod(0o600)
                try:
                    self.process.stdin.write(json.dumps({'audio':str(source),'language':language})+'\n');self.process.stdin.flush()
                    deadline=time.monotonic()+90
                    while time.monotonic()<deadline:
                        permitted()
                        try:result=self.responses.get(timeout=.2)
                        except queue.Empty:continue
                        if result.get('error'):raise ValueError(result['error'])
                        text=result.get('text','')
                        if not isinstance(text,str) or not text.strip():raise ValueError('No clear speech recognized. Speak near your Mac and try again.')
                        return text.strip()[:3000]
                    raise ValueError('Local speech recognition timed out. Try a shorter question.')
                except BaseException:
                    self.close();raise

    def close(self):
        process,self.process=self.process,None
        if process:
            try:process.terminate();process.wait(timeout=2)
            except (OSError,subprocess.TimeoutExpired):
                try:process.kill();process.wait(timeout=2)
                except OSError:pass
