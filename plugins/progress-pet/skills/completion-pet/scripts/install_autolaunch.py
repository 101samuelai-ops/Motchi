#!/usr/bin/env python3
"""Install/remove a per-user Mochi launcher that follows Codex desktop starts."""
import argparse
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys

LABEL = 'local.mochi.codex-launcher'
SCRIPTS = Path(__file__).resolve().parent


def paths(home=None):
    home = Path(home or Path.home())
    support = home / 'Library/Application Support/Mochi'
    return support, support / 'Launcher', home / 'Library/LaunchAgents' / (LABEL + '.plist'), home / 'Library/Logs/Mochi'


def config_and_agent(app, home=None):
    support, launcher, plist, logs = paths(home)
    config = {'codexBundleIDs': ['com.openai.codex'], 'mochiAppPath': str(app),
              'statusPath': str(launcher / 'status.json'), 'logPath': str(logs / 'launcher.log')}
    agent = {'Label': LABEL, 'ProgramArguments': [str(launcher / 'MochiLauncher'), '--config', str(launcher / 'launcher.json')],
             'RunAtLoad': True, 'KeepAlive': True, 'ThrottleInterval': 30, 'ProcessType': 'Background',
             'LimitLoadToSessionType': 'Aqua',
             'EnvironmentVariables': {'PATH': '/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin'},
             'StandardOutPath': str(logs / 'launcher-stdout.log'), 'StandardErrorPath': str(logs / 'launcher-stderr.log')}
    return config, agent


def prepare(app, output):
    if sys.platform != 'darwin':
        raise RuntimeError('This launcher requires macOS.')
    if not (app / 'Contents/Info.plist').is_file():
        raise ValueError('Provide the complete Mochi.app path with --app.')
    info = plistlib.loads((app / 'Contents/Info.plist').read_bytes())
    if not str(info.get('CFBundleIdentifier', '')).startswith('local.progress-pet.'):
        raise ValueError('The provided app is not a Mochi companion bundle.')
    compiler = shutil.which('swiftc')
    if not compiler:
        raise RuntimeError('Apple Swift command-line tools are required to build the launcher.')
    output.mkdir(parents=True, exist_ok=True)
    binary = output / 'MochiLauncher'
    # Use the installed compiler directly when available; /usr/bin/swiftc is an
    # xcrun shim which otherwise needs a separate system temporary cache.
    direct = Path('/Library/Developer/CommandLineTools/usr/bin/swiftc')
    sdk = Path('/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk')
    if direct.exists() and sdk.exists():
        compiler = str(direct)
    scratch = output / 'tmp'; scratch.mkdir(exist_ok=True)
    environment = dict(os.environ, TMPDIR=str(scratch))
    command = [compiler, str(SCRIPTS / 'MochiLauncher.swift'), '-module-cache-path', str(output / 'modules')]
    if compiler == str(direct):
        command += ['-sdk', str(sdk)]
    subprocess.run(command + ['-o', str(binary)], env=environment, check=True)
    subprocess.run([str(binary), '--self-test'], check=True)
    support, launcher, plist, logs = paths()
    config, agent = config_and_agent(support / 'Mochi.app')
    (output / 'launcher.json').write_text(json.dumps(config, indent=2) + '\n')
    (output / (LABEL + '.plist')).write_bytes(plistlib.dumps(agent))
    return binary, config, agent


def install(app, output, login_app=False):
    binary, config, agent = prepare(app, output)
    support, launcher, plist, logs = paths()
    launcher.mkdir(parents=True, exist_ok=True)
    plist.parent.mkdir(parents=True, exist_ok=True)
    logs.mkdir(parents=True, exist_ok=True)
    # Install a stable app copy so moving/deleting the original output folder
    # does not break login startup. Do not restart a currently running companion.
    target = support / 'Mochi.app'
    if app != target:
        shutil.copytree(app, target, dirs_exist_ok=True, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    launch_path = target / 'Contents/Resources/launch.json'
    launch = json.loads(launch_path.read_text())
    launch.update({'--replace': False, '--report-on-start': False, '--log': str(logs / 'events.log')})
    launch_path.write_text(json.dumps(launch, indent=2) + '\n')
    destination = launcher / 'MochiLauncher'
    staged = destination.with_suffix('.new')
    shutil.copy2(binary, staged); staged.chmod(0o755); staged.replace(destination)
    (launcher / 'launcher.json').write_text(json.dumps(config, indent=2) + '\n')
    if login_app:
        helper = support / 'Mochi Launcher.app'
        executable = helper / 'Contents/MacOS/MochiLauncher'
        resources = helper / 'Contents/Resources'
        executable.parent.mkdir(parents=True, exist_ok=True)
        resources.mkdir(parents=True, exist_ok=True)
        shutil.copy2(binary, executable)
        executable.chmod(0o755)
        (resources / 'launcher.json').write_text(json.dumps(config, indent=2) + '\n')
        info = {'CFBundleIdentifier': LABEL + '.app', 'CFBundleName': 'Mochi Launcher',
                'CFBundleDisplayName': 'Mochi Launcher', 'CFBundleExecutable': 'MochiLauncher',
                'CFBundlePackageType': 'APPL', 'CFBundleVersion': '1',
                'CFBundleShortVersionString': '1.0', 'LSUIElement': True,
                'NSHighResolutionCapable': True, 'LSMinimumSystemVersion': '12.0'}
        (helper / 'Contents/Info.plist').write_bytes(plistlib.dumps(info))
        # The login app replaces the LaunchAgent; never install both.
        if plist.exists():
            shutil.copy2(plist, output / 'previous-launch-agent.plist')
            subprocess.run(['launchctl', 'bootout', 'gui/' + str(os.getuid()) + '/' + LABEL], capture_output=True, text=True)
            plist.unlink()
        print('Installed login helper:', helper)
        print('Add it in System Settings > General > Login Items > Open at Login.')
        return
    domain = 'gui/' + str(os.getuid())
    # This label belongs only to this launcher; existing Mochi/Codex processes
    # and their approval connections are never stopped here.
    if plist.exists():
        shutil.copy2(plist, output / 'previous-launch-agent.plist')
        subprocess.run(['launchctl', 'bootout', domain + '/' + LABEL], capture_output=True, text=True)
    plist.write_bytes(plistlib.dumps(agent))
    result = subprocess.run(['launchctl', 'bootstrap', domain, str(plist)], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError('Startup files are installed, but macOS did not load the launcher: ' + (result.stderr.strip() or result.stdout.strip()))
    print('Installed and loaded:', plist)
    print('Stable Mochi app:', target)
    print('Status:', launcher / 'status.json')
    print('Mochi will open quietly when Codex desktop starts. Existing Mochi is left running.')


def remove():
    support, launcher, plist, logs = paths()
    subprocess.run(['launchctl', 'bootout', 'gui/' + str(os.getuid()) + '/' + LABEL], capture_output=True, text=True)
    plist.unlink(missing_ok=True)
    print('LaunchAgent disabled. If using Mochi Launcher.app, also remove Mochi Launcher from System Settings > General > Login Items > Open at Login.')
    print('Mochi and its installed app are left intact.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app', type=Path)
    parser.add_argument('--output', type=Path, default=Path.cwd() / 'outputs/auto-launch')
    parser.add_argument('--install', action='store_true')
    parser.add_argument('--login-app', action='store_true', help='Install a normal app for macOS Login Items instead of a LaunchAgent')
    parser.add_argument('--remove', action='store_true')
    parser.add_argument('--status', action='store_true')
    args = parser.parse_args()
    if args.remove:
        remove(); return
    if args.status:
        support, launcher, plist, logs = paths()
        print('Startup file installed:', plist.exists())
        print('Login helper installed:', (support / 'Mochi Launcher.app').exists())
        print('Login helper registration is managed in System Settings > General > Login Items.')
        path = launcher / 'status.json'
        print(path.read_text() if path.exists() else 'No launcher status yet.')
        return
    if not args.app:
        parser.error('--app /absolute/path/Mochi.app is required')
    app = args.app.expanduser().resolve()
    if args.install:
        install(app, args.output.resolve(), login_app=args.login_app)
    else:
        binary, config, agent = prepare(app, args.output.resolve())
        print('Prepared launcher:', binary)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, RuntimeError, OSError, subprocess.CalledProcessError) as exc:
        sys.exit('Mochi auto-launch: ' + str(exc))
