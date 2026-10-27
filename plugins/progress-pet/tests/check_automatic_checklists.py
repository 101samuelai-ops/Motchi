"""Automatic scope matching and live completion while history catches up."""
import copy
from pathlib import Path
import sys
import tempfile
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/completion-pet/scripts'))
from checklist_sync import Checklists, Store

checks = []
def check(value, label):
    assert value, label
    checks.append(label)

def entry(identity, text, role='user', at=None):
    return {'id': identity, 'text': text, 'role': role, 'chat': 'chat', 'at': at or time.time()}

def action(e, title, task=None, relation='none', kind='add'):
    return {'kind':kind, 'title':title, 'taskId':task, 'relation':relation,
            'evidenceId':e['id'], 'quote':e['text'], 'reason':'Compared requested outcomes and acceptance criteria.'}

with tempfile.TemporaryDirectory(prefix='motchi-auto-') as temp:
    project = Path(temp) / 'project'; project.mkdir()
    c = Checklists()
    original = c.propose(project, 'chat', 'Export invoices as CSV', 'initial')['taskId']
    e = entry('equivalent', 'Please add comma-separated invoice downloads.')
    c.apply_inference(project, [e], {'actions':[action(e, 'Download invoices in CSV', original, 'same')]})
    check(len(Store(project).read()['tasks']) == 1 and not c.view(project,'chat')['questions'],
          'Equivalent wording reuses task identity without a user question')
    e2 = entry('distinct', 'Also export invoices as PDF documents.')
    c.apply_inference(project, [e2], {'actions':[action(e2, 'Export invoices as PDF', original, 'different')]})
    check(len(Store(project).read()['tasks']) == 2 and not Store(project).read()['tasks'][1]['done'],
          'Similar wording with distinct deliverables automatically stays separate and unchecked')
    before = copy.deepcopy(Store(project).read()['tasks'])
    bogus = entry('bogus', 'Please add an invoice email button.')
    c.apply_inference(project, [bogus], {'actions':[action(bogus, 'Email invoices', 'other-project-id', 'same')]})
    check(Store(project).read()['tasks'] == before, 'Unknown target IDs cannot redirect a same-task decision')
    c.apply_inference(project, [e,e2], {'actions':[action(e, 'Download invoices in CSV', original, 'same'),action(e2, 'Export invoices as PDF', original, 'different')]})
    check(len(Store(project).read()['tasks']) == 2, 'Replayed matching decisions cannot duplicate tasks')
    check({m['decision'] for m in c.view(project,'chat')['matches']} == {'same','different'},
          'Automatic match decisions retain their reasons and source evidence')
    # Keep all older sections pending while explicitly reviewing the latest update.
    for n in range(40):
        c.history.ingest(project,'chat',[entry('old-'+str(n), 'Earlier conversation acknowledgement '+str(n)+'.')])
    done = entry('finished', 'Invoice CSV export is implemented and all export checks passed.', 'assistant')
    c.history.ingest(project,'chat',[done])
    def infer(cwd, history, tasks):
        return {'actions':[action(h, '', original, 'same', 'complete') for h in history
                           if not h.get('contextOnly') and h['text'] == done['text']]}
    c.infer = infer
    c.reconcile(str(project), [], 'live', recent=True)
    view = c.view(project,'chat')
    check(Store(project).read()['tasks'][0]['done'] and not Store(project).read()['tasks'][1]['done'],
          'A current completion checks its exact task without completing a related deliverable')
    check(view['coverage']['pending'] == 41 and view['lastLiveReviewedAt'],
          'Live completion is prioritized without falsely acknowledging older history')
    count = len(view['changes'])
    while c.view(project,'chat')['coverage']['pending']:
        c.reconcile(str(project), [], 'catch-up')
    check(len(c.view(project,'chat')['changes']) == count and c.view(project,'chat')['coverage']['reviewed'] == 41,
          'Historical catch-up reviews every section without repeating the live completion')
    c.undo(project,view['changes'][0]['id'],c.view(project,'chat')['revision'])
    c.reconcile(str(project), [], 'live-replay', recent=True)
    check(not Store(project).read()['tasks'][0]['done'], 'Undo remains protected during live replay')
    # Old UI questions migrate to automatic decisions without invoking any sender.
    legacy = {'id':'legacy','selection':'chat','title':'Download invoices CSV','source':'legacy-source','createdAt':time.time(),
              'status':'pending','candidateId':original,'text':'Please add invoice CSV download.','done':False}
    Store(project).change(lambda s:c.metadata(s)['proposals'].update(legacy=legacy))
    c.infer = lambda cwd,h,t: {'actions':[action(h[0], legacy['title'], original, 'same')]}
    c.review_proposals(project)
    p = Store(project).read()['mochi']['proposals']['legacy']
    check(p['taskId'] == original and p['status'] == 'ready' and p['text'],
          'Old duplicate questions resolve automatically while their work remains unsent')
    # A changing checklist must not be completed using a stale model comparison.
    late = entry('late', 'The invoice PDF export is complete and verified.', 'assistant')
    c.history.ingest(project,'chat',[late])
    previous = c.view(project,'chat')['coverage']['reviewed']
    pdf = Store(project).read()['tasks'][1]['id']
    def concurrent(cwd,h,tasks):
        Store(cwd).change(lambda s:s['tasks'][1].update(manualOverride=True))
        return {'actions':[action(h[-1], '', pdf, 'same', 'complete')]}
    c.infer = concurrent
    c.reconcile(str(project), [], 'concurrent')
    check(not Store(project).read()['tasks'][1]['done'] and c.view(project,'chat')['coverage']['reviewed'] == previous,
          'Concurrent correction invalidates stale analysis without discarding its history')
    # A similar completed plan is classified in the background, not shown as a question.
    plan_project = Path(temp)/'plan'; plan_project.mkdir()
    cp = Checklists(lambda cwd,h,t:{'actions':[action(h[0], 'Build the login screen', t[0]['id'], 'same')]})
    plan_id=cp.propose(plan_project,'chat','Build the login page','initial')['taskId']
    item={'id':'chat','cwd':str(plan_project),'activity':{'turnId':'p1','updatedAt':time.time(),'plan':[{'title':'Build the login screen','done':True}]}}
    cp.sync_plan(item)
    state=Store(plan_project).read();cp.sync_plan(item)
    check(Store(plan_project).read()['revision']==state['revision'] and not cp.view(plan_project,'chat')['questions'],
          'Repeated completed plans do not churn revisions or ask a duplicate question')
    cp.review_proposals(plan_project)
    check(len(Store(plan_project).read()['tasks'])==1 and Store(plan_project).read()['tasks'][0]['done'],
          'A semantically equivalent completed plan automatically checks off its existing task')
    cp.close();cp.history.close()
    c.close(); c.history.close()
print(f'{len(checks)} automatic checklist checks passed')
for label in checks: print('PASS', label)
