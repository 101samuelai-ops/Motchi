"""Automatic project routing must survive the next client heartbeat.

Exercises the actual Mac controller and preview transport with a fixture answer;
this verifies delivery/cancellation, not speech accuracy or provider latency.
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
import tempfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/completion-pet/scripts'))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'android'))
from mac_voice import MacVoice
from preview_live import LivePreview

checks=0
def check(value,label):
    global checks
    assert value,label
    checks+=1

class Process:
    def poll(self):return None
    def terminate(self):pass
    def wait(self,timeout=None):pass

class Portal:
    def __init__(self):
        self.voice=self;self.cancelled=[];self.error=None
        self.executor=ThreadPoolExecutor(max_workers=1)
    def cancel(self,*args):self.cancelled.append(args)
    def device_permitted(self,device):return True
    def run_mac_voice(self,device,request,audio,**extra):
        if self.error:raise ValueError(self.error)
        return {'wake':True,'heard':'How is Alpha?', 'text':'One verified task remains.',
                'projectId':'alpha','selection':'alpha-chat','projectName':'Alpha',
                'discussionTimings':{'contextMs':250,'providerMs':1000,'totalMs':1250,'other':'omit'}}
    def synthesize_mac_reply(self,*args):pass

class Connection:
    def __init__(self,voice):self.voice=voice
    def request(self,path,body=None):
        assert path=='/v1/mac-voice'
        self.voice.control('preview',body)
        return self.voice.poll('preview')
    def close(self):pass

with tempfile.TemporaryDirectory() as directory:
    portal=Portal();voice=MacVoice(portal,Path(directory)/'helper',clock=lambda:100.)
    voice.owner='preview';voice.process=Process();voice.last_frame_at=100.
    voice.context={'projectId':None,'selection':None}
    voice.activate();voice.poll('preview');epoch=voice.epoch
    preview=LivePreview(Connection(voice))
    preview.enabled=True
    try:
        voice.busy=True
        voice.recognize('preview',epoch,bytes(640),False,True,'How is Alpha?')
        check(voice.timings['discussion']=={'contextMs':250,'providerMs':1000,'totalMs':1250},
              'Voice diagnostics separate context and provider time and retain only numeric timing fields')
        check(voice.context=={'projectId':None,'selection':None},
              'Automatic project routing does not change the caller context before delivery')
        preview.call({'action':'voiceInfo'})
        events=preview.call({'action':'voiceEvents'})['events']
        check(len(events)==1 and events[0]['text']=='One verified task remains.',
              'An unselected-project heartbeat delivers the automatic project answer')
        check(voice.epoch==epoch and not portal.cancelled[-1:] == [('preview',epoch)],
              'The heartbeat cannot cancel the just-completed answer generation')
        preview.call({'action':'voiceContext','projectId':'alpha','selection':'alpha-chat'})
        # The UI may adopt the result immediately after publication, before
        # recognize() has run its final busy-flag cleanup.
        voice.busy=True
        preview.call({'action':'voiceInfo'})
        voice.busy=False
        check(voice.epoch==epoch and voice.context=={'projectId':'alpha','selection':'alpha-chat'},
              'Opening the automatically selected project adopts its exact reply without cancellation')
        voice.audio_ready('preview',epoch,dict(events[0]))
        preview.call({'action':'voiceInfo'})
        audio=preview.call({'action':'voiceEvents'})['events']
        check(len(audio)==1 and audio[0]['audioOnly'] and audio[0]['turnId']==events[0]['turnId'],
              'Delayed spoken playback still belongs to the visible answer after project adoption')
        preview.call({'action':'voiceContext','projectId':'beta','selection':'beta-chat'})
        preview.call({'action':'voiceInfo'})
        check(voice.epoch!=epoch and ('preview',epoch) in portal.cancelled,
              'An actual switch to another project still cancels the old generation')
        check(not preview.call({'action':'voiceEvents'})['events'],
              'The new project cannot receive a leftover answer')
        voice.activate();voice.poll('preview');epoch=voice.epoch
        portal.error='The project answer service timed out. Try again.';voice.busy=True
        voice.recognize('preview',epoch,bytes(640),False,True,'项目进度怎么样？')
        preview.call({'action':'voiceInfo'})
        failed=preview.call({'action':'voiceEvents'})['events']
        check(len(failed)==1 and failed[0]['failed'] and failed[0]['transcript']=='项目进度怎么样？',
              'A failed answer is an explicit main-stage result with the recognized question')
        check(not voice.busy and voice.active_until==0 and voice.issue==portal.error,
              'Provider failure ends capture of this question instead of listening forever')
    finally:
        preview.server.server_close();preview.close();voice.close();portal.executor.shutdown(wait=True)

print(f'{checks} automatic-project voice handoff, playback and failure checks passed')
