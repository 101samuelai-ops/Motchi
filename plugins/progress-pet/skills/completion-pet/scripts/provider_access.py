"""Reuse a configured provider's shell credential for GUI-launched Codex children.

Only the selected provider's env_key from user configuration is requested.
Nothing is persisted, logged, placed in argv, or imported from project files.
"""
import os
from pathlib import Path
import pwd
import re
import secrets
import signal
import subprocess
import threading
import time
import tomllib

_lock = threading.Lock()
_cache = {}


def configured_key():
    root = Path(os.environ.get('CODEX_HOME', str(Path.home()/'.codex')))
    try:
        config = tomllib.loads((root/'config.toml').read_text())
        profile = config.get('profiles', {}).get(config.get('profile'), {})
        provider = profile.get('model_provider', config.get('model_provider', 'openai'))
        key = config.get('model_providers', {}).get(provider, {}).get('env_key')
        return key if isinstance(key, str) and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,127}', key) else None
    except (OSError, ValueError, TypeError, AttributeError):
        return None


def shell_value(key):
    shell = pwd.getpwuid(os.getuid()).pw_shell
    if shell not in ('/bin/zsh', '/bin/bash', '/bin/sh'):
        return None
    marker = 'MOTCHI_ENV_' + secrets.token_hex(16)
    # Startup output is ignored. The key name is a validated positional argument;
    # its value only travels through the private stdout pipe into process memory.
    command = 'printf "\\n%s\\n" "$2"; /usr/bin/printenv "$1"; printf "\\n%s\\n" "$2"'
    process = subprocess.Popen([shell, '-ilc', command, 'motchi-provider', key, marker],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        text=True, start_new_session=True, cwd=str(Path.home()))
    try:
        output, _ = process.communicate(timeout=5)
        pieces = output.split('\n'+marker+'\n')
        value = pieces[1].strip() if len(pieces)==3 else ''
        return value if value and len(value)<=16384 and '\n' not in value and '\x00' not in value else None
    except (subprocess.TimeoutExpired, UnicodeError):
        return None
    finally:
        if process.poll() is None:
            try: os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError: pass
            try: process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL); process.wait(timeout=1)


def environment():
    env = dict(os.environ)
    key = configured_key()
    if not key or env.get(key):
        return env
    with _lock:
        cached = _cache.get(key)
        if not cached or cached[0] <= time.monotonic():
            try: value = shell_value(key)
            except OSError: value = None
            cached = (time.monotonic() + (300 if value else 15), value)
            _cache[key] = cached
        if cached[1]: env[key] = cached[1]
    return env


def failure_code(message):
    """Reduce provider errors to safe codes; never return raw server messages."""
    message = str(message).lower()
    if 'missing environment variable' in message or any(x in message for x in ('unauthorized','invalid api key','invalid_api_key','authentication','401')):
        return 'authentication'
    if any(x in message for x in ('rate limit','rate_limit','quota','429')):
        return 'rate_limit'
    if any(x in message for x in ('model_not_found','model not found','does not support','unsupported model')):
        return 'configuration'
    if any(x in message for x in ('connection','network','dns','connect','timed out')):
        return 'connection'
    return 'unavailable'
