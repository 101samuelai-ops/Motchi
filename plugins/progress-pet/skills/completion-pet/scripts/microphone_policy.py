"""Local microphone pause. Paired clients cannot override it over HTTP."""
import argparse
import json
import os
from pathlib import Path
import tempfile
import time

MAX_TEST_SECONDS = 300


def path(root):
    return Path(root) / 'microphone-policy.json'


def read(root):
    try:
        policy = json.loads(path(root).read_text())
        if not isinstance(policy, dict) or type(policy.get('paused')) is not bool:
            raise ValueError()
        return policy
    except FileNotFoundError:
        return {'paused': False}
    except (OSError, ValueError):
        return {'paused': True}  # Invalid local state cannot start recording.


def save(root, policy):
    root = Path(root)
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.microphone-policy-', dir=root)
    try:
        with os.fdopen(fd, 'w') as output:
            json.dump(policy, output)
        os.replace(temporary, path(root))
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def allowed(root, device, now=None):
    policy = read(root)
    if not policy['paused']:
        return True
    now = time.time() if now is None else now
    start, end = policy.get('issuedAt'), policy.get('until')
    return bool(device and device == policy.get('testDevice')
                and type(start) in (int, float) and type(end) in (int, float)
                and start <= now < end <= start + MAX_TEST_SECONDS)


def pause(root):
    save(root, {'paused': True})


def allow_test(root, device, seconds=MAX_TEST_SECONDS):
    if not read(root)['paused'] or not isinstance(device, str) or not device:
        raise ValueError('Pause Motchi microphones before starting a scoped voice test.')
    if not 0 < seconds <= MAX_TEST_SECONDS:
        raise ValueError('A voice test lasts at most five minutes.')
    now = time.time()
    save(root, {'paused': True, 'testDevice': device, 'issuedAt': now, 'until': now + seconds})


def finish_test(root, device):
    if read(root).get('testDevice') == device:
        pause(root)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.home() / 'Library/Application Support/Mochi/android')
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--pause', action='store_true')
    action.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    save(args.root, {'paused': args.pause})
    print('Motchi Mac microphones paused.' if args.pause else 'Motchi Mac microphones may be enabled by a paired client.')


if __name__ == '__main__':
    main()
