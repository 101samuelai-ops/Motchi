"""Real JSON-RPC approval replies, explanation isolation and lifecycle regressions."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time

# A deterministic app-server peer, not a fake UI: consumes actual JSON-RPC replies
# and only continues after the client responds to the exact server request ID.
if '--server' in sys.argv:
    replies=[];counter=0
    def emit(v):print(json.dumps(v),flush=True)
    for line in sys.stdin:
        m=json.loads(line)
        if 'method' not in m:
            replies.append(m);continue
        method=m['method'];params=m.get('params',{});identity=m.get('id')
        if method=='initialized':continue
        if method=='initialize':result={'userAgent':'test'}
        elif method=='thread/start':
            counter+=1;result={'thread':{'id':f'chat-{counter}','cwd':params['cwd']}}
        elif method=='turn/start':
            result={'turn':{'id':'turn-1'}}
            emit({'method':'turn/started','params':{'threadId':params['threadId'],'turn':{'id':'turn-1'}}})
        elif method=='turn/steer':result={'turnId':params['expectedTurnId']}
        elif method=='test/event':
            emit(params);result={'delivered':True}
        elif method=='test/replies':result={'replies':replies}
        elif method=='test/clear':replies=[];result={}
        elif method in ('thread/resume','turn/interrupt'):result={}
        else:result={}
        emit({'id':identity,'result':result})
    sys.exit(0)

SCRIPTS=Path(__file__).resolve().parents[1]/'skills/completion-pet/scripts'
sys.path.insert(0,str(SCRIPTS))
import dog_bridge as dog
from codex_control import ManagedCodex,CodexConnection
checks=[]
def check(value,label):
    assert value,label
    checks.append(label)
def rejects(function):
    try:function();return False
    except (ValueError,RuntimeError):return True

with tempfile.TemporaryDirectory(prefix='mochi-control-') as temp:
    root=Path(temp);project=root/'project';project.mkdir();hub=root/'hub';hub.mkdir()
    control=ManagedCodex(sys.executable,hub,dog.atomic_json)
    conn=CodexConnection([sys.executable,str(Path(__file__).resolve()),'--server'],control.event,control.disconnected)
    control.connection=conn
    result=control.start_task(str(project),'Example','Build a sample')
    tid=result['selection']
    check(tid=='chat-1' and control.snapshot()[tid]['status']=='active','A task explicitly started in Motchi owns a live Codex connection')
    def event(method,params,identity=None):
        message={'method':method,'params':params}
        if identity is not None:message['id']=identity
        conn.call('test/event',message)
    def permission(rpc=42,kind='permissions',thread=tid,turn='turn-1',**extra):
        method={'permissions':'item/permissions/requestApproval','command':'item/commandExecution/requestApproval','file':'item/fileChange/requestApproval'}[kind]
        event(method,{'threadId':thread,'turnId':turn,'itemId':'item-'+str(rpc),'reason':'Need fixture access',
                     'permissions':{'network':None,'fileSystem':{'read':['/fixture/outside']}},**extra},rpc)
        return next((a['id'] for a in control.snapshot().get(thread,{}).get('approvals',[]) if a['kind']==kind),None)
    def replies():return conn.call('test/replies',{})['replies']
    def clear():conn.call('test/clear',{})
    token=permission()
    check(token and control.snapshot()[tid]['approvals'][0]['canDecide'],'A server-initiated permission request becomes an answerable Motchi card')
    check(not replies(),'Receiving or displaying a request never approves it')
    check(conn.call('test/replies',{})=={'replies':[]},'Ordinary RPC results remain routable while an approval is pending')
    check(rejects(lambda:control.decide('wrong-thread',token,'allow')),'A different project cannot answer the request')
    check(rejects(lambda:control.decide(tid,'stale-token','allow')),'A stale UI request cannot grant access')
    check(rejects(lambda:control.decide(tid,token,'yes')),'Conversational yes is not an approval decision')
    context=control.explain_context(tid,token)
    context['request']['permissions']['fileSystem']['read'].append('/injected')
    control.decide(tid,token,'allow')
    sent=replies()[-1]
    check(sent=={'id':42,'result':{'permissions':{'fileSystem':{'read':['/fixture/outside']}},'scope':'turn'}},'Allow replies to the exact RPC ID with only captured requested access and turn scope')
    check(rejects(lambda:control.decide(tid,token,'allow')) and len(replies())==1,'A request can be answered only once')
    token=permission(43);control.decide(tid,token,'deny')
    check(replies()[-1]=={'id':43,'result':{'permissions':{},'scope':'turn'}},'Deny sends an empty granted-permission profile')
    token=permission(44,kind='command',command='printf fixture',availableDecisions=['accept','decline'])
    control.decide(tid,token,'allow')
    check(replies()[-1]=={'id':44,'result':{'decision':'accept'}},'Command Allow uses the real command-approval protocol')
    token=permission(45,kind='file',grantRoot='/fixture')
    control.decide(tid,token,'deny')
    check(replies()[-1]=={'id':45,'result':{'decision':'decline'}},'File-change Deny uses the real file-approval protocol')
    token=permission(46,kind='command',availableDecisions=['cancel'])
    check(control.snapshot()[tid]['approvals'][0]['decisions']==['deny'] and rejects(lambda:control.decide(tid,token,'allow')),'The UI exposes only decisions Codex actually offers')
    control.decide(tid,token,'deny');check(replies()[-1]['result']=={'decision':'cancel'},'Cancel-only approvals use the supported cancellation response')
    token=permission(47);count=len(replies());out=[]
    def race():
        try:out.append(control.decide(tid,token,'allow'))
        except ValueError:out.append('already resolved')
    workers=[threading.Thread(target=race) for _ in range(2)]
    for w in workers:w.start()
    for w in workers:w.join()
    check(len(replies())==count+1 and 'already resolved' in out,'Concurrent double clicks cannot send duplicate approval replies')
    token=permission(48);event('serverRequest/resolved',{'threadId':tid,'requestId':48})
    check(not control.snapshot()[tid]['approvals'] and rejects(lambda:control.decide(tid,token,'allow')),'Server-side resolution invalidates the matching UI decision')
    token=permission(49);permission(50,thread='unowned-desktop-chat')
    check(replies()[-1].get('error',{}).get('code')==-32601 and len(control.snapshot()[tid]['approvals'])==1,'Requests for unowned desktop chats are never converted into approvals')
    permission(51,turn='wrong-turn')
    check(replies()[-1].get('error',{}).get('code')==-32602,'A stale turn cannot attach its approval to the current task')
    event('turn/completed',{'threadId':tid,'turn':{'id':'other'}})
    check(control.snapshot()[tid]['approvals'],'A different turn cannot clear this task’s pending permission')
    event('turn/completed',{'threadId':tid,'turn':{'id':'turn-1'}})
    check(not control.snapshot()[tid]['approvals'],'Matching task completion clears unanswered approvals')
    control.send_turn(tid,'Next step')
    event('item/tool/requestUserInput',{'threadId':tid,'turnId':'turn-1','itemId':'q','questions':[
        {'id':'colour','question':'Which colour?','options':[{'label':'Blue'}],'isSecret':False},
        {'id':'size','question':'Which size?','options':[],'isSecret':False}]},80)
    questions=control.snapshot()[tid]['questions'];count=len(replies())
    control.question_reply(tid,questions[0]['id'],'Blue')
    check(len(replies())==count and len(control.snapshot()[tid]['questions'])==1,'Multi-question prompts wait for every answer')
    control.question_reply(tid,questions[1]['id'],'Small')
    check(replies()[-1]=={'id':80,'result':{'answers':{'colour':{'answers':['Blue']},'size':{'answers':['Small']}}}},'Ordinary user answers return to the exact app-server request')
    event('item/tool/requestUserInput',{'threadId':tid,'turnId':'turn-1','itemId':'secret','questions':[
        {'id':'password','question':'Password?','isSecret':True}]},82)
    check(replies()[-1].get('error',{}).get('code')==-32602 and not control.snapshot()[tid]['questions'],'Secret prompts are rejected instead of collected in ordinary chat')
    event('item/started',{'threadId':tid,'turnId':'turn-1','item':{'type':'fileChange','id':'item-85','changes':[
        {'path':'sample.txt','kind':{'type':'update'},'diff':'-old\n+new'}]}})
    file_token=permission(85,kind='file')
    check('sample.txt' in control.snapshot()[tid]['approvals'][0]['details'] and '+new' in control.snapshot()[tid]['approvals'][0]['details'],'File approval cards include the actual proposed changes')
    check('toolItems' not in control.snapshot()[tid],'Transient file-item bookkeeping is not exposed in snapshots')
    control.decide(tid,file_token,'deny')
    duplicate=permission(86);permission(86)
    check(len(control.snapshot()[tid]['approvals'])==1 and control.snapshot()[tid]['approvals'][0]['id']==duplicate,'Duplicate server delivery preserves one stable approval identity')
    control.decide(tid,duplicate,'deny')
    check(ManagedCodex.details({'permissions':{'fileSystem':{'entries':[{'path':{'type':'path','path':'/fixture'},'access':'read'}]}}})=='Read: /fixture','Permission scopes are presented as readable access descriptions')
    token=permission(81)
    bridge=dog.DogBridge(project,root=hub);bridge.control=control;bridge.checklists.infer=None
    class Metadata:
        def call(self,*_):return {'data':[]}
        def close(self):pass
    bridge.server=Metadata()
    fake=root/'fake-model';fake.write_text('''#!/usr/bin/env python3
import json,sys
prompt=sys.stdin.read()
assert 'pendingApproval' in prompt and 'read-only' in sys.argv
assert 'only' not in sys.argv
print(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':'This reads only the displayed fixture folder. No approval was sent.'}}),flush=True)
print(json.dumps({'type':'turn.completed'}),flush=True)
''');fake.chmod(0o755);bridge.codex=str(fake)
    count=len(replies())
    answer=bridge.handle_action({'action':'askApproval','selection':tid,'approvalId':token,'text':'Why is access needed?'})
    check('fixture folder' in answer['text'] and answer['routedSelection']==tid,'Permission follow-up questions use a separate read-only context with the exact request')
    check(len(replies())==count and control.snapshot()[tid]['approvals'],'Asking an explanation leaves the original task paused and sends no approval')
    bridge.handle_action({'action':'askApproval','selection':tid,'approvalId':token,'text':'yes'})
    check(len(replies())==count,'Typing yes in the explanation chat does not approve')
    fake.write_text('#!/usr/bin/env python3\nimport sys\nsys.stdin.read()\nsys.exit(1)\n')
    fallback=bridge.handle_action({'action':'askApproval','selection':tid,'approvalId':token,'text':'Explain it'})
    check('still pending' in fallback['text'] and 'latest recorded project update' not in fallback['text'],'Explanation failures preserve the request and do not substitute unrelated progress')
    control.persist();stored=control.registry.read_text()
    check('fixture/outside' not in stored and 'permissions' not in stored and 'command' not in stored,'Registry stores routing metadata without permission contents or commands')
    check(rejects(lambda:control.send_turn(tid,'continue')),'A pending approval cannot be bypassed by starting another turn')
    event('item/completed',{'threadId':tid,'turnId':'turn-1','item':{'type':'agentMessage','text':'Finished the requested task.'}})
    event('turn/completed',{'threadId':tid,'turn':{'id':'turn-1'}})
    check(control.snapshot()[tid].get('managedReplyKey')==tid+':turn-1','A finished managed task supplies a stable key to reopen its answer')
    control.send_turn(tid,'Again');token=permission(90)
    control.stop(tid)
    check(not control.snapshot()[tid]['approvals'] and rejects(lambda:control.decide(tid,token,'allow')),'Stopping a task invalidates its unanswered permission')
    control.send_turn(tid,'Again');token=permission(91)
    conn.close();deadline=time.monotonic()+2
    while control.items[tid]['status']!='disconnected' and time.monotonic()<deadline:time.sleep(.01)
    check(not control.snapshot()[tid]['approvals'] and rejects(lambda:control.decide(tid,token,'allow')),'Connection loss clears decision capabilities without granting access')
    restored=ManagedCodex(sys.executable,hub,dog.atomic_json)
    check(restored.snapshot()[tid]['status']=='disconnected' and not restored.snapshot()[tid]['approvals'],'Restarted tasks never restore stale approval RPC IDs')
    bridge.close()
print(f'{len(checks)} Codex control checks passed')
for label in checks:print('PASS',label)
