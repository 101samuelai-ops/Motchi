"""App lifetime, local mirror, explicit pause and playback ownership regressions."""
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/completion-pet/scripts'))
from desktop_voice import DesktopVoice, DEVICE
import microphone_policy


class Voice:
    def __init__(self):
        self.lock=threading.RLock();self.owner=None;self.lease=0
        self.playback_active=False;self.playback_ticket=None;self.calls=[]
        self.process=None;self.context={};self.language='auto'
    def clock(self): return 100
    def control(self, owner, body):
        self.calls.append((owner,body));self.owner=owner
        self.process=SimpleNamespace(poll=lambda:None)
    def snapshot(self):
        return dict(enabled=bool(self.owner),running=bool(self.owner),turnId='current')
    def stop(self): self.owner=None;self.process=None


with tempfile.TemporaryDirectory() as temporary:
    voice=Voice();messages=[]
    portal=SimpleNamespace(root=Path(temporary),mac_voice=voice,voice_audio={},lock=threading.RLock(),closed=False)
    portal.device_permitted=lambda d:d in (DEVICE,'preview','calendar')
    desktop=DesktopVoice(portal,messages.append)
    desktop.tick();assert not voice.owner,'New installation is opt-in'
    desktop.set_enabled(True);desktop.tick()
    assert voice.owner==DEVICE and len(voice.calls)==1,'App starts capture without a browser'
    desktop.tick();assert len(voice.calls)==1 and voice.lease==125,'App renews the existing microphone without restarting it'
    voice.process=SimpleNamespace(poll=lambda:1)
    desktop.tick();assert len(voice.calls)==1,'Failed capture retries are bounded'
    desktop.retry_at=0;desktop.tick()
    assert len(voice.calls)==2 and voice.owner==DEVICE,'A failed helper restarts after authorization resolves'
    desktop.poll('preview')
    desktop.publish(dict(turnId='current',ready=True,partial=True,text='Listening'))
    desktop.tick()
    assert messages[-1]['events'][0]['ready'],'Native popup receives wake event'
    assert desktop.poll('preview')['events'][0]['ready'],'Native delivery does not consume preview event'
    assert not desktop.poll('preview')['events'],'Preview receives each event once'
    desktop.publish(dict(turnId='obsolete',text='Old reply'))
    desktop.tick();assert not messages[-1]['events'] and not desktop.poll('preview')['events'],'Old turns are not replayed'
    desktop.poll('preview',dict(enabled=True,heartbeat=True,speaking=False,playbackOperationId='forged'))
    assert 'speaking' not in voice.calls[-1][1] and 'playbackOperationId' not in voice.calls[-1][1],'Preview cannot override native playback receipts'
    voice.playback_ticket=('current','answer');portal.voice_audio[(DEVICE,'answer')]=(0,b'RIFF')
    desktop.publish(dict(turnId='current',operationId='answer',audioOnly=True,spokenReply=True))
    desktop.tick();assert messages[-1]['events'][0]['wav'],'Native owner receives local speech audio'
    assert not desktop.poll('preview')['events'],'Preview does not duplicate native playback'
    voice.owner='calendar';desktop.tick();assert voice.owner=='calendar','Existing calendar question retains ownership'
    voice.context={'projectId':'calendar-project'};voice.language='zh'
    voice.process=SimpleNamespace(poll=lambda:1);desktop.retry_at=0;desktop.tick()
    assert voice.calls[-1][0]=='calendar' and voice.calls[-1][1]['projectId']=='calendar-project' and voice.calls[-1][1]['language']=='zh','Recovery preserves a paired session context'
    desktop.publish(dict(turnId='current',operationId='answer',audioOnly=True,spokenReply=True))
    desktop.tick();assert 'wav' not in messages[-1]['events'][0],'Paired device playback is not duplicated on Mac'
    desktop.set_enabled(False);desktop.tick()
    assert not voice.owner and not desktop.enabled,'Explicit Pause remains paused across app ticks'
    assert not microphone_policy.allowed(portal.root,'calendar'),'A paired client cannot restart capture after local Pause'
    assert DesktopVoice(portal,messages.append).enabled is False,'Pause preference survives restart'
    desktop.set_enabled(True);microphone_policy.pause(portal.root);desktop.tick()
    assert not voice.owner,'Persistent mode cannot override the local microphone pause policy'
    desktop.control({'enabled':True})
    assert voice.owner==DEVICE and microphone_policy.allowed(portal.root,DEVICE),'Explicit local Resume claims capture before a paired heartbeat'
    desktop.close();assert not voice.owner,'App shutdown stops capture'
print('Desktop voice: 20 lifecycle, recovery, pause, event and audio isolation checks passed')
