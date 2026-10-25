"""Native request_permissions cards: exact literal adapters and asynchronous lifecycle."""
import importlib.util
import json
from pathlib import Path
import tempfile
import time

script = Path(__file__).resolve().parents[1]/'skills/completion-pet/scripts/dog_bridge.py'
spec = importlib.util.spec_from_file_location('dog',script)
dog = importlib.util.module_from_spec(spec); spec.loader.exec_module(dog)
checks=[]
def check(value,label):
    assert value,label
    checks.append(label)

with tempfile.TemporaryDirectory() as temp:
    root=Path(temp);sessions=root/'sessions';sessions.mkdir();hub=root/'hub';hub.mkdir();project=root/'project';project.mkdir()
    log=sessions/'rollout.jsonl'
    def write(kind,payload):
        with log.open('a') as out:out.write(json.dumps({'type':kind,'timestamp':dog.datetime.now().astimezone().isoformat(),'payload':payload})+'\n')
    def call(identity,source):write('response_item',{'type':'custom_tool_call','name':'exec','call_id':identity,'input':source})
    def output(identity,value,custom=False):write('response_item',{'type':'custom_tool_call_output' if custom else 'function_call_output','call_id':identity,'output':value})
    def wait(identity,cell):write('response_item',{'type':'function_call','name':'functions.wait','call_id':identity,'arguments':json.dumps({'cell_id':cell})})
    write('session_meta',{'id':'chat'})
    write('event_msg',{'type':'task_started','turn_id':'turn'})
    activity=dog.LocalActivity(sessions);item={'id':'chat','path':str(log)}
    def state():return activity.read(item)
    def pending():return state()['approvals']
    args={'permissions':{'file_system':{'write':['/Users/test/.codex']},'network':{'enabled':True}},'reason':'Register Motchi safely','private':'PRIVATE ARGUMENT'}
    write('response_item',{'type':'function_call','name':'functions.request_permissions','call_id':'direct','arguments':json.dumps(args)})
    check(len(pending())==1 and 'Register Motchi' in pending()[0]['reason'],'Direct native permission requests become pending approval alerts')
    check('Edit /Users/test/.codex' in pending()[0]['reason'] and 'Network access' in pending()[0]['reason'],'Requested filesystem and network scope is shown')
    check('PRIVATE ARGUMENT' not in json.dumps(state()),'Unrelated arguments never enter companion state')
    output('other','anything')
    check(len(pending())==1,'Unrelated output cannot clear another permission')
    output('direct',{'permissions':{}})
    check(not pending(),'A matching direct denial resolves its alert')
    source='text(await tools.request_permissions({permissions: {file_system: {write: ["/Users/test/.codex"]}}, reason: "Register Motchi safely"}));'
    call('wrapped',source)
    check(len(pending())==1,'The exact standalone exec wrapper from the screenshot is recognized')
    output('wrapped','Script running with cell ID 42\nWall time 31.0 seconds\nOutput:\n',True)
    check(len(pending())==1,'Exec delivery acknowledgement keeps the permission pending')
    wait('wrong-wait','different-cell');output('wrong-wait','Script completed\nOutput:\n')
    check(len(pending())==1,'A different cell cannot resolve this permission')
    wait('still-wait','42');output('still-wait','Script running with cell ID 42\nOutput:\n')
    check(len(pending())==1,'Waiting again keeps the native decision pending')
    wait('unknown-wait','42');output('unknown-wait','Unrecognized delivery acknowledgement')
    check(len(pending())==1,'Unrecognized wrapper acknowledgement cannot dismiss the request')
    check('permissionCells' not in state() and 'Script running' not in json.dumps(state()),'Execution bookkeeping and tool outputs stay out of the snapshot')
    wait('resolved-wait','42');output('resolved-wait',[{'type':'input_text','text':'Script completed\nWall time 0.0 seconds\nOutput:\n'},{'type':'input_text','text':'{"permissions":{},"scope":"turn","private":"PRIVATE RESULT"}'}])
    check(not pending() and 'PRIVATE RESULT' not in json.dumps(state()),'A matching completed wait clears the permission without copying its result')
    call('fast',source);output('fast',[{'type':'input_text','text':'Script completed\nOutput:\n'}],True)
    check(not pending(),'Fast wrapper completion clears without a wait')
    for i,bad in enumerate([
        'text("'+source.replace('"','\\"')+'");',
        'const example = '+json.dumps(source)+';',
        'text(await tools.request_permissions(getPermissions()));',
        source+'text("other work");',
        source.replace('"Register Motchi safely"','runCommand()'),
        source.replace('"Register Motchi safely"','`template ${runCommand()}`'),
        source.replace('"Register Motchi safely"','process.env.SECRET'),
        source.replace('"Register Motchi safely"','(()=>{throw Error("oops")})()'),
        source.replace('{permissions:', '{...other, permissions:'),
        source.replace('write: ["/Users/test/.codex"]','write: files'),
        source.replace('reason:', '/* comment */ reason:'),
        'text(await tools.request_permissions('+('['*30)+'{}'+(']'*30)+'));',
    ]):
        call('bad-'+str(i),bad)
    check(not pending(),'Examples, expressions, variables, templates, comments and arbitrary scripts are never evaluated or treated as prompts')
    call('quoted','await tools.request_permissions('+json.dumps(args)+');')
    check(len(pending())==1,'Standalone await with a JSON literal is supported')
    write('response_item',{'type':'function_call','name':'functions.request_user_input_async','call_id':'question','arguments':json.dumps({'questions':[{'title':'Choose a theme?'}]})})
    bridge=dog.DogBridge(project,root=hub);bridge.activity=activity;bridge.checklists.infer=None
    class Metadata:
        def call(self,*_):return {'data':[{'id':'chat','cwd':str(project),'path':str(log),'name':'Motchi project','updatedAt':1}]}
        def close(self):pass
    bridge.server=Metadata()
    s=bridge.snapshot();current=s['items'][0]
    check(current['status']=='waitingOnApproval' and current['questions'] and current['approvals'],'Permissions coexist with questions and get approval priority')
    hook={'session_id':'chat','cwd':str(project),'turn_id':'turn','hook_event_name':'PermissionRequest','tool_name':'request_permissions','call_id':'quoted','tool_input':{'reason':'Register Motchi safely'}}
    dog.hook_event(hook,hub)
    check(len(bridge.snapshot()['items'][0]['approvals'])==1,'Hook and rollout mirrors deduplicate the same permission call')
    dog.hook_event({**hook,'hook_event_name':'PostToolUse'},hub)
    check(len(bridge.snapshot()['items'][0]['approvals'])==1,'An empty hook record does not overwrite the still-pending local request')
    write('event_msg',{'type':'task_complete','turn_id':'other-turn'})
    check(len(pending())==1,'Another turn cannot clear the pending permission')
    write('event_msg',{'type':'turn_aborted','turn_id':'turn'})
    check(not pending(),'An interrupted turn clears its permission and wait bookkeeping')
    write('event_msg',{'type':'task_started','turn_id':'turn-next'})
    call('ending',source)
    write('event_msg',{'type':'task_complete','turn_id':'turn-next'})
    check(not pending(),'Task completion clears outstanding native permission alerts')
    call('fresh',source)
    write('event_msg',{'type':'task_started','turn_id':'turn-new'})
    check(not pending(),'A new task does not inherit old approvals')
    check(activity.read({'id':'wrong-project','path':str(log)})=={},'Approval logs must match the catalog chat identity')
    bridge.close()
print(f'{len(checks)} native permission checks passed')
for label in checks:print('PASS',label)
