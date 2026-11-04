"""Two consecutive Mac turns, playback receipts and bounded follow-up consent.

Uses real controllers with fixture PCM/transcripts; no microphone or model.
"""
import io
from pathlib import Path
import struct
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'skills/completion-pet/scripts'))
from mac_voice import MacVoice, FOLLOWUP_SECONDS, PLAYBACK_TAIL_SECONDS
from voice_companion import VoiceCompanion

checks = 0
def check(value, label):
    global checks
    assert value, label
    checks += 1

def frame(n): return struct.pack('<h', n)*320
class Child:
    def __init__(self, pcm=b''): self.stdout=io.BytesIO(pcm)
    def poll(self): return None
    def terminate(self): pass
    def wait(self, timeout=None): pass
class Keywords:
    ready=True; issue=None
    def feed(self, data): return None
    def clear(self): pass
    def close(self): pass
class Endpoint:
    def predict(self, audio, permitted): permitted(); return .99
    def close(self): pass
class Portal:
    def __init__(self, clock):
        self.requests=[]; self.discussions=[]; self.allowed=True; self.transcript=''
        self.voice=VoiceCompanion(lambda _:self.transcript, lambda:[], lambda *a:None,
            lambda _:self.allowed, discuss=self.discuss, clock=clock)
    def device_permitted(self, device): return self.allowed
    def discuss(self, request):
        self.discussions.append(dict(request))
        return {'text':'One verified task remains.', 'scope':'project',
                'projectId':'alpha', 'selection':'alpha-chat'}
    def run_mac_voice(self, device, request, audio, **extra):
        self.requests.append(dict(request))
        return self.voice.run(device, request, audio, **extra)
    def voice_transcribe(self, audio, request): return self.transcript

with tempfile.TemporaryDirectory() as directory:
    for first, second in [('How is Alpha doing?', 'What should I do next?'),
                          ('项目进度怎么样？', '还有什么需要我处理？')]:
        now=[100.]
        portal=Portal(lambda:now[0]); voice=MacVoice(portal,Path(directory)/'helper',clock=lambda:now[0])
        voice.owner='preview'; voice.lease=1000; voice.epoch='initial-generation'
        voice.context={'projectId':'alpha','selection':'alpha-chat'}
        voice.wake_detector=Keywords(); voice.endpoint=Endpoint()
        def feed(pcm):
            child=Child(pcm); voice.process=child
            with patch.object(voice.worker,'submit'):
                voice.capture('preview',voice.epoch,child)
            voice.process=Child(); voice.last_frame_at=now[0]
        def answer(text):
            portal.transcript=text
            with patch.object(voice.worker,'submit',side_effect=lambda fn,*args:fn(*args)):
                voice.assess_endpoint('preview',voice.epoch,voice.segmenter.version,
                                      voice.segmenter.endpoint_audio())
        voice.activate(); voice.poll('preview')
        feed(frame(300)*90+frame(0)*60); answer(first)
        event=voice.poll('preview')['events'][-1]; epoch=voice.epoch; turn=voice.turn_id
        check(len(portal.discussions)==1 and event['text']=='One verified task remains.',
              'The first question completes before the next turn: '+first)
        check(voice.snapshot()['followupSeconds']==FOLLOWUP_SECONDS and voice.stage=='follow-up',
              'A completed answer opens a bounded, visible follow-up window')
        voice.audio_ready('preview',epoch,event)
        ticket={'playbackTurnId':turn,'playbackOperationId':event['operationId']}
        voice.control('preview',dict(enabled=True,conversationVersion=2,**voice.context,**ticket,speaking=True))
        now[0]+=45; voice.lease=1000
        feed(frame(500)*60)
        check(voice.epoch==epoch and len(portal.discussions)==1 and voice.segmenter.speech is None,
              'Motchi speaker output cannot become a follow-up question')
        voice.control('preview',dict(enabled=True,conversationVersion=2,**voice.context,**ticket,speaking=False))
        deadline=voice.followup_until
        check(deadline==now[0]+FOLLOWUP_SECONDS and voice.muted_until==now[0]+PLAYBACK_TAIL_SECONDS,
              'The full follow-up window starts after playback, with only a short echo tail')
        now[0]+=.5
        voice.control('preview',dict(enabled=True,conversationVersion=2,**voice.context,**ticket,speaking=False))
        check(voice.followup_until==deadline,
              'Repeated stopped-playback heartbeats cannot renew follow-up consent')
        feed(frame(300)*90+frame(0)*60)
        check(voice.epoch!=epoch and voice.turn_id!=turn and voice.events[0]['followup'],
              'Follow-up speech starts a fresh turn without a wake name')
        check(voice.segmenter.voiced>=80 and voice.checked_transcript is None,
              'The new turn retains its first words and clears old transcript/endpoint caches')
        answer(second)
        check([r['text'] for r in portal.discussions]==[first,second] and
              all(r['projectId']=='alpha' and r['selection']=='alpha-chat' for r in portal.discussions),
              'Both questions reach the exact selected project once, including the unaddressed follow-up')
        check(portal.requests[-1]['activated'] is True and not portal.requests[-1]['preview'],
              'Only the trusted active Mac window authorizes final follow-up recognition')
        before=voice.followup_until
        voice.control('preview',dict(enabled=True,conversationVersion=2,**voice.context,**ticket,speaking=False))
        check(voice.followup_until==before,
              'A playback completion from the first answer cannot change the second turn')
        feed(frame(300)*90+frame(0)*60)
        third='可以解释一下吗？' if '项目' in first else 'Can you explain that?'
        answer(third)
        check(len(portal.discussions)==3 and portal.discussions[-1]['text']==third,
              'A text-only answer also accepts the next follow-up without waiting for audio')
        now[0]+=FOLLOWUP_SECONDS+1
        epoch=voice.epoch; feed(frame(300)*90+frame(0)*60)
        check(voice.epoch==epoch and voice.segmenter.speech is None and len(portal.discussions)==3,
              'Expired follow-up windows return to local wake-only listening')
        voice.followup_until=now[0]+FOLLOWUP_SECONDS
        voice.control('preview',dict(enabled=True,projectId='beta',selection='beta-chat'))
        check(voice.followup_until==0 and not voice.playback_ticket,
              'A genuine project switch cancels the previous follow-up and playback identity')
        voice.followup_until=now[0]+FOLLOWUP_SECONDS
        voice.stop()
        check(not voice.owner and voice.followup_until==0,
              'Pausing clears all automatic follow-up capture permission')
        voice.close()

print(f'{checks} consecutive bilingual turn, playback and follow-up expiry checks passed')
