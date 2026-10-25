"""Exercise actual separate waiting hook processes and explicit UI dispatch."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

scripts = Path(__file__).resolve().parents[1] / 'skills/completion-pet/scripts'
sys.path.insert(0, str(scripts))
from hook_approvals import HookApprovals
from dog_bridge import DogBridge
from install_approval_hook import install

checks = []
def check(value, text):
    assert value, text
    checks.append(text)

with tempfile.TemporaryDirectory() as folder:
    root = Path(folder)
    project = root / 'project'; project.mkdir()
    hooks = HookApprovals(root)
    event = {'hook_event_name': 'PermissionRequest', 'session_id': 'original-chat',
             'turn_id': 'original-turn', 'tool_use_id': 'original-call', 'cwd': str(project),
             'tool_name': 'Bash', 'tool_input': {'command': 'echo permission-fixture', 'description': 'Fixture only'}}
    def spawn(event=event, timeout=8):
        code = 'import json,sys;from hook_approvals import HookApprovals;print(json.dumps(HookApprovals(sys.argv[1]).wait(json.load(sys.stdin),float(sys.argv[2]))),flush=True)'
        process = subprocess.Popen([sys.executable, '-c', code, str(root), str(timeout)],
            env={**os.environ, 'PYTHONPATH': str(scripts)}, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        process.stdin.write(json.dumps(event)); process.stdin.close()
        return process
    def pending(process):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            records = hooks.records()
            if records:
                return records[-1]
            if process.poll() is not None:
                break
            time.sleep(.02)
        raise AssertionError('No waiting hook')
    def output(process):
        process.wait(timeout=4)
        return json.loads(process.stdout.read())

    process = spawn()
    check(output(process) == {}, 'No companion means native fallback, never automatic approval')
    hooks.heartbeat()
    process = spawn(); record = pending(process)
    check(record['callId'] == 'original-call' and record['turnId'] == 'original-turn', 'Request retains original call/turn binding')
    check(hooks.context('original-chat', record['id'])['canDecide'], 'A held waiting-process lock enables real buttons')
    check('echo permission-fixture' in hooks.context('original-chat', record['id'])['details'], 'Exact tool input is available for user review')
    for selection, identity, decision in [('other-chat', record['id'], 'allow'), ('original-chat', '../bad', 'allow'), ('original-chat', record['id'], 'yes')]:
        try:
            hooks.decide(selection, identity, decision)
            raise AssertionError('Invalid reply accepted')
        except ValueError:
            pass
    check(process.poll() is None, 'Wrong chat, invalid ID, and typed yes cannot decide the request')
    time.sleep(.1)
    check(process.poll() is None and not json.loads(hooks.path(record['id']).read_text()).get('decision'), 'Reading explanation context leaves permission pending')
    result = hooks.decide('original-chat', record['id'], 'allow')
    check('original Codex' in result, 'Button waits for original hook acknowledgement')
    check(output(process) == {'hookSpecificOutput': {'hookEventName': 'PermissionRequest', 'decision': {'behavior': 'allow'}}}, 'Allow returns official decision from original hook process')
    try:
        hooks.decide('original-chat', record['id'], 'deny')
        raise AssertionError('Double reply accepted')
    except ValueError:
        pass
    check(not hooks.records(), 'Consumed decisions cannot be reused')

    bridge = DogBridge(project, root=root)
    bridge.checklists.infer = None
    class Catalog:
        def call(self, *_):
            return {'data': [{'id': 'original-chat', 'cwd': str(project), 'name': 'Fixture project', 'updatedAt': 1}]}
        def close(self): pass
    bridge.server = Catalog()
    bridge.activity.read = lambda _: {'approvals': [{'id': 'log-only', 'callId': 'original-call', 'reason': 'Fixture only'}]}
    process = spawn(); record = pending(process)
    item = next(i for i in bridge.snapshot()['items'] if i['id'] == 'original-chat')
    check(len(item['approvals']) == 1 and item['approvals'][0]['canDecide'], 'Actual hook replaces its log mirror with direct decision buttons')
    check(not item.get('managedCodex'), 'Existing desktop chats need no duplicate owned task')
    answer = bridge.handle_action({'action': 'decideApproval', 'selection': 'original-chat', 'approvalId': record['id'], 'decision': 'deny'})
    check('Deny sent' in answer['text'], 'Normal Mochi UI action dispatches a hook decision')
    check(output(process)['hookSpecificOutput']['decision'] == {'behavior': 'deny', 'message': 'Denied by user in Mochi.'}, 'Deny returns a real Codex denial')
    item = next(i for i in bridge.snapshot()['items'] if i['id'] == 'original-chat')
    check(not item['approvals'][0].get('canDecide'), 'A log-only request never receives fake approval buttons')

    process = spawn(); record = pending(process)
    process.kill(); process.wait()
    check(not hooks.records(), 'Killed hook loses decision capability immediately')
    try:
        hooks.decide('original-chat', record['id'], 'allow')
        raise AssertionError('Dead hook accepted')
    except ValueError: pass
    check(not json.loads(hooks.path(record['id']).read_text()).get('decision'), 'Dead request cannot receive a queued allow')
    process = spawn(timeout=.2); record = pending(process)
    check(output(process) == {}, 'Expiry falls back without granting permission')
    process = spawn(); record = pending(process)
    hooks.cancel('different-chat')
    check(process.poll() is None, 'Cancellation of another chat does not affect this request')
    hooks.cancel('original-chat', 'original-turn')
    check(output(process) == {}, 'Original-turn cancellation clears request without approval')
    bridge.close(); hooks.close()
    check(not hooks.online(), 'Companion shutdown removes its availability heartbeat')

with tempfile.TemporaryDirectory() as folder:
    root = Path(folder)
    original = {'hooks': {'SessionStart': [{'hooks': [{'type': 'command', 'command': 'echo existing-start'}]}],
                'PermissionRequest': [{'matcher': 'Bash', 'hooks': [{'type': 'command', 'command': 'echo existing-policy'}]}]}}
    (root / 'hooks.json').write_text(json.dumps(original))
    install(root)
    first = (root / 'hooks.json').read_text()
    data = json.loads(first)
    check(data['hooks']['SessionStart'] == original['hooks']['SessionStart'], 'Installer preserves unrelated event handlers')
    check(data['hooks']['PermissionRequest'][0] == original['hooks']['PermissionRequest'][0], 'Installer preserves another permission policy and its matcher')
    install(root)
    check((root / 'hooks.json').read_text() == first, 'Repeated installation does not duplicate the Mochi handler')
    check(any(json.loads(p.read_text()) == original for p in root.glob('hooks.json.mochi-backup-*')), 'Existing hook configuration has a recoverable backup')
    check(not any('trust' in p.name or 'config.toml' == p.name for p in root.iterdir()), 'Installer never writes trust records or approval policy')

print(f'{len(checks)} hook approval checks passed')
for text in checks: print('PASS', text)
