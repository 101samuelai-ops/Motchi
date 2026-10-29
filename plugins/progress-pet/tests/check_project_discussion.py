"""History retrieval, routing, review-before-answer and read-only scope."""
import json
from pathlib import Path
import sys
import tempfile
import threading
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/completion-pet/scripts'))
import project_discussion as D
from checklist_sync import Checklists
from dog_bridge import DogBridge,checklist
from voice_companion import VoiceCompanion
checks=0
def check(value,label):
 global checks
 assert value,label
 checks+=1

with tempfile.TemporaryDirectory() as temp:
 root=Path(temp);alpha=root/'alpha';beta=root/'beta';alpha.mkdir();beta.mkdir()
 for p,name,title in ((alpha,'Alpha','Export account backups'),(beta,'Beta','Render calendar layout')):
  (p/'.progress-pet.json').write_text(json.dumps({'name':name,'tasks':[{'id':name,'title':title,'done':False}]}))
 rows=[{'id':'a-chat','cwd':str(alpha),'title':'Alpha build','status':'active','progress':checklist(alpha)},
       {'id':'a-review','cwd':str(alpha),'title':'Alpha review','status':'idle','progress':checklist(alpha)},
       {'id':'b-chat','cwd':str(beta),'title':'Beta build','status':'idle','progress':checklist(beta)}]
 projects=D.grouped(rows)
 check(len(projects)==2 and projects[0]['progress']['total']==1,'Duplicate project chats share one checklist count')
 check(D.route('How is Alpha doing?',projects)['projects'][0]['name']=='Alpha','A named project selects directly')
 check(D.route('Can account backups export?',projects)['projects'][0]['name']=='Alpha','Distinctive checklist topics select the relevant project')
 check(D.route('How are all projects doing?',projects)['scope']=='overview','Macro questions request all projects')
 check(D.route('Compare Alpha and Beta',projects)['scope']=='overview','Explicit comparison includes the named projects')
 check(D.route('Hello, how are you?',projects,projects[0]['id'])['scope']=='general','Ordinary conversation is not trapped in an old project')
 check(D.route('Hello Motchi',projects+[dict(projects[0],name='Motchi')],projects[0]['id'])['scope']=='general','Greeting the companion does not select the Motchi software project')
 check(D.route('What remains?',projects,projects[0]['id'])['scope']=='project','A project follow-up preserves context')
 check(D.route('How is Alpha?',projects+[dict(projects[1],name='Alpha',aliases=['Alpha'])])['scope']=='choice','Duplicate names require a choice')
 review=Checklists(history_path=root/'private.sqlite3')
 review.history.ingest(alpha,'a-chat',[{'id':'start','role':'user','text':'Implement account backup export.','at':1},
                                     {'id':'done','role':'assistant','text':'Account export is implemented and tests passed.','at':2}])
 review.history.ingest(beta,'b-chat',[{'id':'secret','role':'assistant','text':'Other project private evidence.','at':3}])
 retrieved=D.context_for(review.history,projects[0],'account backups')
 check(retrieved['availableSections']==2 and len(retrieved['messages'])==2,'Discussion retrieves both requirements and AI work evidence')
 check('Other project' not in json.dumps(retrieved),'History SQL is isolated to the exact project folder')
 for n in range(12):review.history.ingest(alpha,'a-chat',[{'id':str(n),'role':'assistant','text':'A long update '+('x'*4000),'at':n+4}])
 bounded=D.context_for(review.history,projects[0],'account export',budget=4000)
 check(sum(len(m['text']) for m in bounded['messages'])<=4000 and not bounded['complete'],'Retrieval has a visible bounded coverage instead of claiming every message was read')
 def infer(cwd,history,tasks):
  entry=next((e for e in history if e['text']=='Account export is implemented and tests passed.' and not e.get('contextOnly')),None)
  return {'actions':[{'kind':'complete','taskId':'Alpha','evidenceId':entry['id'],'quote':entry['text'],'reason':'Implementation and tests explicitly confirmed.'}]} if entry else {'actions':[]}
 review.infer=infer
 # Completion is in the oldest batch; recent-only review cannot declare it read.
 review.reconcile(str(alpha),rows[:2],'initial')
 check(checklist(alpha)['tasks'][0]['done'],'Verified assistant evidence checks off the existing task')
 bridge=object.__new__(DogBridge);bridge.checklists=review;bridge.ask_locks={};bridge.history={};bridge.snapshot=lambda:{'items':rows};captured=[]
 def ask(target,question,**options):captured.append((target,question,options));return 'Evidence-based answer'
 bridge.ask=ask
 result=bridge.discuss_result({'text':'How is Alpha?'})
 ctx=captured[-1][2]['discussion_context']
 check(result['scope']=='project' and len(ctx['projects'])==1 and ctx['projects'][0]['history']['messages'],'Project answers receive history context before generation')
 check(ctx['projects'][0]['checklist']['completed']==1,'Answers use the reconciled checkmark state')
 result=bridge.discuss_result({'text':'What needs attention across all projects?'})
 check(result['scope']=='overview' and len(captured[-1][2]['discussion_context']['projects'])==2,'Macro answers analyze distinct projects rather than duplicate chats')
 result=bridge.discuss_result({'text':'Let us discuss a new idea'})
 check(result['scope']=='general' and not result.get('routedSelection'),'General chat does not claim delivery or pin an arbitrary project')
 for request in ({'text':'What remains?','projectId':projects[0]['id'],'selection':'b-chat'},
                 {'text':'What remains?','projectId':'unknown-project'}):
  try:bridge.discuss_result(request);rejected=False
  except ValueError:rejected=True
  check(rejected,'A stale or mismatched explicit identity cannot silently select another project')
 bridge.ask=lambda *a,**k:json.dumps({'scope':'project','projectId':projects[1]['id'],'text':'Calendar details'})
 result=bridge.discuss_result({'text':'Can we talk about a new idea?'})
 check(result['projectId']==projects[1]['id'] and result['selection']=='b-chat','History analysis may resolve an otherwise general question to a supplied project')
 bridge.ask=lambda *a,**k:json.dumps({'scope':'project','projectId':'invented','text':'Invented project claims'})
 result=bridge.discuss_result({'text':'Can we talk about a new idea?'})
 check(result['scope']=='choice' and 'Invented project claims' not in json.dumps(result),'An invalid model project ID produces clarification instead of wrong-project claims')
 bridge.ask=lambda *a,**k:json.dumps({'scope':'project','projectId':projects[1]['id'],'text':'Wrong project answer','details':'Wrong details'})
 result=bridge.discuss_result({'text':'How is Alpha?'})
 check(result.get('summaryUnavailable') and 'Wrong' not in json.dumps(result),'A provider cannot replace an explicitly selected project, including hidden details')
 bridge.ask=lambda *a,**k:json.dumps({'scope':'general','projectId':None,'text':'Hello! What shall we discuss?','details':'','nextStep':'','caveat':'','evidence':[]})
 result=bridge.discuss_result({'text':'Hello'})
 check(not result['sources'] and not result.get('summaryUnavailable'),'General conversation shows no unrelated project coverage')
 pid=projects[0]['id'];context={'projects':[{'id':pid,'name':'Alpha','checklist':{'completed':1,'total':2},'history':{'messages':[
     {'id':'older','chat':'a-chat','role':'assistant','text':'Export is implemented and tested.','at':1},
     {'id':'newer','chat':'a-chat','role':'user','text':'The export still fails on my device.','at':2}]}}]}
 answer={'scope':'project','projectId':pid,'text':'Export is built, but it still fails on your device. It needs a fix before you can rely on it.',
         'details':'The later device report contradicts the earlier test claim.','nextStep':'Reproduce and fix the device failure.',
         'caveat':'A working device export has not been confirmed.','evidence':[{'projectId':pid,'chat':'a-chat','messageId':'newer','quote':'The export still fails on my device.'}]}
 display=D.presentation(json.dumps(answer),context,{pid})
 check(display['text']==answer['text'] and display['evidence'][0]['role']=='user','A concise assessment retains an exact later user report separately from its summary')
 check('messageId' not in display['text'] and display['nextStep']==answer['nextStep'],'The main answer separates the suggested action from reference metadata')
 for field,value in (('projectId','wrong-project'),('chat','b-chat'),('messageId','invented'),('quote','The export works perfectly.')):
  invalid=json.loads(json.dumps(answer));invalid['evidence'][0][field]=value
  display=D.presentation(json.dumps(invalid),context,{pid})
  check(display.get('summaryUnavailable') and not display['evidence'] and 'works perfectly' not in display['text'],
        'A fabricated or wrong-project '+field+' rejects the generated assessment')
 invalid=dict(answer,text='a'*901)
 check(D.presentation(json.dumps(invalid),context,{pid}).get('summaryUnavailable'),'An oversized summary is rejected without cutting off a qualifying sentence')
 check(D.presentation('provider unavailable',context,{pid},'项目进度如何？')['caveat'].startswith('实时总结'),'Provider failure returns a labelled Chinese count fallback')
 check('evidence' in D.answer_schema()['required'] and 'details' in D.answer_schema()['required'],'The provider contract includes summary and separate supporting references')
 text=['Hey Motchi, how are all projects doing?'];answers=[]
 voice=VoiceCompanion(lambda _:text[0],lambda:projects,lambda *a:None,lambda _:True,discuss=lambda r:answers.append(r) or {'scope':'overview','text':'Overview'})
 request={'generation':'generation-1234'}
 result=voice.run('device',request,b'audio')
 check(result['scope']=='overview' and answers,'Voice and typing share the same macro discussion path')
 text[0]='Something in the room'
 check(voice.run('device',{**request,'session':result['session']},b'audio')=={'wake':False} and len(answers)==1,'After a reply, ambient speech cannot trigger another answer')
 review.close();review.history.close()
print(f'{checks} project routing, history evidence, checklist and wake-only checks passed')
