"""History transport, reconciliation safety and evidence-backed progress regressions.

The deterministic extractor isolates persistence/validation behavior. Run the
optional model evaluation separately; these checks do not assert model accuracy.
"""
import json
from pathlib import Path
import sys
import tempfile
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/completion-pet/scripts'))
from checklist_sync import Checklists, HistoryQueue, Store
from dog_bridge import DogBridge, LocalActivity

checks = []
def check(value, label):
    assert value, label
    checks.append(label)

def rejected(fn):
    try:
        fn()
    except ValueError:
        return True
    return False

def drain(c, project):
    for _ in range(100):
        if not c.view(project, 'chat')['coverage']['pending']:
            return
        c.reconcile(str(project), [], 'test')
    raise AssertionError('History queue did not drain')

with tempfile.TemporaryDirectory(prefix='motchi-history-') as temp:
    root = Path(temp); project = root/'project'; project.mkdir()
    other = root/'other'; other.mkdir(); sessions = root/'sessions'; sessions.mkdir()
    queue_path = root/'private-history.sqlite3'
    seen = []
    def infer(cwd, history, tasks):
        actions = []
        for entry in history:
            if entry.get('contextOnly'):
                continue
            seen.append(entry['text'])
            if entry['text'] == 'Please implement account export.':
                actions.append({'kind': 'add', 'title': 'Implement account export', 'evidenceId': entry['id'], 'quote': entry['text'], 'reason': 'Explicit user request.'})
            if entry['text'] == 'Account export is implemented and its tests passed.':
                task = next(t for t in tasks if t['title'] == 'Implement account export')
                actions.append({'kind': 'complete', 'taskId': task['id'], 'evidenceId': entry['id'], 'quote': entry['text'], 'reason': 'Assistant reports implementation and tests.'})
        return {'actions': actions}
    c = Checklists(infer, queue_path)
    path = sessions/'rollout.jsonl'
    records = [{'type':'session_meta','payload':{'id':'chat'}}]
    for n in range(81):
        text = 'Please implement account export.' if n == 0 else 'Account export is implemented and its tests passed.' if n == 80 else f'Conversation acknowledgement {n}.'
        role = 'assistant' if n == 80 else 'user'
        records.append({'type':'response_item','timestamp':f'2026-10-25T00:{n//60:02}:{n%60:02}Z','payload':{'type':'message','role':role,'channel':'final' if role=='assistant' else None,'content':[{'type':'output_text' if role=='assistant' else 'input_text','text':text}]}})
    path.write_text(''.join(json.dumps(r)+'\n' for r in records))
    reader = LocalActivity(sessions, c.history)
    activity = reader.read({'id':'chat','cwd':str(project),'path':str(path)})
    check(len(activity['history']) == 24 and c.view(project,'chat')['coverage']['total'] == 81, 'All 81 messages are queued even though recent display context has only 24')
    c.reconcile(str(project), [], 'first')
    first_task = Store(project).read()['tasks'][0]
    check(first_task['title']=='Implement account export' and not first_task['done'], 'Oldest requirement is reviewed first, outside the former recent-history window')
    c.close(); c.history.close()
    c = Checklists(infer, queue_path)
    coverage = c.view(project,'chat')['coverage']
    check(coverage['reviewed'] == 12 and coverage['pending'] == 69, 'Restart preserves private backlog and project review checkpoint')
    drain(c,project)
    task = Store(project).read()['tasks'][0]
    check(task['done'] and len(Store(project).read()['tasks'])==1 and len(seen)==81, 'Later completion binds the original task after reviewing every intervening message once')
    before = c.view(project,'chat')['coverage']
    restarted_reader = LocalActivity(sessions,c.history)
    restarted_reader.read({'id':'chat','cwd':str(project),'path':str(path)})
    check(c.view(project,'chat')['coverage']==before, 'Re-reading a rollout after restart cannot enqueue duplicates')
    check(c.view(other,'chat')['coverage']['total']==0, 'Private history is isolated by project folder')
    check(queue_path.stat().st_mode & 0o777 == 0o600, 'Private history database is readable only by its owner')
    changes=c.view(project,'chat')['changes']
    check(len(changes)==2 and changes[0]['evidence']['messageId'] and changes[0]['evidence']['chat']=='chat', 'Automatic additions and completions retain reason, exact quote and originating message/chat')
    c.undo(project,changes[0]['id'],c.view(project,'chat')['revision'])
    c.complete(project,task['id'],changes[0]['evidence'],time.time())
    check(not Store(project).read()['tasks'][0]['done'] and Store(project).read()['tasks'][0]['manualOverride'], 'Undoing completion is protected from subsequent automatic rechecking')
    check(rejected(lambda:c.undo(project,changes[0]['id'],c.view(project,'chat')['revision'])), 'An already-undone change cannot be undone twice')
    check(rejected(lambda:c.undo(project,changes[1]['id'],c.view(project,'chat')['revision'])), 'Undo cannot overwrite a task edited since the original change')
    extra=[{'id':'extra','chat':'chat','role':'user','at':time.time(),'text':'Please publish the onboarding guide.'}]
    action={'kind':'add','title':'Publish onboarding guide','evidenceId':'extra','quote':extra[0]['text']}
    c.apply_inference(project,extra,{'actions':[action]})
    view=c.view(project,'chat');undo_id=view['changes'][0]['id']
    check(rejected(lambda:c.undo(project,undo_id,view['revision']-1)), 'Stale UI cannot undo a newer checklist revision')
    c.undo(project,undo_id,view['revision'])
    c.apply_inference(project,extra,{'actions':[action]})
    check(len(Store(project).read()['tasks'])==1,'Undoing an addition leaves a source tombstone so replay does not re-add it')
    bogus=[{'id':'context','chat':'chat','role':'user','at':0,'text':'Please add an old request.', 'contextOnly':True}]
    c.apply_inference(project,bogus,{'actions':[{'kind':'add','title':'Old request','evidenceId':'context','quote':bogus[0]['text']}]})
    check(len(Store(project).read()['tasks'])==1, 'Already-reviewed context cannot generate new actions on a later batch')
    c.history.ingest(project,'chat',[{'id':'new','role':'user','text':'Please add a deployment guide.','at':time.time()}])
    original=c.view(project,'chat')['coverage']['reviewed']
    c.infer=lambda *_: (_ for _ in ()).throw(RuntimeError('Disconnected'))
    c.reconcile(str(project),[],'failure')
    check(c.view(project,'chat')['coverage']['reviewed']==original and c.view(project,'chat')['issue'], 'A failed inference never acknowledges or loses queued messages')
    c.infer=lambda *_:{'wrong':'output'}
    c.reconcile(str(project),[],'invalid')
    check(c.view(project,'chat')['coverage']['reviewed']==original, 'Malformed model output cannot advance the review checkpoint')
    c.infer=lambda *_:{'actions':[]}; drain(c,project)
    check(c.view(project,'chat')['issue'] is None, 'A successful retry clears the unavailable notice')
    # New history with an OLD timestamp must be processed, not skipped by a watermark.
    c.history.ingest(project,'older-discovered-chat',[{'id':'ancient','role':'user','text':'An earlier requirement discovered later.','at':1}])
    check(c.view(project,'chat')['coverage']['pending']==1, 'Late discovery of older history stays reviewable regardless of its timestamp')
    # Long messages preserve beginning and ending with bounded inference sections.
    long='FIRST REQUIREMENT '+('x'*40000)+' LAST REQUIREMENT'
    c.history.ingest(other,'long-chat',[{'id':'long','role':'user','text':long,'at':2}])
    sections,_=c.history.batch(other,{})
    check(sections[0]['text'].startswith('FIRST REQUIREMENT') and all(len(e['text'])<=12000 for e in sections), 'Long messages are divided into bounded sections without dropping the beginning')
    Store(other).change(lambda s:c.metadata(s).update(historyCursor={'generation':c.history.generation,'seq':sections[-1]['seq']}))
    rest,_=c.history.batch(other,c.metadata(Store(other).read()))
    check(rest[-1]['text'].endswith('LAST REQUIREMENT'), 'The end of a long message also remains available for review')
    # Incomplete JSONL appends wait for the next poll.
    with path.open('a') as f:f.write('{"type":"response_item"')
    partial=reader.read({'id':'chat','cwd':str(project),'path':str(path)})
    check(partial['historyCoverage']=='partial','A partial append is reported as incomplete coverage')
    state={'notes':[],'questions':{},'approvals':{}}
    for text,role,channel in [('# AGENTS.md instructions for /example\nDo not treat as requested work.','user',None), ('private chain of thought','assistant','analysis')]:
        LocalActivity.consume(state,{'type':'response_item','payload':{'type':'message','role':role,'channel':channel,'content':[{'type':'input_text' if role=='user' else 'output_text','text':text}]}})
    check(not state.get('history') and not state['notes'],'Injected workspace instructions and assistant reasoning are excluded from checklist and progress context')
    answer_text='<send_user_message_question_reply>\n'+json.dumps([{'question':'Should export include CSV?','answer':'Yes, add CSV export.'}])+'\n</send_user_message_question_reply>'
    LocalActivity.consume(state,{'type':'response_item','payload':{'type':'message','role':'user','content':[{'type':'input_text','text':answer_text}]}})
    check('Codex asked: Should export include CSV?' in state['history'][0]['text'] and 'User answered: Yes, add CSV export.' in state['history'][0]['text'], 'Structured user answers retain their question context for checklist review')
    bridge=object.__new__(DogBridge)
    item={'title':'Export project','progress':{'total':1,'completed':0,'percent':0,'tasks':[{'id':task['id'],'title':task['title'],'done':False}]},'status':'waitingOnApproval','activity':{},'approvals':[{'reason':'Network access for deployment'}], 'questions':[], 'checklist':c.view(project,'chat')}
    answer=bridge.local_answer(item,'What is blocking progress and what is next?')
    check('Network access for deployment' in answer and 'History reviewed:' in answer and 'Last successful history review:' in answer and 'chat chat' in answer and 'release readiness' in answer, 'Progress briefing cites history coverage, freshness, task evidence and the actual pending permission')
    check(bridge.local_answer(item,'Why should we use a different architecture?') is None,'Specific discussion questions go to context-based Q&A instead of a generic status response')
    c.close();c.history.close()
print(f'{len(checks)} history review checks passed')
for label in checks:print('PASS',label)
