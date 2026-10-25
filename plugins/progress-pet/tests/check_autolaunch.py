"""Validate launchd argument boundaries and the generated per-user installation."""
import importlib.util
from pathlib import Path
import plistlib

source = Path(__file__).resolve().parents[1] / 'skills/completion-pet/scripts/install_autolaunch.py'
spec = importlib.util.spec_from_file_location('autolaunch', source)
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
home = Path('/Users/Example User')
app = home / 'Library/Application Support/Mochi/Mochi.app'
config, agent = module.config_and_agent(app, home)
assert agent['ProgramArguments'] == [str(home / 'Library/Application Support/Mochi/Launcher/MochiLauncher'),
    '--config', str(home / 'Library/Application Support/Mochi/Launcher/launcher.json')]
assert plistlib.loads(plistlib.dumps(agent)) == agent
assert config['codexBundleIDs'] == ['com.openai.codex']
assert config['mochiAppPath'] == str(app)
assert agent['RunAtLoad'] and agent['KeepAlive'] and agent['LimitLoadToSessionType'] == 'Aqua'
assert agent['Label'] == 'local.mochi.codex-launcher'
assert agent['StandardErrorPath'].startswith(str(home / 'Library/Logs/Mochi'))
print('7 launcher configuration checks passed: paths with spaces, plist encoding, exact Codex identity, stable app path, GUI login startup, dedicated job label, and local logs.')
