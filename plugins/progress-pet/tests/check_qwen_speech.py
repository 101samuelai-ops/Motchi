"""Local ASR process privacy/cancellation; fixtures are not accuracy tests."""
import io
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
from unittest.mock import patch
import wave
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/completion-pet/scripts'))
from qwen_speech import Recognizer,config
checks=0
def check(value,label):
 global checks
 assert value,label
 checks+=1

def wav():
 stream=io.BytesIO()
 with wave.open(stream,'wb') as out:
  out.setnchannels(1);out.setsampwidth(2);out.setframerate(16000)
  out.writeframes(b''.join(struct.pack('<h',int(1800*math.sin(n*.1))) for n in range(1600)))
 return stream.getvalue()

with tempfile.TemporaryDirectory() as temp:
 root=Path(temp);model=root/'model';model.mkdir()
 (model/'config.json').write_text('{}');(model/'model.safetensors').write_bytes(b'fixture')
 try:config(root);missing=False
 except ValueError:missing=True
 check(missing,'Missing private setup is actionable without downloading anything')
 (root/'qwen.json').write_text(json.dumps({'python':sys.executable,'model':str(model)}))
 check(config(root)[1]==model,'Runtime and model must be local absolute existing paths')
 worker=root/'fixture.py'
 worker.write_text('import sys,json,os,time\nfrom pathlib import Path\nassert os.environ["HF_HUB_OFFLINE"]=="1"\nassert os.environ["TRANSFORMERS_OFFLINE"]=="1"\nfor line in sys.stdin:\n r=json.loads(line);p=Path(r["audio"]);assert p.is_file() and p.stat().st_mode&0o777==0o600\n if r["language"]=="zh":time.sleep(5)\n print(json.dumps({"text":"English and 中文"}),flush=True)\n')
 original=subprocess.Popen
 def spawn(command,**options):return original([sys.executable,'-u',str(worker)],**options)
 recognizer=Recognizer(root)
 with patch('qwen_speech.subprocess.Popen',side_effect=spawn):
  check(recognizer.recognize(wav())=='English and 中文','Offline worker returns bilingual Unicode text')
  check(not list(root.glob('qwen-speech-*')),'Successful transcription removes temporary audio')
  first=recognizer.process
  recognizer.recognize(wav())
  check(recognizer.process is first,'Warm recognition reuses one model worker')
  calls=[0]
  def permission():
   calls[0]+=1
   if calls[0]>2:raise ValueError('Listening cancelled')
  try:recognizer.recognize(wav(),'zh',permitted=permission);cancelled=False
  except ValueError:cancelled=True
  check(cancelled and recognizer.process is None and first.poll() is not None,'Cancellation terminates the in-progress recognition worker')
  check(not list(root.glob('qwen-speech-*')),'Cancelled recognition removes temporary audio')
  try:recognizer.recognize(b'not audio');invalid=False
  except ValueError:invalid=True
  check(invalid and recognizer.process is None,'Invalid audio cannot start recognition')
 recognizer.close()
print(f'{checks} local Qwen configuration, offline process and cancellation checks passed')
