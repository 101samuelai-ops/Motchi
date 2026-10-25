"""Behavior checks for non-deciding approval hooks and project-bound dog answers."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile

SCRIPT=Path(__file__).resolve().parents[1]/'skills/completion-pet/scripts/dog_bridge.py'
spec=importlib.util.spec_from_file_location('dog_bridge',SCRIPT)
dog=importlib.util.module_from_spec(spec);spec.loader.exec_module(dog)
checks=[]
def check(value,label):
    assert value,label
    checks.append(label)
with tempfile.TemporaryDirectory(prefix='dog-hub-test-') as temp:
    root=Path(temp);hub=root/'hub';hub.mkdir();a=root/'A';b=root/'B';a.mkdir();b.mkdir()
    a.joinpath('.progress-pet.json').write_text(json.dumps({'name':'Alpha','tasks':[{'id':'1','title':'Build','done':True},{'id':'2','title':'Test','done':False}]}))
    b.joinpath('.progress-pet.json').write_text(json.dumps({'name':'Beta','tasks':[]}))
    def event(kind,tool='Bash',turn='t1',description='Needs a permission'):
        return {'session_id':'session-A','cwd':str(a),'hook_event_name':kind,'turn_id':turn,'tool_name':tool,'tool_input':{'description':description}}
    dog.hook_event(event('PermissionRequest'),hub)
    state=json.loads(next(hub.glob('*.json')).read_text())
    check(state['status']=='waitingOnApproval' and len(state['approvals'])==1,'Approval is recorded without granting permission')
    first_alert=next(iter(state['approvals'].values()))['id']
    dog.hook_event(event('PermissionRequest'),hub)
    state=json.loads(next(hub.glob('*.json')).read_text())
    check(len(state['approvals'])==1,'Repeated approval notifications are deduplicated')
    check(next(iter(state['approvals'].values()))['id']==first_alert,'Duplicate notifications retain the same alert identity')
    dog.hook_event(event('PostToolUse','OtherTool'),hub)
    state=json.loads(next(hub.glob('*.json')).read_text())
    check(len(state['approvals'])==1,'Unrelated tool completion cannot clear an approval')
    dog.hook_event(event('PermissionRequest',turn='t2'),hub)
    dog.hook_event(event('Stop',turn='t1'),hub)
    state=json.loads(next(hub.glob('*.json')).read_text())
    check(len(state['approvals'])==1 and next(iter(state['approvals'].values()))['turnId']=='t2','Stopping one turn preserves another turn’s approval')
    dog.hook_event(event('PostToolUse',turn='t2'),hub)
    state=json.loads(next(hub.glob('*.json')).read_text())
    check(not state['approvals'] and state['status']=='active','Matching tool completion resolves its approval')
    dog.hook_event(event('PermissionRequest'),hub)
    state=json.loads(next(hub.glob('*.json')).read_text())
    check(next(iter(state['approvals'].values()))['id']!=first_alert,'A repeated request after resolution receives a new alert identity')
    dog.hook_event(event('PostToolUse'),hub)
    dog.hook_event(event('Stop',turn='t2'),hub)
    check(json.loads(next(hub.glob('*.json')).read_text())['status']=='idle','Stopped work is idle, not project complete')
    result=subprocess.run([sys.executable,str(SCRIPT),'--hook'],input='invalid',capture_output=True,text=True)
    check(result.returncode==0 and json.loads(result.stdout)=={},'Malformed hook input stays non-blocking and returns no decision')
    check(dog.checklist(a)['percent']==50,'Checklist progress is completed over total')
    check(dog.checklist(b)['percent'] is None,'Empty checklist does not claim completion')
    b.joinpath('.progress-pet.json').write_text('{broken')
    check(dog.checklist(b)['percent'] is None and dog.checklist(b)['issue'],'Invalid checklist never shows a stale percentage')
    bridge=dog.DogBridge(a,root=hub);bridge.checklists.infer=None
    class Metadata:
        def call(self,method,params):
            return {'data':[{'id':'session-A','cwd':str(a),'name':'Actual Alpha title','updatedAt':3}, {'id':'session-B','cwd':str(b),'name':'Actual Beta title','updatedAt':2}]}
        def close(self):pass
    bridge.server=Metadata()
    snap=bridge.snapshot()
    check({i['id'] for i in snap['items']}=={'session-A','session-B'},'Picker includes multiple Codex projects without creating chats')
    check(next(i for i in snap['items'] if i['id']=='session-A')['title']=='Actual Alpha title','Codex chat titles are preserved')
    check('Test' in bridge.ask('session-A','progress') and 'Beta' not in bridge.ask('session-A','progress'),'Local answer stays scoped to selected project')
    try:bridge.ask('unknown','progress');rejected=False
    except ValueError:rejected=True
    check(rejected,'Unknown project selection is rejected')
    try:bridge.ask('session-A','x'*3001);rejected=False
    except ValueError:rejected=True
    check(rejected,'Oversized chat inputs are rejected')
print(f'{len(checks)} dog hub checks passed')
for label in checks:print('PASS',label)
