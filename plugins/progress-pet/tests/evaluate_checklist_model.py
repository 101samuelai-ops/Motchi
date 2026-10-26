"""Optional signed-in Codex evaluation. Synthetic fixture only; normal usage applies.

Usage: python3 tests/evaluate_checklist_model.py --live [--report /tmp/report.json]
This is an accuracy smoke sample, not a guarantee or broad benchmark.
"""
import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'skills/completion-pet/scripts'))
from checklist_sync import model_infer
from dog_bridge import DogBridge

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--live', action='store_true', help='Use the configured Codex provider and sign-in')
parser.add_argument('--report', type=Path)
args=parser.parse_args()
if not args.live:
    parser.error('Pass --live to run the synthetic sample against your configured Codex model.')
fixture=json.loads(Path(__file__).with_name('fixtures').joinpath('history_review.json').read_text())
history=[{**e,'chat':'synthetic-chat','at':i+1} for i,e in enumerate(fixture['history'])]
bridge=object.__new__(DogBridge)
started=time.monotonic()
try:
    with tempfile.TemporaryDirectory(prefix='motchi-evaluation-') as project:
        output=model_infer(shutil.which('codex') or '/opt/homebrew/bin/codex', project, history, fixture['tasks'], bridge.isolated_config_flags)
except (OSError, RuntimeError, TimeoutError) as exc:
    report={'sample':'Synthetic 12-message mixed-intent smoke evaluation', 'status':'unavailable',
            'reason':str(exc), 'accuracyMeasured':False}
    print(json.dumps(report,indent=2))
    if args.report:args.report.write_text(json.dumps(report,indent=2)+'\n')
    sys.exit(2)
entries={e['id']:e for e in history}
matched=set();false_additions=0;unsupported_completions=0;invalid_evidence=0;duplicates=0
for action in output['actions']:
    entry=entries.get(action.get('evidenceId'));quote=action.get('quote','')
    if not entry or not isinstance(quote,str) or len(quote.strip())<8 or quote not in entry['text']:
        invalid_evidence+=1
    expected=next((i for i,e in enumerate(fixture['expected']) if action.get('kind')==e['kind'] and action.get('evidenceId') in e['evidenceIds'] and
                   (not e.get('taskId') or action.get('taskId')==e['taskId']) and
                   (not e.get('titleIncludes') or e['titleIncludes'] in action.get('title','').casefold())),None)
    if expected is None:
        if action.get('kind')=='add':false_additions+=1
        else:unsupported_completions+=1
    elif expected in matched:
        duplicates+=1
    else:matched.add(expected)
report={'sample':'Synthetic 12-message mixed-intent smoke evaluation','elapsedSeconds':round(time.monotonic()-started,2),
        'expected':len(fixture['expected']),'matched':len(matched),'missedCommitmentsOrCompletions':len(fixture['expected'])-len(matched),
        'falseAdditions':false_additions,'unsupportedCompletions':unsupported_completions,'invalidEvidence':invalid_evidence,
        'duplicateActions':duplicates,'actions':output['actions']}
print(json.dumps(report,indent=2))
if args.report:args.report.write_text(json.dumps(report,indent=2)+'\n')
sys.exit(0 if len(matched)==len(fixture['expected']) and not any((false_additions,unsupported_completions,invalid_evidence,duplicates)) else 1)
