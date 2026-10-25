"""Explicit, one-shot decisions returned by the original PermissionRequest hook.

No log parsing can create a decision-capable request. The waiting hook owns an
OS lock; its original invocation is the only process that emits Codex's reply.
"""
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
import uuid


def atomic(path, value):
    fd, name = tempfile.mkstemp(prefix='.approval-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as out:
            json.dump(value, out, ensure_ascii=False)
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


class HookApprovals:
    def __init__(self, root):
        self.root = Path(root) / 'permission-replies'
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.client_id = uuid.uuid4().hex

    def heartbeat(self):
        atomic(self.root / ('client-' + self.client_id + '.json'), {'updatedAt': time.time()})

    def close(self):
        (self.root / ('client-' + self.client_id + '.json')).unlink(missing_ok=True)

    def online(self):
        for path in self.root.glob('client-*.json'):
            try:
                if time.time() - json.loads(path.read_text())['updatedAt'] < 20:
                    return True
            except (OSError, ValueError, KeyError, TypeError):
                pass
        return False

    def path(self, identity):
        if not isinstance(identity, str) or not identity.startswith('hook:'):
            raise ValueError('Not a live Mochi approval request.')
        token = identity[5:]
        if len(token) != 32 or any(c not in '0123456789abcdef' for c in token):
            raise ValueError('Invalid approval identity.')
        return self.root / (token + '.json')

    @contextmanager
    def locked(self, path):
        with path.with_suffix('.decision-lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield

    def live(self, path, record):
        if record.get('status') != 'pending' or record.get('expiresAt', 0) <= time.time():
            return False
        try:
            with path.with_suffix('.waiting-lock').open('a') as lock:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    return True
        except OSError:
            pass
        return False

    def records(self):
        result = []
        for path in self.root.glob('*.json'):
            if path.name.startswith('client-'):
                continue
            try:
                record = json.loads(path.read_text())
                if self.live(path, record):
                    result.append(record)
                elif time.time() - record.get('resolvedAt', record.get('expiresAt', time.time())) > 60:
                    # Tool arguments live only as long as needed for the pending
                    # decision and its short delivery acknowledgement.
                    with self.locked(path):
                        path.unlink(missing_ok=True)
                    path.with_suffix('.waiting-lock').unlink(missing_ok=True)
                    path.with_suffix('.decision-lock').unlink(missing_ok=True)
            except (OSError, ValueError, TypeError):
                continue
        return result

    @staticmethod
    def public(record):
        return {key: record[key] for key in ('id', 'turnId', 'callId', 'tool', 'reason', 'details', 'createdAt', 'expiresAt')} | {
            'source': 'permissionHook', 'kind': 'hook', 'canDecide': True, 'decisions': ['allow', 'deny']}

    def context(self, selection, identity):
        path = self.path(identity)
        try:
            record = json.loads(path.read_text())
        except (OSError, ValueError):
            raise ValueError('This approval is no longer pending.') from None
        if record.get('sessionId') != selection or not self.live(path, record) or record.get('decision'):
            raise ValueError('This approval has expired, disconnected, or already received a decision.')
        return self.public(record)

    def decide(self, selection, identity, decision, timeout=4):
        if decision not in ('allow', 'deny'):
            raise ValueError('Choose Allow once or Deny explicitly.')
        path = self.path(identity)
        with self.locked(path):
            self.context(selection, identity)
            record = json.loads(path.read_text())
            record['decision'] = decision
            atomic(path, record)
        # A queued click is not reported as a delivered Codex decision.
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            record = json.loads(path.read_text())
            if record.get('status') == 'delivered':
                return ('Allow' if decision == 'allow' else 'Deny') + ' sent to the original Codex permission request.'
            if not self.live(path, record):
                raise ValueError('The permission connection closed before delivery. No successful approval was confirmed.')
            time.sleep(.04)
        raise RuntimeError('Decision delivery is unconfirmed. Check the request state before trying again.')

    def cancel(self, session, turn=None):
        for record in self.records():
            if record.get('sessionId') != session or (turn and record.get('turnId') != turn):
                continue
            path = self.path(record['id'])
            with self.locked(path):
                fresh = json.loads(path.read_text())
                if fresh.get('status') == 'pending':
                    fresh.update(status='cancelled', resolvedAt=time.time())
                    atomic(path, fresh)

    def wait(self, event, timeout=540):
        """Called synchronously by Codex. Return {} on every non-decision path."""
        cwd, session = event.get('cwd'), event.get('session_id')
        if (event.get('hook_event_name') != 'PermissionRequest' or not isinstance(session, str) or not session
                or not isinstance(cwd, str) or not Path(cwd).is_absolute() or not self.online()):
            return {}
        tool = event.get('tool_name')
        if not isinstance(tool, str) or not tool:
            return {}
        arguments = event.get('tool_input', {})
        details = json.dumps(arguments, ensure_ascii=False, indent=2)
        if len(details) > 50000:
            return {}  # Never authorize a request whose full details cannot be shown.
        reason = next((arguments[k] for k in ('description', 'justification', 'reason')
                       if isinstance(arguments, dict) and isinstance(arguments.get(k), str) and arguments[k]), None)
        identity = 'hook:' + uuid.uuid4().hex
        path = self.path(identity)
        parent = os.getppid()
        record = {'id': identity, 'sessionId': session, 'cwd': str(Path(cwd).resolve()),
                  'turnId': event.get('turn_id', ''), 'callId': event.get('tool_use_id') or event.get('call_id'),
                  'tool': tool, 'reason': reason or tool + ' needs your approval.', 'details': details,
                  'digest': hashlib.sha256(details.encode()).hexdigest(),
                  'createdAt': time.time(), 'expiresAt': time.time() + timeout, 'status': 'pending'}
        with path.with_suffix('.waiting-lock').open('a') as waiter:
            fcntl.flock(waiter, fcntl.LOCK_EX)
            atomic(path, record)
            try:
                while time.time() < record['expiresAt']:
                    with self.locked(path):
                        fresh = json.loads(path.read_text())
                        if fresh.get('status') != 'pending':
                            return {}
                        if os.getppid() != parent or not self.online():
                            return {}
                        decision = fresh.get('decision')
                        if decision in ('allow', 'deny') and time.time() < record['expiresAt']:
                            # Commit under the same lock used by cancellation/decision.
                            fresh.update(status='delivered', resolvedAt=time.time())
                            atomic(path, fresh)
                            output = {'behavior': decision}
                            if decision == 'deny':
                                output['message'] = 'Denied by user in Mochi.'
                            return {'hookSpecificOutput': {'hookEventName': 'PermissionRequest', 'decision': output}}
                    time.sleep(.08)
                return {}
            finally:
                with self.locked(path):
                    fresh = json.loads(path.read_text())
                    if fresh.get('status') == 'pending':
                        fresh.update(status='disconnected' if time.time() < record['expiresAt'] else 'expired', resolvedAt=time.time())
                        atomic(path, fresh)


def run_hook(event, root):
    try:
        return HookApprovals(root).wait(event)
    except Exception:
        return {}  # Fall back to the native Codex approval flow, never auto-allow.
