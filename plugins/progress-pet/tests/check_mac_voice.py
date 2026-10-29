"""Mac fallback: bounded segmentation, microphone ownership, lease and pause."""
import io
from pathlib import Path
import queue
import struct
import sys
import tempfile
import time
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/completion-pet/scripts'))
from mac_voice import MacVoice, Segmenter, wav_bytes
checks=0
def check(value,label):
    global checks
    assert value,label
    checks+=1
def rejects(fn):
    try:fn();return False
    except ValueError:return True
def frame(n):return struct.pack('<h',n)*320
segmenter=Segmenter()
check(all(segmenter.push(frame(3)) is None for _ in range(200)), 'Quiet background is not submitted')
for _ in range(90): segmenter.push(frame(300))
check(segmenter.partial() and len(segmenter.partial())>48000, 'Speech has a bounded live preview')
final=None
for _ in range(42): final=segmenter.push(frame(3)) or final
check(final and not segmenter.partial(), 'A pause emits the final recording and clears live audio')
check(wav_bytes(final)[:4]==b'RIFF','Mac capture supplies the same local WAV transport')
class SpeechDetector:
    def __init__(self):self.speaking=True
    def is_speech(self,frame,rate):return self.speaking
detector=SpeechDetector();speech=Segmenter(detector)
for _ in range(90):speech.push(frame(120))
detector.speaking=False
ended=None
for _ in range(42):ended=speech.push(frame(800)) or ended
check(ended is not None,'The speech detector ends a question even when background sound stays loud')
detector.speaking=True
for _ in range(90):speech.push(frame(120))
check(speech.finish() and not speech.partial(),'Finish question flushes captured speech without waiting for silence')

class Frames:
    def __init__(self):self.queue=queue.Queue();self.closed=False
    def read(self,size):
        while not self.closed:
            try:return self.queue.get(timeout=.05)
            except queue.Empty:pass
        return b''
class Child:
    def __init__(self):self.stdout=Frames();self.stderr=io.BytesIO();self.dead=False
    def poll(self):return 0 if self.dead else None
    def terminate(self):self.dead=True;self.stdout.closed=True
    def kill(self):self.terminate()
    def wait(self,timeout=None):return 0
class Portal:
    def __init__(self):self.voice=self;self.cancelled=[];self.requests=[];self.permitted=True
    def cancel(self,*args):self.cancelled.append(args)
    def device_permitted(self,device):return self.permitted
    def submit(self,device,request,audio):
        self.requests.append(request)
        return {'id':request['operationId'],'status':'done','result':{'wake':True,'partial':request['preview'],'heard':'How is Alpha?','text':'A local answer','session':'test-session'}}

with tempfile.TemporaryDirectory() as root:
    binary=Path(root)/'MacMicrophone';binary.touch();portal=Portal();now=[100.0];child=Child()
    with patch('mac_voice.subprocess.Popen',return_value=child):
        voice=MacVoice(portal,binary,clock=lambda:now[0])
        initial=voice.control('calendar',{'enabled':True,'projectId':'alpha','selection':'alpha-chat','activate':True})
        check(initial['inputSource']=='Mac microphone' and initial['running'],'The source is explicit and the microphone process starts')
        check(voice.poll('calendar')['events'][0]['partial'],'Listen now immediately acknowledges on the calendar')
        check(not voice.poll('another')['enabled'],'Another device cannot read the microphone state or transcript')
        check(rejects(lambda:voice.control('another',{'enabled':True})),'A second device cannot hijack microphone capture')
        check(not voice.control('another',{'enabled':False})['enabled'] and not child.dead,'Another device cannot stop the owner’s microphone')
        voice.recognize('calendar',voice.epoch,frame(300)*90,True)
        request=portal.requests[-1]
        check(request['projectId']=='alpha' and request['selection']=='alpha-chat' and request['preview'] and request['activated'],
              'Live Mac speech retains the exact project context and explicit activation')
        check(voice.poll('calendar')['events'][0]['heard']=='How is Alpha?','Addressed live text reaches only the owning calendar')
        previous=voice.epoch
        voice.control('calendar',{'enabled':True,'projectId':'beta','selection':'beta-chat'})
        check(voice.epoch!=previous and voice.session is None and voice.process is child and ('calendar',previous) in portal.cancelled,
              'A project switch cancels the old question session while retaining the microphone')
        voice.stop()
        check(child.dead and portal.cancelled and not voice.owner,'Pause terminates capture and cancels in-flight questions')
        voice.close()
    child=Child()
    with patch('mac_voice.subprocess.Popen',return_value=child):
        voice=MacVoice(portal,binary,clock=lambda:now[0]);voice.control('calendar',{'enabled':True})
        now[0]+=26
        for _ in range(25):
            if child.dead:break
            time.sleep(.05)
        check(child.dead and not voice.owner,'A missing calendar heartbeat stops capture even when the input pipe stalls')
        voice.close()
    class Keywords:
        ready=True;issue=None
        def __init__(self,at=None):self.count=0;self.at=at
        def feed(self,data):
            self.count+=1
            return 'HEY_MOTCHI' if self.count==self.at else None
        def close(self):pass
    def capture_with_keywords(at,expired=False):
        voice=MacVoice(portal,binary,clock=lambda:100.0);child=Child()
        child.stdout=io.BytesIO(frame(300)*100+frame(0)*50)
        voice.owner='calendar';voice.lease=200;voice.process=child;voice.epoch='test-epoch'
        voice.wake_detector=Keywords(at)
        if expired:voice.session='stale-session';voice.session_until=99
        calls=[]
        with patch.object(voice.worker,'submit',side_effect=lambda *args:calls.append(args)):
            voice.capture('calendar',voice.epoch,child)
        events=list(voice.events);session=voice.session;voice.close()
        return calls,events,session
    calls,events,_=capture_with_keywords(None)
    check(not calls and not events,'Idle keyword listening does not run full ASR on background speech')
    calls,events,_=capture_with_keywords(10)
    check(events and events[0]['wake'] and events[0]['partial'],'A keyword acknowledges immediately without waiting for transcription')
    check(calls and all(call[-1] is True for call in calls),'Only keyword-activated audio reaches the full question recognizer')
    calls,events,session=capture_with_keywords(None,expired=True)
    check(not calls and session is None,'An expired pending question returns to keyword-only listening')
print(f'{checks} Mac microphone ownership, live text, segmentation and disconnect checks passed')
