"""Loopback Mac voice test. Pair credentials stay in this process, never the page."""
import base64
from collections import deque
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
from pathlib import Path
import re
import secrets
import signal
import ssl
import sys
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit

ASSETS = Path(__file__).parent / 'app/src/main/assets'
SCRIPTS = Path(__file__).parent.parent / 'skills/completion-pet/scripts'

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_):
        raise ValueError('The Mac connection cannot redirect to another address.')

class MacConnection:
    def __init__(self, root, endpoint=None):
        sys.path.insert(0, str(SCRIPTS))
        from android_host import PortalStore, lan_address
        self.root = Path(root)
        port = json.loads((self.root / 'config.json').read_text()).get('port', 47831)
        self.endpoint = (endpoint or f'https://{lan_address()}:{port}').rstrip('/')
        url = urlsplit(self.endpoint)
        if url.scheme != 'https' or url.username or url.password or url.query or url.fragment or url.path or not ipaddress.ip_address(url.hostname).is_private:
            raise ValueError('Use the running Mac companion’s private HTTPS address.')
        self.ssl = ssl.create_default_context(cafile=str(self.root / 'server.pem'))
        self.ssl.check_hostname = False  # Exact private endpoint plus the local leaf certificate.
        self.opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=self.ssl), NoRedirect())
        self.token = None
        self.store = PortalStore(self.root)
        issued = None
        try:
            with self.store.lock:
                if self.store.db.execute('SELECT COUNT(*) FROM pairing WHERE expires>?', (time.time(),)).fetchone()[0]:
                    raise ValueError('A calendar pairing code is active. Finish that pairing before opening a live preview.')
            pin = hashlib.sha256(ssl.PEM_cert_to_DER_cert((self.root / 'server.pem').read_text())).hexdigest()
            ticket = self.store.issue(self.endpoint, pin).split('.', 1)[1]
            code = json.loads(base64.urlsafe_b64decode(ticket + '='*(-len(ticket) % 4)))['code']
            issued = hashlib.sha256(code.encode()).hexdigest()
            paired = self.request('/v1/pair', {'code': code, 'name': 'Local Mac voice preview'})
            self.token, self.device_id = paired['token'], paired['deviceId']
        except BaseException:
            if issued:
                with self.store.lock, self.store.db:
                    self.store.db.execute('DELETE FROM pairing WHERE code=?',(issued,))
            self.store.close()
            raise

    def request(self, path, body=None, method=None):
        headers = {'Content-Type': 'application/json'}
        if self.token:
            headers['Authorization'] = 'Bearer ' + self.token
        request = urllib.request.Request(self.endpoint + path,
                  data=json.dumps(body).encode() if body is not None else None,
                  headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=12) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            try: message = json.load(error).get('error', 'Mac request failed.')
            except (ValueError, OSError): message = 'Mac request failed.'
            raise ValueError(message) from None
        except OSError:
            raise ValueError('The Mac companion is unavailable. Keep Motchi open and try again.') from None

    def close(self):
        try:
            if self.token:
                # Revoke locally even if Wi-Fi changed during the preview.
                identity = self.store.authenticate(self.token)
                if identity:
                    self.store.revoke(identity)
        finally:
            self.token = None
            self.store.close()


class LivePreview:
    def __init__(self, connection, port=0, voice_test=False):
        self.connection = connection
        self.lock = threading.RLock()
        self.enabled = False
        self.voice_test = voice_test
        self.test_started = False
        self.context = {'projectId': None, 'selection': None}
        self.language = 'auto'
        self.events = deque(maxlen=32)
        self.turn = ''
        self.state = {'enabled': False, 'running': False, 'source': 'mac', 'language': 'auto',
                      'status': 'Tap Talk or enable wake listening to test the Mac microphone'}
        self.csrf = secrets.token_hex(32)
        self.closed = False
        preview = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_): pass
            def respond(self, status, content, mime='application/json'):
                if mime == 'application/json': content = json.dumps(content, ensure_ascii=False).encode()
                self.send_response(status)
                for key, value in {'Content-Type': mime, 'Cache-Control': 'no-store',
                        'X-Content-Type-Options': 'nosniff', 'Cross-Origin-Resource-Policy': 'same-origin',
                        'Content-Security-Policy': "frame-ancestors 'none'", 'Permissions-Policy': 'microphone=(), camera=()'}.items():
                    self.send_header(key, value)
                self.send_header('Content-Length', str(len(content))); self.end_headers(); self.wfile.write(content)
            def host_valid(self):
                return self.headers.get('Host') == preview.authority
            def do_GET(self):
                if not self.host_valid(): self.respond(403, {'error': 'Local preview only.'}); return
                name = 'index.html' if self.path == '/' else self.path.lstrip('/')
                if name not in {'index.html', 'app.js', 'app.css', 'appearance.css', 'appearance.js', 'native.js', 'core.js', 'dog.svg'}:
                    self.respond(404, {'error': 'Not found.'}); return
                content = (Path(__file__).with_name('preview_voice.js') if name == 'native.js' else ASSETS/name).read_bytes()
                if name == 'index.html':
                    content = content.replace(b'<head>', ('<head><meta name="motchi-preview" content="'+preview.csrf+'">').encode())
                    content = content.replace(b"connect-src 'none'", b"connect-src 'self'; media-src 'self' blob:")
                    content = content.replace(b'<body>', '<body class="preview-read-only"><div class="preview-banner">Motchi 0.18 live Mac test &middot; Real projects &middot; Work submissions disabled &nbsp; <span>Enable listening, then say Motchi / 莫奇 · English + 中文.</span></div>'.encode())
                if name == 'app.css':
                    content += b'\n.preview-banner{padding:12px 24px;background:#203b39;color:white;font:14px system-ui;display:flex;gap:12px;flex-wrap:wrap}.preview-banner span{opacity:.8}.preview-read-only #comment,.preview-read-only #send,.preview-read-only #changes button{display:none}.preview-read-only #checklist input{pointer-events:none}\n'
                mime = 'text/html' if name.endswith('.html') else 'text/css' if name.endswith('.css') else 'image/svg+xml' if name.endswith('.svg') else 'application/javascript'
                self.respond(200, content, mime)
            def do_POST(self):
                if self.path != '/api' or not self.host_valid() or self.headers.get('Origin') != preview.url.rstrip('/') or self.headers.get('X-Motchi-Preview') != preview.csrf:
                    self.respond(403, {'error': 'Open this preview directly in its local tab.'}); return
                try:
                    length = int(self.headers.get('Content-Length', '0'))
                    if not 0 < length <= 32000 or self.headers.get_content_type() != 'application/json':
                        raise ValueError('Invalid preview request.')
                    body = json.loads(self.rfile.read(length))
                    if not isinstance(body, dict): raise ValueError('Invalid preview request.')
                    self.respond(200, {'ok': True, 'data': preview.call(body)})
                except ValueError as error:
                    self.respond(400, {'ok': False, 'error': str(error)[:400]})
                except (KeyError, TypeError):
                    self.respond(400, {'ok': False, 'error': 'This preview supports project questions and Mac voice controls. Try again or use the installed app for other actions.'})
                except Exception:
                    self.respond(503, {'ok': False, 'error': 'Mac connection unavailable. Keep Motchi open and refresh.'})
        self.server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
        self.authority = '127.0.0.1:' + str(self.server.server_port)
        self.url = 'http://' + self.authority + '/'

    def control(self, restart_test=False, **extra):
        if self.voice_test:
            from microphone_policy import allowed
        if self.voice_test and (not self.test_started or
                restart_test and not allowed(self.connection.root, self.connection.device_id)):
            from microphone_policy import allow_test
            allow_test(self.connection.root, self.connection.device_id)
            self.test_started = True
        if self.voice_test and self.test_started:
            if not allowed(self.connection.root, self.connection.device_id):
                self.connection.request('/v1/mac-voice', {'enabled': False})
                self.enabled = False; self.events.clear()
                self.state = dict(self.state, enabled=False, running=False, busy=False, rms=0, recentRms=0,
                                  stage='idle', issue='', status='Voice test ended · tap Talk to start a new test')
                return self.state
        payload = dict(self.context, enabled=True, heartbeat=not restart_test,
                       conversationVersion=2, language=self.language, **extra)
        state = self.connection.request('/v1/mac-voice', payload)
        self.enabled = bool(state.get('enabled'))
        next_turn = state.get('turnId', '')
        if next_turn and next_turn != self.turn:
            self.turn = next_turn; self.events.clear()
        for event in state.pop('events', []):
            if event.get('projectId'):
                self.context = {k: event.get(k) for k in ('projectId', 'selection')}
            self.events.append(event)
        self.state = dict(state, source='mac', language=self.language)
        return self.state

    def call(self, body):
        with self.lock:
            action = body.get('action')
            if action == 'info': return {'paired': True}
            if action == 'snapshot': return self.connection.request('/v1/projects')
            if action == 'voiceContext':
                self.context = {k: body.get(k) or None for k in ('projectId', 'selection')}
                return {'saved': True}
            if action == 'voiceInfo': return self.control(speaking=body.get('speaking') is True) if self.enabled else self.state
            if action == 'voiceEvents':
                result = list(self.events); self.events.clear(); return {'events': result}
            if action == 'wakeListening':
                if type(body.get('enabled')) is not bool: raise ValueError('Choose whether to enable listening.')
                if body['enabled']: return self.control(restart_test=True)
                self.connection.request('/v1/mac-voice', {'enabled': False})
                self.enabled = False; self.events.clear()
                self.state = dict(self.state, enabled=False, running=False, speaking=False, busy=False,
                                  issue='', stage='idle', rms=0, recentRms=0, status='Mac microphone paused')
                return self.state
            if action in ('listenNow', 'finishVoice'): return self.control(restart_test=action=='listenNow', **{'activate' if action == 'listenNow' else 'finish': True})
            if action == 'voiceSource' and body.get('source') == 'mac': return self.state
            if action == 'voiceLanguage' and body.get('language') in ('en', 'zh', 'auto'):
                self.language = body['language']; return self.control() if self.enabled else dict(self.state, language=self.language)
            if action == 'quickAccessInfo': return {'enabled': False, 'visible': False, 'canPinShortcut': False}
            if action in ('job', 'voiceAudio'):
                identity = body.get('id', '')
                if not isinstance(identity, str) or not re.fullmatch(r'[a-zA-Z0-9-]{8,100}', identity): raise ValueError('Invalid operation.')
                return self.connection.request('/v1/'+('operations/' if action == 'job' else 'voice-audio/')+identity)
            if action == 'submit':
                request = body.get('request', {})
                if not isinstance(request, dict) or request.get('action') not in ('ask', 'discuss'): raise ValueError('Questions only in this preview.')
                return self.connection.request('/v1/operations', {k: request.get(k) for k in ('action', 'text', 'operationId', 'projectId', 'selection')})
            raise ValueError('Use the installed app for this action.')

    def close(self):
        with self.lock:
            if self.closed: return
            self.closed = True
            try:
                if self.enabled: self.connection.request('/v1/mac-voice', {'enabled': False})
            finally:
                try:
                    if self.voice_test:
                        from microphone_policy import finish_test
                        finish_test(self.connection.root, self.connection.device_id)
                    self.connection.close()
                finally: self.server.server_close()


def run(root, port=0, endpoint=None, voice_test=False):
    connection = MacConnection(root, endpoint)
    from microphone_policy import read, finish_test
    try:
        if voice_test:
            if not read(root)['paused']:
                raise ValueError('Pause Motchi microphones before starting a scoped voice test.')
        preview = LivePreview(connection, port, voice_test=voice_test)
    except BaseException:
        if voice_test:
            finish_test(root, connection.device_id)
        connection.close(); raise
    def stop(*_): raise KeyboardInterrupt
    previous = signal.signal(signal.SIGTERM, stop)
    print(preview.url, flush=True)
    try: preview.server.serve_forever()
    except KeyboardInterrupt: pass
    finally:
        try: preview.close()
        finally:
            if voice_test:
                finish_test(root, connection.device_id)
            signal.signal(signal.SIGTERM, previous)
