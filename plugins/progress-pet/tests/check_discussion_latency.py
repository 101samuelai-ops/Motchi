"""Avoid redundant RPCs and long checklist waits during spoken discussion.

Uses an isolated answer executable and virtual review clock; no microphone,
real project history, model, or service credentials are needed.
"""
import json
from pathlib import Path
import sys
import tempfile
import time
import threading
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'skills/completion-pet/scripts'))
from dog_bridge import DogBridge
from android_host import AndroidPortal
from mac_voice import MacVoice

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

    # The structured final message is complete, but the CLI never sends its
    # turn/shutdown acknowledgement. It must not add ten seconds to the reply.
    code=worker.read_text()
    worker.write_text(code.replace("print(json.dumps({'type':'turn.completed'}),flush=True)",
                                   'import time; time.sleep(10)'))
    began=time.monotonic()
    answer=bridge.ask('alpha-chat','What remains?',discussion_context=context)
    check(json.loads(answer)['text']=='Export needs its device check.' and time.monotonic()-began<2,
          'A completed structured answer is returned without waiting for turn completion')
    worker.write_text('#!'+sys.executable+'\nimport time; time.sleep(10)\n')
    with patch('dog_bridge.VOICE_ANSWER_SECONDS',.1):
        began=time.monotonic()
        answer=bridge.ask('alpha-chat','项目进度？',discussion_context=dict(context,voiceTurn=True,fallback='Recorded counts only.'))
    check(time.monotonic()-began<2 and 'Recorded counts only.' in answer,
          'An unresponsive answer process is stopped and returns a labelled recorded fallback')

    # Bound the earlier context lookup too, including code stuck before ask().
    portal=object.__new__(AndroidPortal);release=threading.Event();checked=threading.Event();late=[]
    portal.discussion_slots=threading.BoundedSemaphore(3)
    def stuck(request):
        release.wait(2)
        try:request['_permitted']();late.append('saved')
        except ValueError:checked.set()
        return {'text':'obsolete'}
    portal.bridge=SimpleNamespace(discuss_result=stuck)
    with patch('android_host.VOICE_DISCUSSION_SECONDS',.1):
        began=time.monotonic()
        try:portal.discuss({'text':'项目进度？','_voice':True});timed_out=False
        except ValueError as error:timed_out='超时' in str(error)
    check(timed_out and time.monotonic()-began<1,'A stalled context lookup ends the request with a localized retry message')
    release.set()
    check(checked.wait(1) and not late,'A timed-out background lookup cannot save a late answer')

    voice=MacVoice(SimpleNamespace(device_permitted=lambda _:True))
    try:
        voice.owner='test';voice.epoch='turn';voice.busy=True;voice.stage='processing'
        notice=voice.processing_notice('test','turn',voice.question_revision,'项目进度？')
        check(notice and '整理回答' in notice['text'] and notice['processingNotice'],
              'A pending Chinese voice turn can get a brief spoken reassurance')
        voice.audio_ready('test','turn',notice)
        check(voice.events[-1]['audioOnly'],'Reassurance audio does not create a second answer or conversation entry')
        voice.busy=False;voice.events.clear()
        try:voice.audio_ready('test','turn',notice);obsolete=False
        except ValueError:obsolete=True
        check(obsolete and not voice.events,'A completed answer suppresses late reassurance audio')
        voice.busy=True;voice.question_revision+=1
        check(voice.processing_notice('test','turn',notice['noticeRevision'],'old') is None,
              'Resuming speech invalidates an earlier reassurance')
    finally:
        voice.owner=None;voice.close()

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
