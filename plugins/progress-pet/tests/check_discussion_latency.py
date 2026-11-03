"""Avoid redundant RPCs and long checklist waits during spoken discussion.

Uses an isolated answer executable and virtual review clock; no microphone,
real project history, model, or service credentials are needed.
"""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'skills/completion-pet/scripts'))
from dog_bridge import DogBridge

checks = 0
def check(value, label):
    global checks
    assert value, label
    checks += 1

with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    worker = root/'answer'
    worker.write_text('#!'+sys.executable+'\n'+'''
import json, sys
args=sys.argv[1:]
assert args[args.index('--sandbox')+1]=='read-only'
assert args[args.index('--ask-for-approval')+1]=='never'
prompt=sys.stdin.read()
context=json.loads(prompt.split('DISCUSSION_CONTEXT_JSON:\\n')[1].split('\\nUSER_QUESTION:')[0])
assert context['projects'][0]['history']['messages'][0]['text']=='The export still needs a device check.'
answer=json.dumps({'scope':'project','projectId':'alpha','text':'Export needs its device check.','details':'','nextStep':'','caveat':'','evidence':[]})
print(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':answer}}),flush=True)
print(json.dumps({'type':'turn.completed'}),flush=True)
''')
    worker.chmod(0o700)
    bridge = object.__new__(DogBridge)
    bridge.root=root; bridge.project=str(root); bridge.codex=str(worker); bridge.history={}
    bridge.resolve=lambda _: {'title':'Alpha','cwd':str(root),'progress':{}}
    bridge.isolated_config_flags=lambda _: []
    def redundant_rpc(_):
        raise AssertionError('Discussion must not request legacy notes only to discard them.')
    bridge.recent_context=redundant_rpc
    context={'scope':'project','historyKey':'alpha','projects':[{'id':'alpha','history':{'messages':[
        {'text':'The export still needs a device check.'}]}}]}
    answer=bridge.ask('alpha-chat','What remains?',discussion_context=context)
    check(json.loads(answer)['text']=='Export needs its device check.',
          'The real answer subprocess receives retrieved history without a redundant notes RPC')
    check(not bridge.history,'An unvalidated provider response is not saved as displayed discussion')

    rows=[]
    for n in range(8):
        cwd=root/('project-'+str(n)); cwd.mkdir()
        rows.append({'id':'chat-'+str(n),'cwd':str(cwd),'title':'Project '+str(n),
                     'status':'active','progress':{'total':2,'completed':1,'tasks':[]}})
    now=[0.]; waits=[]; captured=[]
    class Review:
        history=None
        def review_now(self,cwd,items,timeout):
            waits.append(timeout); now[0]+=timeout
            return {'coverage':{'pending':1},'syncing':True}
    bridge.checklists=Review(); bridge.ask_locks={}
    bridge.snapshot=lambda: {'items':rows}
    bridge.ask=lambda target,question,**options: captured.append(options['discussion_context']) or json.dumps({
        'scope':'overview','projectId':None,'text':'Device checks remain.','details':'',
        'nextStep':'','caveat':'','evidence':[]})
    def history(_,project,question,**options):
        return {'availableSections':2,'selectedSections':1,'complete':False,'messages':[
            {'id':'latest','chat':project['selection'],'role':'user','at':2,'text':'The device check still fails.'}]}
    with patch('dog_bridge.time',SimpleNamespace(monotonic=lambda:now[0])), \
         patch('dog_bridge.discussion.context_for',side_effect=history), \
         patch('dog_bridge.checklist',return_value={'total':2,'completed':1,'tasks':[]}):
        result=bridge.discuss_result({'text':'How are all projects doing?','_voice':True})
        check(len(waits)==8 and sum(waits)<=1.000001,
              'Every project gets a review request while voice waits at most one second in total')
        check(len(captured[-1]['projects'])==8 and all(p['history']['messages'] for p in captured[-1]['projects']),
              'Bounding review wait does not skip any project or its latest available history')
        check(all(p['checklist']['completed']==1 and p['checklist']['total']==2 for p in captured[-1]['projects']),
              'Full checklist counts remain intact')
        check(all(s['reviewPending'] for s in result['sources']) and result.get('freshnessNotice'),
              'Ongoing reconciliation is visible instead of claiming a finished review')
        check(result['discussionTimings']=={'contextMs':1000,'providerMs':0,'totalMs':1000},
              'Context preparation and provider latency are measured separately without storing speech')
        waits.clear()
        bridge.discuss_result({'text':'How are all projects doing?'})
        check(round(sum(waits))==8,'Typed discussion retains its existing eight-second review budget')

print(f'{checks} discussion latency, history, freshness and isolation checks passed')
