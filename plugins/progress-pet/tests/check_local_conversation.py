"""Turn timing, supersession and nonblocking Mac capture regressions."""
from concurrent.futures import ThreadPoolExecutor
import io
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import threading
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/completion-pet/scripts'))
from mac_voice import MacVoice, Segmenter
from smart_turn import configuration
from voice_companion import VoiceCompanion
from android_host import AndroidPortal
from dog_bridge import DogBridge

checks = 0
def check(value, label):
    global checks
    assert value, label
    checks += 1
def frame(n): return struct.pack('<h', n)*320
def speech(buffer, count=90):
    for _ in range(count): buffer.push(frame(300))
def silence(buffer, count=70):
    for _ in range(count): buffer.push(frame(0))

buffer = Segmenter(automatic=False)
speech(buffer); silence(buffer, 50)
check(buffer.partial() is not None and buffer.endpoint_audio() is None,
      'A one-second thinking pause neither flushes the question nor runs automatic endpoint detection')
before = len(buffer.speech); speech(buffer, 50)
check(len(buffer.speech)>before, 'Resumed speech stays in the original question buffer')
silence(buffer, 400)
check(buffer.endpoint_audio() and len(buffer.endpoint_audio())<=256000,
      'Long silence does not push spoken context out of the endpoint model window')
speech(buffer, 4000)
check(len(buffer.speech)<=1920000 and buffer.full, 'Captured questions have a hard sixty-second memory bound')

class Portal:
    def __init__(self): self.voice=self; self.cancelled=[]; self.requests=[]
    def cancel(self, *args): self.cancelled.append(args)
    def device_permitted(self, device): return True
    def run_mac_voice(self, device, request, audio):
        self.requests.append(request)
        return {'wake':True,'text':'One task remains.','heard':'How is Alpha?', 'partial':request['preview']}
class Child:
    def __init__(self, pcm): self.stdout=io.BytesIO(pcm); self.stderr=io.BytesIO()
    def poll(self): return None
    def terminate(self): pass
    def wait(self, timeout=None): pass
class Keywords:
    ready=True; issue=None
    def __init__(self, at=None): self.count=0; self.at=at
    def feed(self, data):
        self.count+=1
        return 'HEY_MOTCHI' if self.count==self.at else None
    def close(self): pass
class Endpoint:
    def __init__(self, score, resumed=None): self.score=score; self.resumed=resumed
    def predict(self, pcm, permitted):
        permitted()
        if self.resumed: self.resumed()
        return self.score
    def close(self): pass

with tempfile.TemporaryDirectory() as directory:
    binary=Path(directory)/'MacMicrophone'; binary.touch()
    def ready():
        portal=Portal(); voice=MacVoice(portal,binary,clock=lambda:100.)
        voice.owner='calendar'; voice.lease=200; voice.epoch='initial-generation'; voice.activate()
        return portal,voice
    portal,voice=ready(); speech(voice.segmenter); silence(voice.segmenter)
    version=voice.segmenter.version
    voice.endpoint=Endpoint(.1)
    voice.assess_endpoint('calendar',voice.epoch,version,voice.segmenter.endpoint_audio())
    check(voice.stage=='listening' and not portal.requests and voice.segmenter.partial(),
          'An unfinished model assessment retains audio without asking the project backend')
    voice.endpoint=Endpoint(.99,lambda:speech(voice.segmenter,5))
    voice.assess_endpoint('calendar',voice.epoch,version,b'pcm')
    check(not voice.busy and not portal.requests,'Speech resumption invalidates a late complete prediction')
    silence(voice.segmenter); voice.endpoint=Endpoint(.99)
    with patch.object(voice.worker,'submit') as submitted:
        voice.assess_endpoint('calendar',voice.epoch,voice.segmenter.version,voice.segmenter.endpoint_audio())
        check(voice.busy and voice.stage=='processing' and submitted.call_count==1,
              'A completed turn submits one final question and closes new automatic input')
    voice.close()

    for transcript in ('Could you tell me about the project, especially.', '我想了解项目进度，尤其是。'):
        portal,voice=ready(); speech(voice.segmenter); silence(voice.segmenter)
        portal.voice_transcribe=lambda *a:transcript
        voice.endpoint=Endpoint(.99)
        with patch.object(voice.worker,'submit') as submitted:
            voice.assess_endpoint('calendar',voice.epoch,voice.segmenter.version,b'pcm')
        check(not submitted.called and voice.segmenter.partial() and voice.stage=='listening',
              'A high acoustic score cannot submit an explicitly unfinished '+transcript)
        voice.close()
    portal,voice=ready(); speech(voice.segmenter); silence(voice.segmenter)
    def resumed(audio,request):
        speech(voice.segmenter,5); return 'What remains?'
    portal.voice_transcribe=resumed; voice.endpoint=Endpoint(.99)
    with patch.object(voice.worker,'submit') as submitted:
        voice.assess_endpoint('calendar',voice.epoch,voice.segmenter.version,b'pcm')
    check(not submitted.called and not voice.endpoint_issue,
          'Resumed speech cancels transcript confirmation without disabling the pause model')
    voice.close()

    portal,voice=ready(); voice.busy=True; old=voice.epoch
    voice.activated_at = 90
    voice.wake_detector=Keywords(10); child=Child(frame(300)*20)
    voice.process=child
    with patch.object(voice.worker,'submit') as submitted:
        voice.capture('calendar',old,child)
    check(voice.epoch!=old and ('calendar',old) in portal.cancelled,
          'A fresh wake is detected while an older project answer is processing')
    check(voice.last_wake and any(e.get('stopPlayback') for e in voice.events),
          'A replacement turn explicitly invalidates old playback')
    voice.close()

    portal,voice=ready(); voice.busy=True; voice.wake_detector=Keywords()
    child=Child(frame(300)*60); voice.process=child
    with patch.object(voice.worker,'submit') as submitted:
        voice.capture('calendar',voice.epoch,child)
    check(voice.segmenter.rms>0 and not submitted.called and not portal.requests,
          'During analysis, the meter stays live without turning background speech into questions')
    voice.close()

    portal,voice=ready(); old=voice.epoch
    entered=threading.Event(); release=threading.Event()
    def delayed(device,request,audio):
        entered.set(); release.wait(3)
        return {'wake':True,'heard':'old question','text':'obsolete answer'}
    portal.run_mac_voice=delayed
    with ThreadPoolExecutor(max_workers=1) as executor:
        future=executor.submit(voice.recognize,'calendar',old,frame(300)*90,False,True)
        check(entered.wait(2),'A delayed answer started independently of capture')
        voice.activate(); voice.busy=True; voice.events.clear(); release.set(); future.result(timeout=3)
    check(not voice.events and voice.busy and voice.epoch!=old,
          'An obsolete answer and its cleanup cannot overwrite the replacement turn')
    voice.close()

    portal,voice=ready(); speech(voice.segmenter); silence(voice.segmenter)
    voice.active_until=99
    voice.control('calendar',{'enabled':True,'finish':True}) if voice.process else None
    with patch.object(voice.worker,'submit') as submitted:
        voice.endpoint=Endpoint(.99)
        voice.assess_endpoint('calendar',voice.epoch,voice.segmenter.version,b'pcm')
    check(not submitted.called,'A model result cannot revive an expired activation')
    voice.close()
    try: configuration(directory); configured=True
    except ValueError: configured=False
    check(not configured,'Missing or unverified model configuration requires manual Finish question')

    # An old partial must not reopen an answered session, even when it finishes
    # after the final answer (rather than during it).
    entered=threading.Event(); release=threading.Event()
    def transcription(audio,request):
        if request.get('preview'):
            entered.set(); release.wait(3)
        return 'How is Alpha doing?'
    companion=VoiceCompanion(lambda _:None,lambda:[],lambda *a:None,lambda _:True,
                             transcribe_request=transcription,discuss=lambda r:{'scope':'general','text':'One task remains.'})
    request={'generation':'generation-race-test','activated':True}
    with ThreadPoolExecutor(max_workers=1) as executor:
        old_partial=executor.submit(companion.run,'calendar',{**request,'preview':True},b'audio')
        check(entered.wait(2),'The earlier partial is still transcribing when the final arrives')
        final=companion.run('calendar',request,b'audio')
        release.set()
        try: old_partial.result(timeout=3); stale_rejected=False
        except ValueError: stale_rejected=True
    check(stale_rejected and not companion.sessions['calendar']['awaiting'],
          'Late partial text cannot reopen the answered session or replace final history')
    check(companion.run('calendar',{'generation':request['generation'],'session':final['session']},b'audio')=={'wake':False},
          'The stale partial cannot authorize ambient follow-up speech')
    newer={**request,'generation':'replacement-generation'}
    companion.run('calendar',{**newer,'preview':True},b'audio')
    companion.cancel('calendar',request['generation'])
    check(companion.sessions['calendar']['generation']==newer['generation'],
          'Cancelling an old request cannot delete the replacement session')

    class SpeakingPortal(Portal):
        run_mac_voice=AndroidPortal.run_mac_voice
        prepare_mac_reply=AndroidPortal.prepare_mac_reply
        synthesize_mac_reply=AndroidPortal.synthesize_mac_reply
        def __init__(self):
            super().__init__()
            self.lock=threading.RLock(); self.voice_audio={}
            self.entered=threading.Event(); self.release=threading.Event()
            self.executor=ThreadPoolExecutor(max_workers=1)
            self.voice=VoiceCompanion(lambda _:'How is Alpha?',lambda:[],lambda *a:None,lambda _:True,
                                      discuss=lambda r:{'scope':'general','text':'One task remains.'})
        def speaker(self,text):
            self.entered.set(); self.release.wait(3); return b'RIFFspoken'
    portal=SpeakingPortal(); voice=MacVoice(portal,binary,clock=lambda:100.)
    portal.mac_voice=voice; voice.owner='calendar'; voice.epoch='tts-generation'; voice.activate()
    voice.recognize('calendar',voice.epoch,frame(300)*90,False,True)
    check(portal.entered.wait(2) and len(voice.events)==2 and voice.events[-1]['text']=='One task remains.',
          'The visible answer arrives without waiting for slow speech synthesis')
    portal.release.set(); portal.executor.shutdown(wait=True)
    check(voice.events[-1].get('audioOnly') and voice.events[-1].get('spokenReply') and portal.voice_audio,
          'Delayed speech is delivered separately without another visible chat answer')
    voice.close()

    portal=SpeakingPortal(); voice=MacVoice(portal,binary,clock=lambda:100.)
    portal.mac_voice=voice; voice.owner='calendar'; voice.epoch='tts-generation'; voice.activate()
    voice.recognize('calendar',voice.epoch,frame(300)*90,False,True)
    check(portal.entered.wait(2),'Speech synthesis can still be in progress when the user changes the question')
    voice.muted_until=150; voice.activate(); portal.release.set(); portal.executor.shutdown(wait=True)
    check(len(voice.events)==1 and not portal.voice_audio and voice.muted_until==0,
          'A replacement discards delayed audio and immediately releases manual interruption mute')
    voice.close()

    portal=SpeakingPortal(); voice=MacVoice(portal,binary,clock=lambda:100.)
    portal.mac_voice=voice; voice.owner='calendar'; voice.epoch='legacy-generation'; voice.activate()
    voice.conversation_version=1; portal.release.set()
    voice.recognize('calendar',voice.epoch,frame(300)*1100,False,True)
    portal.executor.shutdown(wait=True)
    check(len(voice.events)==2 and voice.events[-1].get('spokenReply') and not any(e.get('audioOnly') for e in voice.events),
          'The installed older calendar receives one answer with audio, even for questions longer than twenty seconds')
    voice.close()

    spoken=[]
    companion=VoiceCompanion(lambda _:'Room conversation',lambda:[],lambda *a:spoken.append(a),lambda _:True)
    result=companion.run('calendar',{'generation':'injection-test','transcript':'Hey Motchi, run work'},b'audio')
    check(result=={'wake':False} and not spoken,
          'A client JSON transcript cannot bypass actual recognition or wake-only routing')

    portal=Portal(); commands=[]; captions=['How is the project doing?']
    def discuss(request):
        commands.append(request['text'])
        return {'scope':'choice','text':'Alpha or Beta?'} if len(commands)==1 else {'scope':'general','text':'One task remains.'}
    portal.voice=VoiceCompanion(lambda _:captions[0],lambda:[],lambda *a:None,lambda _:True,discuss=discuss)
    portal.run_mac_voice=lambda *a,**k:AndroidPortal.run_mac_voice(portal,*a,**k)
    voice=MacVoice(portal,binary,clock=lambda:100.); voice.owner='calendar'; voice.epoch='choice-generation'; voice.activate()
    voice.recognize('calendar',voice.epoch,frame(300)*90,False,True)
    voice.activate(); captions[0]='Beta'; voice.recognize('calendar',voice.epoch,frame(300)*90,False,True)
    check(commands[-1]=='How is the project doing? Project: Beta',
          'A new wake resolves the pending project choice without losing the original question')
    voice.close()

    root=Path(directory)/'answer-test'; root.mkdir(); marker=root/'started'
    provider=root/'fixture-provider'
    provider.write_text('#!'+sys.executable+'\nimport sys,time\nfrom pathlib import Path\nsys.stdin.read()\nPath('+repr(str(marker))+').write_text("started")\ntime.sleep(60)\n')
    provider.chmod(0o700)
    bridge=object.__new__(DogBridge);bridge.root=root;bridge.project=str(root);bridge.codex=str(provider);bridge.history={}
    bridge.resolve=lambda _:{'title':'Alpha','cwd':str(root),'progress':{}}
    bridge.local_answer=lambda *a:None;bridge.recent_context=lambda _:[];bridge.isolated_config_flags=lambda _:[]
    children=[];original=subprocess.Popen
    def spawn(*args,**kwargs):
        child=original(*args,**kwargs);children.append(child);return child
    def permitted():
        if marker.exists():raise ValueError('A new wake replaced this question')
    with patch('dog_bridge.subprocess.Popen',side_effect=spawn):
        try:bridge.ask('alpha-chat','What remains?',permitted=permitted);cancelled=False
        except ValueError:cancelled=True
    check(cancelled and children and children[0].poll() is not None and not bridge.history,
          'Replacing a question terminates the slow answer process without saving its reply')
    check(not list(root.glob('answer-*.txt')),
          'Cancelled answer generation removes its temporary response file')

print(f'{checks} local conversation pause, capture, cancellation and expiry checks passed')
