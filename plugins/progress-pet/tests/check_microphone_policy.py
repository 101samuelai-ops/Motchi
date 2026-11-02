"""Local pause cannot be undone by paired clients or an expired test."""
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import time
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/completion-pet/scripts'))
import microphone_policy as policy
from mac_voice import MacVoice

checks = 0
def check(condition, message):
    global checks
    assert condition, message
    checks += 1
def rejected(action):
    try: action(); return False
    except ValueError: return True

class Portal:
    def __init__(self, root): self.root=root; self.voice=self
    def cancel(self, *args): pass
    def device_permitted(self, device): return True
class Child:
    def __init__(self): self.stdout=io.BytesIO(struct.pack('<h',200)*320); self.stderr=io.BytesIO(); self.dead=False
    def poll(self): return 0 if self.dead else None
    def terminate(self): self.dead=True
    def wait(self, timeout=None): pass

with tempfile.TemporaryDirectory() as temporary:
    root=Path(temporary); binary=root/'MacMicrophone'; binary.touch()
    check(policy.allowed(root,'calendar'),'An existing installation keeps its normal default before local pause')
    policy.pause(root)
    check(not policy.allowed(root,'calendar'),'Local pause blocks calendar reactivation')
    check(policy.path(root).stat().st_mode & 0o777 == 0o600,'Pause state is owner-only')
    voice=MacVoice(Portal(root),binary)
    with patch('mac_voice.subprocess.Popen') as started:
        check(rejected(lambda:voice.control('calendar',{'enabled':True})),
              'A paired request cannot override the local pause')
        check(not started.called,'Blocked requests never open the microphone')
    policy.allow_test(root,'preview',seconds=60)
    state=policy.read(root)
    check(policy.allowed(root,'preview') and not policy.allowed(root,'calendar'),
          'Only the exact test device can record during the scoped test')
    check(not policy.allowed(root,'preview',now=state['until']),
          'The test expires even if its browser keeps polling')
    child=Child()
    voice.owner='preview';voice.epoch='test-generation';voice.lease=100;voice.clock=lambda:0;voice.process=child
    policy.pause(root)
    voice.capture('preview',voice.epoch,child)
    check(child.dead and voice.owner is None,'A local pause closes already-running capture')
    check(rejected(lambda:voice.valid('preview','test-generation')),
          'Paused in-flight speech cannot publish an answer')
    policy.allow_test(root,'preview',seconds=60)
    voice.owner='preview';voice.epoch='late-answer-generation'
    def late_answer(*args):
        policy.pause(root)
        return {'wake':True,'heard':'Old question','text':'Old answer'}
    voice.portal.run_mac_voice=late_answer
    voice.recognize('preview',voice.epoch,struct.pack('<h',200)*320,False,True)
    check(not voice.events,'An answer racing a local pause is discarded before publication')
    check(rejected(lambda:voice.publish_transcript('preview',voice.epoch,'Late words')) and not voice.events,
          'A late streaming caption cannot publish after local pause')
    policy.allow_test(root,'preview',seconds=60)
    policy.finish_test(root,'another')
    check(policy.allowed(root,'preview'),'Closing an unrelated client cannot alter the active test')
    policy.finish_test(root,'preview')
    check(not policy.allowed(root,'preview') and policy.read(root)=={'paused':True},
          'Ending the test restores pause without reopening other devices')
    check(rejected(lambda:policy.allow_test(root,'preview',seconds=301)),
          'Local test exceptions cannot exceed five minutes')
    policy.path(root).write_text('invalid json')
    check(not policy.allowed(root,'calendar'),'Corrupt state fails closed')
    policy.save(root,{'paused':False})
    check(policy.allowed(root,'calendar'),'An explicit local resume restores normal controls')
    voice.close()
print(f'{checks} local microphone pause, expiry and capture checks passed')
