"""Question delivery, reply isolation, cancellation, and MCP protocol behavior."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time

SCRIPTS=Path(__file__).resolve().parents[1]/'skills/completion-pet/scripts'
sys.path.insert(0,str(SCRIPTS))
import dog_bridge as dog
import mochi_mcp as mcp
checks=[]
def check(value,label):
    assert value,label
    checks.append(label)
class Metadata:
    def call(self,*_):return {'data':[]}
    def close(self):pass
with tempfile.TemporaryDirectory(prefix='mochi-question-test-') as temp:
    root=Path(temp);hub=root/'hub';hub.mkdir();a=root/'A';b=root/'B';a.mkdir();b.mkdir()
    bridge=dog.DogBridge(a,root=hub);bridge.server=Metadata();bridge.checklists.infer=None
    results=[]
    def ask(name,cancel=None,timeout=3):
        try:results.append(mcp.ask_user({'project_path':str(a),'project_name':name,'question':'Choose the theme?','options':['Forest','Ocean']},cancel,hub,timeout))
        except Exception as exc:results.append(exc)
    thread=threading.Thread(target=ask,args=('Alpha',));thread.start()
    deadline=time.monotonic()+2
    item=None
    while time.monotonic()<deadline:
        item=next((i for i in bridge.snapshot()['items'] if i.get('questions')),None)
        if item:break
        time.sleep(.01)
    check(item is not None and item['questions'][0]['canReply'],'Codex question appears as an answerable project popup')
    q=item['questions'][0]
    check(q['options']==['Forest','Ocean'],'Question choices are preserved')
    wrong='folder:'+str(a)
    try:bridge.reply_question(wrong,q['id'],'wrong project');rejected=False
    except ValueError:rejected=True
    check(rejected,'A different project cannot answer the pending request')
    bridge.reply_question(item['id'],q['id'],'Forest')
    thread.join(2)
    check(not thread.is_alive() and results[-1]['answer']=='Forest','Typed reply returns to the exact waiting Codex tool call')
    try:bridge.reply_question(item['id'],q['id'],'Ocean');rejected=False
    except ValueError:rejected=True
    check(rejected,'Answered questions reject a second reply')
    check(not next(i for i in bridge.snapshot()['items'] if i['id']==item['id'])['questions'],'Answered questions no longer trigger attention popups')
    cancel=threading.Event();cancel.set();ask('Cancelled',cancel)
    check(isinstance(results[-1],RuntimeError),'Cancellation ends the question without inventing an answer')
    ask('Expired',timeout=.05)
    check(isinstance(results[-1],TimeoutError),'Unanswered questions expire explicitly')
    check(not any(i['questions'] for i in bridge.snapshot()['items']),'Cancelled and expired questions leave no pending popup')
    key='b'*32
    dog.atomic_json(hub/'questions'/f'{key}.json',{'id':key,'cwd':str(a),'title':'Waiting','question':'Still deciding?','options':[],'createdAt':time.time(),'expiresAt':time.time()+5,'status':'pending','source':'mochi'})
    pending=mcp.wait_for_reply(key,root=hub,wait_seconds=.01)
    check(pending['status']=='waitingForReply' and pending['question_id']==key,'A short wait returns the same pending question without fabricating an answer')
    wait_item=next(i for i in bridge.snapshot()['items'] if any(q['id']==key for q in i['questions']))
    bridge.reply_question(wait_item['id'],key,'Ready now')
    check(mcp.wait_for_reply(key,root=hub,wait_seconds=1)['answer']=='Ready now','A later wait resumes the original request and receives its reply')
    event={'session_id':'session-a','cwd':str(a),'turn_id':'turn-a','hook_event_name':'PreToolUse','tool_name':'functions.request_user_input_async','tool_input':{'questions':[{'title':'Which target platform?','options':['Mac','Web']}]}}
    dog.hook_event(event,hub)
    item=next(i for i in bridge.snapshot()['items'] if i['id']=='session-a')
    check(item['questions'][0]['question']=='Which target platform?' and not item['questions'][0]['canReply'],'Built-in Codex questions are mirrored with reply-in-Codex routing')
    dog.hook_event({**event,'hook_event_name':'PostToolUse'},hub)
    check(bool(next(i for i in bridge.snapshot()['items'] if i['id']=='session-a')['questions']),'Async delivery completion keeps the question pending')
    dog.hook_event({**event,'hook_event_name':'UserPromptSubmit'},hub)
    check(not next(i for i in bridge.snapshot()['items'] if i['id']=='session-a')['questions'],'User reply clears the async hook alert')
    dog.hook_event({**event,'hook_event_name':'Stop','last_assistant_message':'Which color would you like?'},hub)
    check(bool(next(i for i in bridge.snapshot()['items'] if i['id']=='session-a')['questions']),'A final assistant clarification ending in a question is surfaced')
    dog.hook_event({**event,'hook_event_name':'UserPromptSubmit'},hub)
    check(not next(i for i in bridge.snapshot()['items'] if i['id']=='session-a')['questions'],'User follow-up clears a final-message question')
    result=subprocess.run([sys.executable,str(SCRIPTS/'mochi_mcp.py')],input='\n'.join([json.dumps({'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2024-11-05'}}),json.dumps({'jsonrpc':'2.0','id':2,'method':'tools/list'})])+'\n',capture_output=True,text=True,timeout=5)
    rows=[json.loads(r) for r in result.stdout.splitlines()]
    check(result.returncode==0 and rows[0]['result']['protocolVersion']=='2024-11-05' and rows[1]['result']['tools'][0]['name']=='ask_user','Standard MCP clients can initialize and discover the question tool')
print(f'{len(checks)} Codex question checks passed')
for label in checks:print('PASS',label)
