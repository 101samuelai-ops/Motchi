"""Pending-input lifecycle and permission alert regressions, without live prompts."""
import importlib.util
import json
from pathlib import Path
import tempfile
import time

script = Path(__file__).resolve().parents[1] / 'skills/completion-pet/scripts/dog_bridge.py'
spec = importlib.util.spec_from_file_location('dog', script)
dog = importlib.util.module_from_spec(spec); spec.loader.exec_module(dog)
checks = []
def check(value, label):
    assert value, label
    checks.append(label)

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp); sessions=root/'sessions'; sessions.mkdir(); hub=root/'hub'; hub.mkdir()
    project=root/'project'; project.mkdir(); log=sessions/'rollout.jsonl'
    def write(kind, payload):
        with log.open('a') as out:
            out.write(json.dumps({'type':kind,'timestamp':dog.datetime.now().astimezone().isoformat(),'payload':payload})+'\n')
    def call(name, identity, question):
        write('response_item',{'type':'function_call','name':name,'call_id':identity,'arguments':json.dumps({'questions':[{'title':question,'options':['Blue','Green']}],'private':'DO NOT COPY'})})
    write('session_meta',{'id':'chat'})
    write('event_msg',{'type':'task_started','turn_id':'turn-a'})
    call('request_user_input_async','call-async','Which colour?')
    write('response_item',{'type':'function_call_output','call_id':'call-async','output':'{"accepted":true}'})
    activity=dog.LocalActivity(sessions); item={'id':'chat','path':str(log)}
    q=activity.read(item)['questions']
    check(len(q)==1 and q[0]['question']=='Which colour?','Async delivery acknowledgement keeps the user question pending')
    check(not q[0]['canReply'],'Built-in questions direct replies to Codex')
    check('DO NOT COPY' not in json.dumps(activity.read(item)),'Unrelated tool arguments are excluded')
    call('functions.request_user_input','call-sync','Which layout?')
    check(len(activity.read(item)['questions'])==2,'Both ordinary and async question tools are observed')
    write('response_item',{'type':'function_call_output','call_id':'unrelated','output':'secret'})
    check(len(activity.read(item)['questions'])==2,'Unrelated tool results cannot resolve a question')
    write('response_item',{'type':'function_call_output','call_id':'call-sync','output':'secret answer not retained'})
    check(len(activity.read(item)['questions'])==1,'A synchronous answer resolves only its matching request')
    write('response_item',{'type':'message','role':'user','content':[{'type':'input_text','text':'<send_user_message_question_reply>\n'+json.dumps([{'questionItemId':json.dumps(['request_user_input_async','call-async',0]),'answer':'Blue'}])+'\n</send_user_message_question_reply>'}]})
    check(activity.read(item)['questions']==[],'A structured async reply clears its matching question')
    call('request_user_input_async','call-wait','Pick one?')
    bridge=dog.DogBridge(project,root=hub);bridge.activity=activity;bridge.checklists.infer=None
    class Metadata:
        def call(self,method,params):return {'data':[{'id':'chat','cwd':str(project),'path':str(log),'name':'Demo project','updatedAt':1}]}
        def close(self):pass
    bridge.server=Metadata()
    snap=bridge.snapshot(); selected=snap['items'][0]
    check(snap['autoSelection']=='chat' and selected['status']=='waitingOnInput','Recorded questions become prioritized pending-input projects')
    hook={'session_id':'chat','cwd':str(project),'turn_id':'turn-a','tool_name':'request_user_input_async','tool_input':{'questions':[{'title':'Pick one?'}]},'hook_event_name':'PreToolUse'}
    dog.hook_event(hook,hub)
    check(len(bridge.snapshot()['items'][0]['questions'])==1,'Hook and log mirrors do not duplicate the same question')
    permission={**hook,'tool_name':'exec_command','hook_event_name':'PermissionRequest','tool_input':{'justification':'Allow access to the project folder?','cmd':'PRIVATE COMMAND'}}
    dog.hook_event(permission,hub);dog.hook_event(permission,hub)
    item=bridge.snapshot()['items'][0]
    check(len(item['approvals'])==1 and item['approvals'][0]['reason']=='Allow access to the project folder?','Permission alerts retain the explanation and deduplicate')
    check(item['questions'] and item['approvals'],'Questions and permission alerts coexist')
    check('PRIVATE COMMAND' not in json.dumps(item),'Permission alert does not retain command contents')
    dog.hook_event({**permission,'hook_event_name':'PostToolUse'},hub)
    check(bridge.snapshot()['items'][0]['approvals']==[],'Finished tool clears its permission alert')
    write('event_msg',{'type':'turn_aborted','turn_id':'turn-a'})
    check(activity.read({'id':'chat','path':str(log)})['questions']==[],'Aborting a turn clears outstanding recorded questions')
    bridge.close()
print(f'{len(checks)} attention checks passed')
for label in checks:print('PASS',label)
