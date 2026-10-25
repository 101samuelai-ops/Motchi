#!/usr/bin/env python3
"""Register Mochi's user permission hook; never grant trust or alter policy."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import shlex
import shutil
import sys


def install(config_root):
    root = Path(config_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    path = root / 'hooks.json'
    original = path.read_text() if path.exists() else None
    data = json.loads(original) if original else {}
    groups = data.setdefault('hooks', {}).setdefault('PermissionRequest', [])
    bridge = Path(__file__).with_name('dog_bridge.py').resolve()
    command = shlex.quote(sys.executable) + ' ' + shlex.quote(str(bridge)) + ' --permission-hook'
    # Exact command identifies older Mochi registrations without touching other hooks.
    for group in groups:
        group['hooks'] = [h for h in group.get('hooks', []) if not (
            h.get('type') == 'command' and '/progress-pet/' in h.get('command', '') and
            'dog_bridge.py' in h.get('command', '') and
            h.get('command', '').endswith(' --permission-hook'))]
    groups[:] = [g for g in groups if g.get('hooks')]
    groups.append({'hooks': [{'type': 'command', 'command': command, 'timeout': 600}]})
    result = json.dumps(data, indent=2) + '\n'
    if result != original:
        if original is not None:
            backup = path.with_name('hooks.json.mochi-backup-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
            shutil.copy2(path, backup)
        from hook_approvals import atomic
        atomic(path, data)
    print('Registered permission hook:', path)
    print('Command:', command)
    print('User action required: review/trust this exact hook in Codex /hooks, then reload the relevant session.')
    return path


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config-root', default=str(Path.home() / '.codex'))
    install(parser.parse_args().config_root)
