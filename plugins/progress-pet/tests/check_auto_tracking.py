"""Regression checks for automatic selection, local activity and resilient replies."""
import importlib.util
import json
from pathlib import Path
import tempfile
import time

SCRIPT = Path(__file__).resolve().parents[1] / 'skills/completion-pet/scripts/dog_bridge.py'
spec = importlib.util.spec_from_file_location('dog_bridge', SCRIPT)
dog = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dog)
checks = []
def check(value, label):
    assert value, label
    checks.append(label)

with tempfile.TemporaryDirectory(prefix='mochi-tracking-') as tmp:
    root = Path(tmp); sessions = root/'sessions'; sessions.mkdir(); hub=root/'hub'; hub.mkdir()
    project=root/'project'; project.mkdir(); other=root/'other'; other.mkdir()
    log=sessions/'rollout.jsonl'
    def write(kind, payload, partial=False):
        record={'timestamp':dog.datetime.now().astimezone().isoformat(), 'type':kind, 'payload':payload}
        with log.open('a') as out:out.write(json.dumps(record)+('' if partial else '\n'))
    write('session_meta', {'id':'chat-a'})
    write('event_msg', {'type':'task_started', 'turn_id':'turn-1'})
    write('response_item', {'type':'message','role':'assistant','content':[{'type':'output_text','text':'Built the login screen.'}]})
    write('response_item', {'type':'reasoning','content':[{'text':'PRIVATE REASONING MUST NOT APPEAR'}]})
    write('response_item', {'type':'function_call','name':'functions.update_plan','arguments':json.dumps({'plan':[{'step':'Build login','status':'completed'},{'step':'Test login','status':'in_progress'}]})})
    activity=dog.LocalActivity(sessions)
    item={'id':'chat-a','path':str(log)}
    state=activity.read(item)
    check(state['state']=='active' and state['turnId']=='turn-1','Explicit task start is tracked')
    check(state['plan'][0]['done'] and not state['plan'][1]['done'],'Codex task plans preserve completed and ongoing steps')
    check('PRIVATE' not in json.dumps(state),'Private reasoning is excluded')
    write('event_msg', {'type':'task_complete','turn_id':'different-turn'})
    check(activity.read(item)['state']=='active','Another turn cannot finish the tracked task')
    write('event_msg', {'type':'task_complete','turn_id':'turn-1','last_agent_message':'Login built; tests still need work.'},partial=True)
    check(activity.read(item)['state']=='active','Incomplete log append is retried without losing the event')
    with log.open('a') as out:out.write('\n')
    check(activity.read(item)['state']=='idle','Matching completion finishes the turn, not the project')
    check(activity.read({'id':'wrong-chat','path':str(log)})=={},'Rollout metadata must match the selected chat')
    outside=root/'outside.jsonl';outside.write_text(log.read_text())
    check(activity.read({'id':'chat-a','path':str(outside)})=={},'Activity reader rejects paths outside Codex sessions')
    bridge=dog.DogBridge(project,root=hub);bridge.activity=activity;bridge.checklists.infer=None
    class Metadata:
        def call(self,method,params):
            if method=='thread/list':return {'data':[{'id':'chat-a','cwd':str(project),'name':'Alpha project','path':str(log),'updatedAt':2}, {'id':'chat-b','cwd':str(other),'name':'World Trigger','updatedAt':1}]}
            return {'data':[]}
        def close(self):pass
    bridge.server=Metadata()
    snap=bridge.snapshot();alpha=next(i for i in snap['items'] if i['id']=='chat-a')
    check(alpha['progress']['percent']==50 and alpha['progress']['source']=='checklist','Recorded Codex plans seed the automatic project checklist')
    start=time.monotonic();answer=bridge.ask('chat-a','whats has being done?')
    check('Login built' in answer and time.monotonic()-start < 1,'Screenshot question gets a grounded local answer without a model timeout')
    check('Test login' in bridge.ask('chat-a',"what's left?"),'Remaining work answers use recorded plan steps')
    check(bridge.route_topic('chat-a','what has World Trigger done?',True)=='chat-b','Chat text selects an explicitly named project automatically')
    check(bridge.route_topic('chat-a','what has World Trigger done?',False)=='chat-a','Manual pin remains scoped to its selected project')
    write('event_msg', {'type':'task_started','turn_id':'turn-2'})
    snap=bridge.snapshot()
    check(snap['autoSelection']=='chat-a' and next(i for i in snap['items'] if i['id']=='chat-a')['trackingKey'].endswith(':turn-2'),'New task drives automatic selection and a stable one-time tracking identity')
    check(not next(i for i in snap['items'] if i['id']=='chat-a')['activity']['plan'],'A new task does not inherit the old task’s plan')
    fake=root/'fake-codex';fake.write_text('''#!/usr/bin/env python3
import json,sys,time
sys.stdin.read()
print(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':'The login screen is built.'}}),flush=True)
print(json.dumps({'type':'turn.completed'}),flush=True)
time.sleep(120)
''');fake.chmod(0o755);bridge.codex=str(fake)
    start=time.monotonic();reply=bridge.ask('chat-a','Why use a login screen?')
    check(reply=='The login screen is built.' and time.monotonic()-start < 8,'Final model answer returns without waiting for a stuck CLI shutdown')
    fake.write_text('#!/usr/bin/env python3\nimport sys\nsys.stdin.read()\nsys.exit(1)\n')
    fallback=bridge.ask('chat-a','Why use a password?')
    check('recorded project update' in fallback and 'Login built' in fallback,'Provider failure returns a grounded fallback instead of an empty timeout')
    bridge.close()
print(f'{len(checks)} automatic tracking checks passed')
for label in checks:print('PASS',label)
