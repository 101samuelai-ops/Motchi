"""Checklist reconciliation, exact-turn steering and duplicate decisions."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/completion-pet/scripts'))
from checklist_sync import Checklists, Store
from dog_bridge import DogBridge, LocalActivity, atomic_json
from codex_control import ManagedCodex, CodexConnection
checks=[]
def check(value,label):
    assert value,label
    checks.append(label)
def rejects(fn):
    try: fn(); return False
    except (ValueError,RuntimeError,TimeoutError): return True
with tempfile.TemporaryDirectory() as temp:
    root=Path(temp);project=root/'project';project.mkdir();other=root/'other';other.mkdir();hub=root/'hub';hub.mkdir()
    c=Checklists()
    first=c.propose(project,'chat-a','Build the login page','first')
    check(len(Store(project).read()['tasks'])==1,'A new task is added unchecked')
    check(not Store(project).read()['tasks'][0]['done'],'Adding work never marks it complete')
    c.propose(project,'chat-a','Build the login page','first')
    check(len(Store(project).read()['tasks'])==1,'Repeated history sources are idempotent')
    similar=c.propose(project,'chat-a','Build the login screen','second',text='Build the login screen')
    pid=similar['proposalId']
    check(similar['pending'] and len(Store(project).read()['tasks'])==1,'A similar task waits for a real user decision')
    check(len(c.view(project,'chat-a')['questions'])==1 and not c.view(project,'chat-b')['questions'],'Duplicate questions remain in their originating chat')
    check(rejects(lambda:c.resolve(project,'chat-b',pid,'Same task')),'Another chat cannot resolve a duplicate')
    check(rejects(lambda:c.resolve(project,'chat-a',pid,'yes')),'An ambiguous reply does not silently merge tasks')
    result=c.resolve(project,'chat-a',pid,'Same task')
    check(result['taskId']==first['taskId'] and len(Store(project).read()['tasks'])==1,'Same task preserves the original checklist identity')
    sent=[]
    def sender(selection,text):sent.append((selection,text));return {'text':'sent'}
    c.delivery(project,'chat-a',pid,sender)
    check(sent==[('chat-a','Build the login screen')],'Resolved explicit work sends its original prompt once')
    check(rejects(lambda:c.delivery(project,'chat-a',pid,sender)) and len(sent)==1,'Double submission cannot duplicate a delivered prompt')
    similar=c.propose(project,'chat-a','Build the login screen','third')
    c.resolve(project,'chat-a',similar['proposalId'],'Different task')
    check(len(Store(project).read()['tasks'])==2,'Different task creates a separate unchecked item')
    check(len(sent)==1,'Automatic reconciliation never sends work to Codex')
    skipped=c.propose(project,'chat-a','Build the login screen','fourth')
    c.resolve(project,'chat-a',skipped['proposalId'],'Skip')
    check(len(Store(project).read()['tasks'])==2 and not c.view(project,'chat-a')['questions'],'Skip dismisses only the proposed addition')
    state=Store(project).read();rev=state['revision'];tid=first['taskId']
    c.toggle(project,tid,False,rev)
    check(rejects(lambda:c.toggle(project,tid,True,rev)),'Stale UI revisions cannot overwrite concurrent checklist edits')
    c.complete(project,tid,{'quote':'All login work is implemented and tested.'},time.time())
    check(not Store(project).read()['tasks'][0]['done'],'Automatic completion respects a manual unchecked override')
    Store(project).change(lambda s:s['tasks'][0].update(manualOverride=False,reopenedAt=time.time()))
    c.complete(project,tid,{'quote':'Old work was complete.'},time.time()-10)
    check(not Store(project).read()['tasks'][0]['done'],'Older evidence cannot complete newly reopened work')
    history=[{'id':'u1','role':'user','text':'Please implement account export.','chat':'chat-a','at':time.time()},
             {'id':'a1','role':'assistant','text':'The login page is implemented and all its checks passed.','chat':'chat-a','at':time.time()}]
    c.apply_inference(project,history,{'actions':[{'kind':'add','title':'Implement account export','evidenceId':'u1','quote':'Please implement account export.'}]})
    export=next(t for t in Store(project).read()['tasks'] if t['title']=='Implement account export')
    check(not export['done'],'Verified user-message evidence can add work from history')
    count=len(Store(project).read()['tasks'])
    c.apply_inference(project,history,{'actions':[{'kind':'add','title':'Made up task','evidenceId':'u1','quote':'This quote never occurred.'}]})
    check(len(Store(project).read()['tasks'])==count,'Invented extraction evidence is rejected')
    c.apply_inference(project,history,{'actions':[{'kind':'complete','taskId':tid,'evidenceId':'u1','quote':'Please implement account export.'}]})
    check(not Store(project).read()['tasks'][0]['done'],'A user request is not evidence of completed implementation')
    c.apply_inference(project,history,{'actions':[{'kind':'complete','taskId':tid,'evidenceId':'a1','quote':history[1]['text']}]})
    check(Store(project).read()['tasks'][0]['done'],'A matching assistant completion update can check off the item')
    c.propose(other,'chat-b','Other project task','other')
    check(len(Store(other).read()['tasks'])==1 and len(Store(project).read()['tasks'])==count,'Projects keep independent checklist stores')
    plan_item={'id':'plan-chat','cwd':str(other),'updatedAt':time.time(),'activity':{'turnId':'turn-p','updatedAt':time.time(),'plan':[{'title':'Verify deployment','done':False}]}}
    c.sync_plan(plan_item);plan_item['activity']['plan'][0]['done']=True;plan_item['activity']['updatedAt']=time.time();c.sync_plan(plan_item)
    check(next(t for t in Store(other).read()['tasks'] if t['title']=='Verify deployment')['done'],'A recorded plan completion updates its bound checklist item')
    state=Store(other).read();n=len(state['tasks']);c.sync_plan(plan_item)
    check(len(Store(other).read()['tasks'])==n,'Repeated plan polling cannot create repeated checklist items')
    restart=Checklists();check(restart.view(project,'chat-a')['tasks']==c.view(project,'chat-a')['tasks'],'Checklist and decisions survive a companion restart');restart.close()
    retry=c.propose(project,'chat-a','Add CSV reports','retry',text='Add CSV reports')['proposalId']
    def refused(*_):raise ValueError('Answer the pending permission first')
    check(rejects(lambda:c.delivery(project,'chat-a',retry,refused)),'An outstanding permission can block prompt delivery')
    check(any(d['id']==retry and d['status']=='notSent' for d in c.view(project,'chat-a')['deliveries']),'Blocked delivery remains explicitly saved and unsent')
    c.retry_delivery(project,'chat-a',retry,sender)
    check(sent[-1]==('chat-a','Add CSV reports'),'The user can explicitly send a saved task after answering the permission')
    uncertain=c.propose(project,'chat-a','Add audit history','uncertain',text='Add audit history')['proposalId']
    def timeout(*_):raise TimeoutError('not confirmed')
    check(rejects(lambda:c.delivery(project,'chat-a',uncertain,timeout)) and rejects(lambda:c.retry_delivery(project,'chat-a',uncertain,sender)),'Uncertain delivery cannot be blindly retried')
    # Semantically related titles need a question even with no lexical overlap.
    c.infer=lambda cwd,h,tasks:{'actions':[{'kind':'add','title':'Implement authentication','taskId':tid,'evidenceId':h[0]['id'],'quote':h[0]['text']}]}
    semantic=c.propose(project,'chat-a','Implement authentication','semantic',semantic=True)
    check(semantic['pending'],'Semantic matching can ask about related tasks with different wording')
    c.resolve(project,'chat-a',semantic['proposalId'],'Skip')
    historic=[{'id':'old','role':'assistant','chat':'chat-a','text':'The privacy policy is published and verified.','at':time.time()-100}]
    c.apply_inference(project,historic,{'actions':[{'kind':'addComplete','title':'Publish privacy policy','evidenceId':'old','quote':historic[0]['text']}]})
    check(next(t for t in Store(project).read()['tasks'] if t['title']=='Publish privacy policy')['done'],'Already finished work can be reconstructed from historical completion evidence')
    # A completed old plan cannot undo explicitly reopened extra work or churn revisions.
    plan_item['activity']['updatedAt']=time.time()-10
    Store(other).change(lambda s:next(t for t in s['tasks'] if t['title']=='Verify deployment').update(done=False,reopenedAt=time.time()))
    revision=Store(other).read()['revision'];c.sync_plan(plan_item)
    check(Store(other).read()['revision']==revision,'Stale completed plans neither recheck reopened work nor churn revisions')
    c.close()
    # Actual bidirectional connection to a deterministic protocol peer.
    managed=ManagedCodex(sys.executable,hub,atomic_json)
    peer=Path(__file__).with_name('check_codex_control.py')
    conn=CodexConnection([sys.executable,str(peer),'--server'],managed.event,managed.disconnected);managed.connection=conn
    chat=managed.start_task(str(project),'Test','Initial task')['selection']
    result=managed.add_work(chat,'Also add CSV export')
    check('ongoing' in result['text'] and managed.items[chat]['turnId']=='turn-1','Additional work steers the exact ongoing turn without starting another')
    check(managed.snapshot()[chat]['activity']['history'][-1]['text']=='Also add CSV export','Accepted steering appears in checklist history')
    conn.call('test/event',{'id':77,'method':'item/permissions/requestApproval','params':{'threadId':chat,'turnId':'turn-1','itemId':'p','permissions':{'network':{'enabled':True}}}})
    check(rejects(lambda:managed.add_work(chat,'Do more')) and not conn.call('test/replies',{})['replies'],'Additional work cannot approve or bypass a pending permission')
    check(rejects(lambda:managed.add_work('unowned','Do more')),'Read-only desktop chats cannot be taken over')
    managed.decide(chat,managed.snapshot()[chat]['approvals'][0]['id'],'deny')
    conn.call('test/event',{'method':'turn/completed','params':{'threadId':chat,'turn':{'id':'turn-1'}}})
    managed.add_work(chat,'Next task')
    check(managed.snapshot()[chat]['status']=='active','An idle owned chat accepts additional work in the same chat')
    managed.close()
    # Visible messages only. No reasoning or arbitrary tool output enters extraction.
    state={'notes':[],'questions':{},'approvals':{}}
    for role,channel,text in [('user',None,'Please build a checklist.'),('assistant','analysis','private reasoning'),('assistant','commentary','Checklist is built and checked.')]:
        LocalActivity.consume(state,{'type':'response_item','timestamp':'2026-10-22T00:00:00Z','payload':{'type':'message','role':role,'channel':channel,'content':[{'type':'input_text' if role=='user' else 'output_text','text':text}]}})
    check([e['text'] for e in state['history']]==['Please build a checklist.','Checklist is built and checked.'],'Only visible chat messages are used for history extraction')
    LocalActivity.consume(state,{'type':'response_item','payload':{'type':'function_call_output','output':'secret tool output'}})
    check(len(state['history'])==2,'General tool outputs are excluded from checklist context')
print(f'{len(checks)} checklist and additional-work checks passed')
for label in checks:print('PASS',label)
