"""Early/quiet PCM and name-only activation, without recording a microphone."""
from array import array
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/completion-pet/scripts'))
from mac_voice import InputLevel,Segmenter
from wake_detector import WakeDetector
from voice_companion import addressed

checks=0
def check(value,label):
    global checks
    assert value,label
    checks+=1
def pcm(value):return array('h',[value]*320).tobytes()

gain=InputLevel()
check(gain.apply(pcm(0))==pcm(0),'Digital silence stays silent')
check(max(array('h',gain.apply(pcm(100))))>=700,'Quiet speech is amplified before wake and VAD, including its first frame')
check(gain.apply(pcm(16000))==pcm(16000),'Ordinary loud speech is not attenuated or distorted')
mixed=array('h',[32000,-32000]+[100]*318)
result=array('h',gain.apply(mixed.tobytes()))
check(result==mixed and max(result)<=32767 and min(result)>=-32768,'Loud peaks cannot clip through input gain')
for _ in range(1000):gain.apply(pcm(1))
check(gain.gain<=8,'Quiet-room noise cannot produce unlimited gain')
for text,wanted in [('Mochi, how is Alpha?','how is Alpha?'),('Hi Moki!',''),
                    ('请问莫奇，项目进度怎么样？','请问 项目进度怎么样？'),
                    ('What is finished, Moji?','What is finished'),('默契','')]:
    check(addressed(text)==wanted,'Name-only or similar pronunciation: '+text)
check(addressed('The weather is pleasant') is None and addressed('Mochington') is None,
      'Unrelated speech and longer name prefixes remain unaddressed')
class AlwaysSpeech:
    def is_speech(self,*_):return True
segment=Segmenter(AlwaysSpeech(),automatic=False)
for _ in range(80):segment.push(pcm(300),voiced=True)
for _ in range(60):segment.push(pcm(800),voiced=False)
check(segment.quiet==60 and segment.endpoint_audio(),
      'The neural speech/noise decision can expose a real pause despite loud input and a permissive older VAD')

with tempfile.TemporaryDirectory(prefix='motchi-wake-ready-') as directory:
    root=Path(directory);flag=root/'ready';worker=root/'worker.py'
    worker.write_text('''import json,sys,time
from pathlib import Path
flag=Path(sys.argv[1])
while not flag.exists():time.sleep(.01)
print(json.dumps({'ready':True}),flush=True)
while True:
 frame=sys.stdin.buffer.read(640)
 if len(frame)!=640:break
 if any(frame):print(json.dumps({'keyword':'MOTCHI'}),flush=True)
''')
    original=subprocess.Popen
    def spawn(command,**options):return original([sys.executable,'-u',str(worker),str(flag)],**options)
    detector=WakeDetector(root)
    with patch('wake_detector.configuration',return_value=(Path(sys.executable),root)),patch('wake_detector.subprocess.Popen',side_effect=spawn):
        detector.start()
        check(not detector.ready,'A loading keyword worker cannot claim readiness')
        detector.feed(pcm(300))
        flag.touch()
        found=None;deadline=time.monotonic()+3
        while time.monotonic()<deadline and not found:
            found=detector.feed(pcm(0));time.sleep(.01)
        check(found=='MOTCHI','A wake spoken during model loading is queued and recognized after readiness')
        first=detector.process
        detector.start()
        check(detector.process is first,'Repeated enable reuses the ready keyword process')
        detector.close()
        check(first.poll() is not None and detector.frames.empty() and detector.events.empty(),
              'Pause terminates the worker and clears queued microphone audio and wake events')
    # Feeding a stalled model must stay bounded and cannot block capture.
    class Stalled:
        def poll(self):return None
    detector=WakeDetector(root);detector.process=Stalled()
    started=time.monotonic()
    for _ in range(10000):detector.feed(pcm(20))
    check(time.monotonic()-started<1 and detector.frames.qsize()<=120,
          'A stalled wake worker cannot block capture or retain more than 2.4 seconds')
    detector.speech_ready=True;detector.probability=.9;detector.probability_at=time.monotonic()
    check(detector.speech() is True,'A fresh neural speech decision is available to the turn controller')
    detector.probability=.1
    check(detector.speech() is False,'Background noise can keep the meter moving while the turn controller sees a pause')
    detector.probability_at-=1
    check(detector.speech() is None,'An old speech decision cannot keep a stalled question open')
    detector.process=None
print(f'{checks} early audio, bounded gain, name-only wake and queue checks passed')
