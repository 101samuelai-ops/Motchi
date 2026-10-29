"""Opt-in, paired LAN portal for the Android companion. No remote approvals.

This server shares a DogBridge instance with the desktop, not a second owner of
Codex tasks. Private credentials, comments, jobs and TLS keys live outside git.
"""
import argparse
from array import array
import base64
import fcntl
from concurrent.futures import ThreadPoolExecutor
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import io
import json
import math
import os
from pathlib import Path
import re
import secrets
import socket
import sqlite3
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import wave
from voice_companion import VoiceCompanion, spoken_wav
from mac_voice import MacVoice
import doubao_speech
from qwen_speech import Recognizer
from configure_doubao import save_private

SUPPORT = Path.home() / 'Library/Application Support/Mochi/android'
MAX_AUDIO = 16000 * 2 * 60 + 4096


def project_id(cwd):
    return hashlib.sha256(str(Path(cwd).resolve()).encode()).hexdigest()[:24]


def lan_address():
    if sys.platform=='darwin':
        # Prefer the physical default interface, including when a VPN installs
        # a virtual route. Never bake a user's router address into the service.
        candidates=[]
        try:
            route=subprocess.check_output(['/sbin/route','-n','get','default'],text=True,timeout=3,stderr=subprocess.DEVNULL)
            match=re.search(r'interface:\s*((?:en|bridge)\d+)',route)
            if match:candidates.append(match[1])
        except (OSError,subprocess.SubprocessError):pass
        for interface in dict.fromkeys(candidates+['en0','en1','en2']):
            try:
                address=subprocess.check_output(['/usr/sbin/ipconfig','getifaddr',interface],text=True,timeout=2,stderr=subprocess.DEVNULL).strip()
                if ipaddress.ip_address(address).is_private:return address
            except (OSError,ValueError,subprocess.SubprocessError):pass
        raise OSError('Connect the Mac to a local network before pairing.')
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(('192.0.2.1', 80))  # Route selection only; no datagram is sent.
        return sock.getsockname()[0]
    finally:
        sock.close()


def certificate(root):
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    key, cert = root / 'server.key', root / 'server.pem'
    if not key.exists() or not cert.exists():
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '3650',
                        '-keyout', str(key), '-out', str(cert), '-subj', '/CN=Motchi local companion'],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        key.chmod(0o600); cert.chmod(0o600)
    fingerprint = hashlib.sha256(ssl.PEM_cert_to_DER_cert(cert.read_text())).hexdigest()
    return key, cert, fingerprint


class PortalStore:
    def __init__(self, root, recover=False):
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(str(root / 'portal.sqlite3'), check_same_thread=False)
        (root / 'portal.sqlite3').chmod(0o600)
        with self.db:
            self.db.executescript('''
                CREATE TABLE IF NOT EXISTS devices(id TEXT PRIMARY KEY, token TEXT UNIQUE, name TEXT, at REAL, revoked INTEGER DEFAULT 0);
                CREATE TABLE IF NOT EXISTS pairing(code TEXT PRIMARY KEY, expires REAL);
                CREATE TABLE IF NOT EXISTS comments(id TEXT PRIMARY KEY, project TEXT, selection TEXT, text TEXT, at REAL);
                CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, device TEXT, signature TEXT, action TEXT, project TEXT, status TEXT, result TEXT, at REAL);
            ''')
            # Work may have reached Codex before shutdown. Never replay it.
            if recover:
                self.db.execute("UPDATE jobs SET status='uncertain', result=? WHERE status IN ('queued','running')",
                                (json.dumps({'error': 'Mac connection restarted. Check the project before sending work again.'}),))

    def issue(self, endpoint, fingerprint):
        code = secrets.token_urlsafe(18)
        with self.lock, self.db:
            self.db.execute('DELETE FROM pairing')
            self.db.execute('INSERT INTO pairing VALUES (?,?)', (hashlib.sha256(code.encode()).hexdigest(), time.time()+300))
        payload = {'url': endpoint, 'pin': fingerprint, 'code': code}
        return 'MOTCHI1.' + base64.urlsafe_b64encode(json.dumps(payload, separators=(',', ':')).encode()).decode().rstrip('=')

    def pair(self, code, name):
        if not isinstance(code, str) or not isinstance(name, str) or not 1 <= len(name) <= 80:
            raise ValueError('Invalid pairing request.')
        hashed = hashlib.sha256(code.encode()).hexdigest()
        with self.lock, self.db:
            row = self.db.execute('SELECT expires FROM pairing WHERE code=?', (hashed,)).fetchone()
            if not row or row[0] <= time.time():
                raise ValueError('Pairing code expired or was already used. Request another code on the Mac.')
            self.db.execute('DELETE FROM pairing WHERE code=?', (hashed,))
            token, identity = secrets.token_urlsafe(32), uuid.uuid4().hex
            self.db.execute('INSERT INTO devices(id,token,name,at) VALUES (?,?,?,?)',
                            (identity, hashlib.sha256(token.encode()).hexdigest(), name, time.time()))
            return {'token': token, 'deviceId': identity}

    def authenticate(self, token):
        with self.lock:
            row = self.db.execute('SELECT id FROM devices WHERE token=? AND revoked=0',
                                  (hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
            return row[0] if row else None

    def revoke(self, identity):
        with self.lock, self.db:
            self.db.execute('UPDATE devices SET revoked=1 WHERE id=?', (identity,))

    def comments(self, project):
        with self.lock:
            rows = self.db.execute('SELECT id,selection,text,at FROM comments WHERE project=? ORDER BY at DESC LIMIT 100', (project,)).fetchall()
            return [dict(zip(('id','selection','text','at'), row)) for row in rows]

    def close(self):
        with self.lock:
            self.db.close()


class AndroidPortal:
    def __init__(self, bridge, root=SUPPORT, host=None, port=47831, transcriber=None, speaker=spoken_wav):
        self.bridge, self.root = bridge, Path(root)
        self.host, self.port = host or lan_address(), port
        if not ipaddress.ip_address(self.host).is_private:
            raise ValueError('Choose a local network address.')
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.lease=(self.root/'service.lock').open('a')
        try: fcntl.flock(self.lease, fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            self.lease.close()
            raise ValueError('Android connection is already running in Motchi.')
        self.store = PortalStore(self.root)
        self.executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix='motchi-android')
        self.lock = threading.RLock()
        self.refresh_lock = threading.Lock()
        self.refreshing = threading.Event()
        self.refresh_started = 0
        self.project_locks = {}
        self.cache, self.cache_at = {}, 0
        self.transcriber = transcriber or self.transcribe
        self.speech_lock = threading.Lock()
        self.qwen = Recognizer(self.root)
        self.voice = VoiceCompanion(self.local_transcribe, lambda: self.read_snapshot().get('projects', []),
                                    self.voice_ask, self.device_permitted, transcribe_request=self.voice_transcribe,
                                    refine_addressed=self.refine_addressed,
                                    discuss=(self.discuss if hasattr(bridge,'discuss_result') else None))
        self.voice_audio = {}
        self.speaker = speaker
        self.mac_voice = MacVoice(self)
        self.pair_attempts = {}
        self.closed = False
        key, cert, self.fingerprint = certificate(self.root)
        portal = self
        class Handler(BaseHTTPRequestHandler):
            def setup(self):
                super().setup()
                self.connection.settimeout(15)
            def log_message(self, *_): pass  # Never log tokens, voice or project text.
            def response(self, status, payload):
                data = json.dumps(payload, ensure_ascii=False).encode()
                self.send_response(status)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.send_header('Cache-Control', 'no-store')
                self.send_header('X-Content-Type-Options','nosniff')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers(); self.wfile.write(data)
            def dispatch(self):
                try:
                    # Native clients have no browser Origin; arbitrary websites
                    # cannot call even the pairing endpoint.
                    if self.headers.get('Origin') or self.headers.get('Host') != portal.authority:
                        self.response(403, {'error':'Native paired devices only.'}); return
                    if self.command == 'POST' and self.path == '/v1/pair':
                        now = time.time(); peer = self.client_address[0]
                        with portal.lock:
                            recent = [t for t in portal.pair_attempts.get(peer,[]) if now-t<300]
                            if len(recent)>=5:
                                self.response(429,{'error':'Too many pairing attempts. Wait five minutes.'}); return
                            portal.pair_attempts[peer] = recent+[now]
                        body = self.body(4096)
                        self.response(200,portal.store.pair(body.get('code'), body.get('name','Calendar'))); return
                    auth = self.headers.get('Authorization','')
                    device = portal.store.authenticate(auth[7:]) if auth.startswith('Bearer ') else None
                    if not device:
                        self.response(401,{'error':'Device not paired or access revoked.'}); return
                    if self.command == 'GET' and self.path == '/v1/projects':
                        self.response(200, portal.read_snapshot()); return
                    if self.path == '/v1/speech-provider':
                        if self.command == 'POST':
                            provider=self.body(1024).get('provider')
                            if provider not in ('local','doubao','qwen'): raise ValueError('Choose Qwen, Whisper or Doubao speech.')
                            save_private(portal.root/'speech-provider.json',{'provider':provider})
                        elif self.command != 'GET': raise ValueError('Use the speech provider controls.')
                        self.response(200,doubao_speech.info(portal.root)); return
                    if self.path == '/v1/mac-voice':
                        if self.command == 'POST':
                            portal.mac_voice.control(device,self.body(4096))
                        elif self.command != 'GET':
                            raise ValueError('Use the Mac microphone controls.')
                        self.response(200,portal.mac_voice.poll(device)); return
                    if self.command == 'GET' and re.fullmatch(r'/v1/operations/[a-zA-Z0-9-]{8,100}',self.path):
                        self.response(200,portal.job(device,self.path.rsplit('/',1)[1])); return
                    if self.command == 'DELETE' and self.path == '/v1/device':
                        portal.store.revoke(device); self.response(200,{'revoked':True}); return
                    if self.command == 'POST' and self.path == '/v1/operations':
                        body = self.body(24000)
                        self.response(202,portal.submit(device,body)); return
                    if self.command == 'GET' and re.fullmatch(r'/v1/voice-audio/[a-zA-Z0-9-]{8,100}', self.path):
                        with portal.lock:
                            entry = portal.voice_audio.get((device, self.path.rsplit('/', 1)[1]))
                        self.response(200, {'wav': base64.b64encode(entry[1]).decode() if entry and time.monotonic()-entry[0]<120 else None}); return
                    if self.command == 'POST' and self.path == '/v1/voice':
                        body = self.body(900_000)
                        if body.get('cancel') is True:
                            portal.voice.cancel(device, str(body.get('generation', '')))
                            self.response(200, {'paused': True}); return
                        data = base64.b64decode(body.pop('audio', ''), validate=True)
                        if not 44 < len(data) <= 640044:
                            raise ValueError('Wake listening accepts speech segments up to 20 seconds.')
                        request = {k: body.get(k) for k in ('operationId', 'generation', 'session', 'projectId', 'selection', 'preview', 'activated', 'language')}
                        request.update(action='listen', audioHash=hashlib.sha256(data).hexdigest())
                        self.response(202, portal.submit(device, request, audio=data)); return
                    if self.command == 'POST' and self.path == '/v1/speech':
                        if self.headers.get('Content-Type') != 'audio/wav':
                            raise ValueError('Record mono 16kHz WAV audio.')
                        length = self.length(MAX_AUDIO)
                        data = self.rfile.read(length)
                        request = {'action':'transcribe','operationId':self.headers.get('X-Operation-ID'),
                                   'audioHash':hashlib.sha256(data).hexdigest()}
                        self.response(202,portal.submit(device,request,audio=data)); return
                    self.response(404,{'error':'Unknown Android action.'})
                except (ValueError,KeyError,TypeError) as exc:
                    self.response(400,{'error':str(exc)[:400]})
                except Exception:
                    self.response(503,{'error':'Mac connection unavailable. No automatic resend was attempted.'})
            def length(self, maximum):
                length = int(self.headers.get('Content-Length','0'))
                if not 0 < length <= maximum: raise ValueError('Request is empty or too large.')
                return length
            def body(self, maximum):
                if self.headers.get('Content-Type','').split(';')[0] != 'application/json':
                    raise ValueError('Use JSON requests.')
                result = json.loads(self.rfile.read(self.length(maximum)))
                if not isinstance(result,dict): raise ValueError('Request must be an object.')
                return result
            do_GET=dispatch
            do_POST=dispatch
            do_DELETE=dispatch
        try:
            self.server = ThreadingHTTPServer((self.host,self.port),Handler)
        except OSError:
            self.executor.shutdown(wait=False, cancel_futures=True)
            self.store.close()
            self.lease.close()
            raise
        # Only the listener that owns this endpoint may recover interrupted jobs.
        # An accidental second launch must not change a live request's status.
        with self.store.lock, self.store.db:
            self.store.db.execute("UPDATE jobs SET status='uncertain', result=? WHERE status IN ('queued','running')",
                (json.dumps({'error':'Mac connection restarted. Check the project before sending work again.'}),))
        self.server.daemon_threads = True
        self.port = self.server.server_port
        self.authority = self.host+':'+str(self.port)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(str(cert),str(key))
        self.server.socket = context.wrap_socket(self.server.socket,server_side=True)
        self.thread = threading.Thread(target=self.server.serve_forever,daemon=True,name='motchi-android-https')

    def start(self):
        self.thread.start()
        return self

    def pairing(self):
        return {'ticket':self.store.issue('https://'+self.authority,self.fingerprint),
                'address':'https://'+self.authority,'fingerprint':self.fingerprint,'expiresIn':300}

    def snapshot(self, force=False):
        with self.refresh_lock:
            if not force and time.monotonic()-self.cache_at<2:
                return self.cache
            raw = self.bridge.snapshot()
            groups = {}
            for item in raw.get('items',[]):
                identity = project_id(item['cwd'])
                group = groups.setdefault(identity, {'id':identity,'name':Path(item['cwd']).name,'cwd':item['cwd'],'chats':[]})
                group['chats'].append(item)
            projects=[]
            for group in groups.values():
                items=group.pop('chats')
                # One checklist per folder, not a sum of repeated chat views.
                from dog_bridge import checklist
                folder=Path(group.pop('cwd'))
                progress=checklist(folder)
                if progress.get('name') and progress['name']!='My project': group['name']=progress['name']
                short=re.split(r'[—–:]',group['name'],maxsplit=1)[0].strip()
                group.update(aliases=list(dict.fromkeys([group['name'],folder.name,short])),folderLabel=folder.parent.name+'/'+folder.name)
                primary=next((i for i in items if i.get('managedCodex') and i.get('status')=='active'),items[0])
                group.update(progress=progress,checklist=primary.get('checklist',{}),selection=primary['id'],
                             updatedAt=max(i.get('updatedAt',0) for i in items),
                             needsInput=any(i.get('questions') or i.get('approvals') for i in items),
                             active=any(i.get('status')=='active' for i in items),
                             chats=[{'id':i['id'],'title':i['title'],'canSend':bool(i.get('managedCodex')),
                                     'status':i.get('status','unknown')} for i in items],
                             comments=self.store.comments(group['id']),
                             questions=[{'id':q['id'],'question':q.get('question',''),'options':q.get('options',[]),
                                         'selection':i['id'],'source':q.get('source'),
                                         'canReply':q.get('source')=='checklist'} for i in items for q in i.get('questions',[])],
                             attention=[{'chat':i['title'],'text':a.get('reason','Approval requested'),
                                         'type':'approval'} for i in items for a in i.get('approvals',[])])
                projects.append(group)
            projects.sort(key=lambda p:(p['needsInput'],p['active'],p['updatedAt']),reverse=True)
            voice=self.root/'speech.json'
            try:
                config=json.loads(voice.read_text());speech=Path(config['binary']).is_file() and Path(config['model']).is_file()
            except (OSError,ValueError,KeyError): speech=False
            self.cache={'projects':projects,'updatedAt':time.time(),'catalogIssue':raw.get('catalogIssue'),
                        'speechAvailable':speech,'wakeVoiceAvailable':speech,'speechProvider':doubao_speech.info(self.root),
                        'scope':'Discovered local Mac projects'}
            self.cache_at=time.monotonic()
            return self.cache

    def read_snapshot(self):
        # Catalog discovery can take a while on the first run. Serve the last
        # observation immediately; never hold a device connection open for it.
        if not self.closed and time.monotonic()-self.cache_at>2 and not self.refreshing.is_set():
            self.refreshing.set()
            self.refresh_started=time.monotonic()
            def refresh():
                try: self.snapshot(force=True)
                except Exception:
                    self.cache = {**self.cache, 'catalogIssue':'Mac project refresh failed. Showing the last observation.'}
                finally: self.refreshing.clear()
            self.executor.submit(refresh)
        if self.cache:return self.cache
        return {'projects':[], 'updatedAt':None, 'loading':True, 'speechAvailable':False,
                'catalogIssue':'Mac is still opening project files. Check file-access prompts on the Mac.' if self.refreshing.is_set() and time.monotonic()-self.refresh_started>20 else None}

    def target(self, request, fresh=True):
        project=next((p for p in (self.cache or self.read_snapshot())['projects'] if p['id']==request.get('projectId')),None)
        if not project: raise ValueError('Project no longer available. Refresh before sending.')
        selection=request.get('selection') or project['selection']
        if not any(c['id']==selection for c in project['chats']):
            raise ValueError('Chat does not belong to the selected project.')
        if not fresh: return project,selection,None
        item=self.bridge.resolve(selection)
        if project_id(item['cwd'])!=project['id']:
            raise ValueError('Project changed. Refresh before sending.')
        return project,selection,item

    def submit(self, device, request, audio=None):
        operation=request.get('operationId')
        if not isinstance(operation,str) or not re.fullmatch(r'[a-zA-Z0-9-]{8,100}',operation):
            raise ValueError('A stable operation ID is required.')
        action=request.get('action')
        if action not in ('ask','discuss','comment','send','start','toggle','undo','resolveDuplicate','transcribe','listen'):
            raise ValueError('Action unavailable. Approval decisions stay on the Mac.')
        if action not in ('transcribe','listen','discuss'): self.target(request, fresh=False)
        if action == 'listen':
            if not isinstance(audio, bytes) or not 44 < len(audio) <= 640044:
                raise ValueError('Wake speech must be a bounded WAV recording.')
            with wave.open(io.BytesIO(audio), 'rb') as wav:
                if wav.getnchannels()!=1 or wav.getsampwidth()!=2 or wav.getframerate()!=16000 or not 0<wav.getnframes()<=320000:
                    raise ValueError('Wake speech must be mono 16kHz PCM, up to 20 seconds.')
        if action=='toggle' and type(request.get('done')) is not bool:
            raise ValueError('Choose a checked or unchecked task state.')
        if action in ('ask','discuss','comment','send','start'):
            text=request.get('text')
            if not isinstance(text,str) or not 1<=len(text.strip())<=3000:
                raise ValueError('Enter 1–3,000 characters.')
        if action=='start' and request.get('confirmed') is not True:
            raise ValueError('Confirm starting a new connected Codex chat.')
        signature=hashlib.sha256(json.dumps(request,sort_keys=True).encode()).hexdigest()
        with self.store.lock,self.store.db:
            old=self.store.db.execute('SELECT device,signature FROM jobs WHERE id=?',(operation,)).fetchone()
            if old:
                if old!=(device,signature): raise ValueError('Operation ID already used for another request.')
                return self.job(device,operation)
            if action == 'listen' and self.store.db.execute("SELECT 1 FROM jobs WHERE device=? AND action='listen' AND status IN ('queued','running')", (device,)).fetchone():
                raise ValueError('A voice segment is already being processed. No ambient audio was queued.')
            count=self.store.db.execute("SELECT COUNT(*) FROM jobs WHERE status IN ('queued','running')").fetchone()[0]
            if count>=24: raise ValueError('Motchi is busy. Wait for existing requests to finish.')
            self.store.db.execute('INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?)',
                (operation,device,signature,action,request.get('projectId'), 'queued','{}',time.time()))
        self.executor.submit(self.execute,device,dict(request),audio)
        return {'id':operation,'status':'queued'}

    def job(self, device, identity):
        with self.store.lock:
            row=self.store.db.execute('SELECT device,status,result,project FROM jobs WHERE id=?',(identity,)).fetchone()
        if not row or row[0]!=device: raise ValueError('Request not available for this device.')
        return {'id':identity,'status':row[1],'result':json.loads(row[2]),'projectId':row[3]}

    def execute(self, device, request, audio):
        identity=request['operationId'];action=request['action']
        status,result='done',{}
        try:
            with self.store.lock,self.store.db:
                self.store.db.execute("UPDATE jobs SET status='running' WHERE id=?",(identity,))
            # Revocation invalidates queued requests too.
            with self.store.lock:
                permitted=self.store.db.execute('SELECT revoked FROM devices WHERE id=?',(device,)).fetchone()
            if not permitted or permitted[0]: raise ValueError('Device access was revoked.')
            if action=='listen':
                result=self.voice.run(device, request, audio)
                if result.get('wake') and result.get('text') and not result.get('partial'):
                    try:
                        spoken = self.speaker(result['text'])
                        self.voice.allowed(device, request['generation'])
                        if spoken:
                            with self.lock:
                                self.voice_audio = {k:v for k,v in self.voice_audio.items() if time.monotonic()-v[0]<120}
                                if len(self.voice_audio)>=8: self.voice_audio.pop(next(iter(self.voice_audio)))
                                self.voice_audio[(device,identity)] = (time.monotonic(), spoken)
                            result['spokenReply']=True
                    except Exception:
                        result['spokenReply']=False
                        result['speechIssue']='Spoken reply unavailable. The answer is readable on screen.'
                # Unaddressed background segments must not leave durable logs.
                if result.get('partial') or not result.get('wake'):
                    with self.store.lock, self.store.db:
                        self.store.db.execute("DELETE FROM jobs WHERE device=? AND action='listen' AND status='done' AND at<?", (device,time.time()-120))
            elif action=='transcribe':
                result={'text':self.local_transcribe(audio)}
            elif action=='discuss':
                result=self.discuss(request)
            else:
                with self.lock:
                    project_lock=self.project_locks.setdefault(request['projectId'],threading.RLock())
                with project_lock:
                    project,selection,item=self.target(request)
                    with self.store.lock:
                        permitted=self.store.db.execute('SELECT revoked FROM devices WHERE id=?',(device,)).fetchone()
                    if not permitted or permitted[0]: raise ValueError('Device access was revoked.')
                    text=request.get('text','').strip()
                    if action=='ask': result=self.bridge.ask_result({'selection':selection,'text':text,'autoFollow':False})
                    elif action=='comment':
                        with self.store.lock,self.store.db:
                            self.store.db.execute('INSERT OR IGNORE INTO comments VALUES (?,?,?,?,?)',
                                (identity,project['id'],selection,text,time.time()))
                        result={'text':'Comment saved to this project. No work was sent to Codex.'}
                    elif action=='send':
                        if not item.get('managedCodex'): raise ValueError('This chat is tracked only. Choose Start connected chat to send work.')
                        result=self.bridge.handle_action({'action':'addWork','selection':selection,'text':text,'operationId':identity})
                    elif action=='start':
                        result=self.bridge.handle_action({'action':'startTask','selection':selection,'text':text})
                        result={**result,'text':'Connected Codex chat started in this project. Permission decisions stay on your Mac.','deliveryStatus':'accepted'}
                    elif action=='toggle':
                        result=self.bridge.handle_action({'action':'setChecklistDone','selection':selection,
                                                          'taskId':request.get('taskId'),'done':request.get('done'),'revision':request.get('revision')})
                    elif action=='undo':
                        result=self.bridge.handle_action({'action':'undoChecklistChange','selection':selection,
                                                          'changeId':request.get('changeId'),'revision':request.get('revision')})
                    elif action=='resolveDuplicate':
                        question=next((q for q in item.get('questions',[]) if q['id']==request.get('questionId') and q.get('source')=='checklist'),None)
                        if not question: raise ValueError('Checklist question is no longer pending.')
                        result=self.bridge.handle_action({'action':'replyQuestion','selection':selection,'questionId':question['id'],'text':request.get('answer')})
                    self.cache_at=0
        except TimeoutError:
            status='uncertain';result={'error':'Codex did not confirm delivery. Check the project before sending again.'}
        except Exception as exc:
            status='failed';result={'error':str(exc)[:500]}
        with self.store.lock,self.store.db:
            self.store.db.execute('UPDATE jobs SET status=?,result=? WHERE id=?',
                                  (status,json.dumps(result,ensure_ascii=False),identity))

    def transcribe(self, audio, language='auto', wake=False):
        if not audio or len(audio)>MAX_AUDIO: raise ValueError('Record up to 60 seconds.')
        with tempfile.TemporaryDirectory(prefix='motchi-voice-',dir=self.root) as directory:
            source=Path(directory)/'speech.wav';source.write_bytes(audio)
            with wave.open(str(source),'rb') as wav:
                if wav.getnchannels()!=1 or wav.getsampwidth()!=2 or wav.getframerate()!=16000 or not 0<wav.getnframes()<=16000*60:
                    raise ValueError('Record mono 16kHz PCM audio, up to 60 seconds.')
                samples=array('h',wav.readframes(wav.getnframes()))
                if sys.byteorder!='little': samples.byteswap()
                if not samples or math.sqrt(sum(n*n for n in samples)/len(samples))<80:
                    raise ValueError('The recording is too quiet. Speak closer to the calendar or type your question.')
            try:config=json.loads((self.root/'speech.json').read_text())
            except (OSError,ValueError): raise ValueError('Local speech engine is not configured. Typing still works.')
            binary,model=Path(config['binary']),Path(config['model'])
            if not binary.is_absolute() or not binary.is_file() or not model.is_absolute() or not model.is_file():
                raise ValueError('Local speech engine is unavailable. Use typing.')
            output=Path(directory)/'transcript'
            args=[str(binary),'-m',str(model),'-f',str(source),'-l',language,'-otxt','-of',str(output),'-nt']
            if wake and language == 'en': args += ['--prompt','Motchi. Hey Motchi. Project progress and checklist.']
            elif wake and language == 'zh': args += ['--prompt','莫奇。项目进度和任务清单。']
            proc=subprocess.run(args,
                                capture_output=True,timeout=180)
            if proc.returncode: raise ValueError('Local transcription failed. Try again or type your question.')
            text=output.with_suffix('.txt').read_text().strip()
            if not text: raise ValueError('No speech recognized. Try again or type your question.')
            return text[:3000]

    def device_permitted(self, device):
        with self.store.lock:
            row=self.store.db.execute('SELECT revoked FROM devices WHERE id=?', (device,)).fetchone()
        return bool(row and not row[0])

    def local_transcribe(self, audio):
        with self.speech_lock:
            if self.transcriber==self.transcribe and doubao_speech.selected(self.root)=='qwen':
                return self.qwen.recognize(audio)
            if self.transcriber==self.transcribe and doubao_speech.selected(self.root)=='doubao':
                return doubao_speech.recognize(self.root,audio)
            return self.transcriber(audio)

    def voice_transcribe(self, audio, request):
        language=request.get('language') or 'en'
        if language not in ('auto','en','zh'): raise ValueError('Choose English, Chinese or automatic speech language.')
        with self.speech_lock:
            if self.transcriber==self.transcribe and doubao_speech.selected(self.root)=='qwen':
                return self.qwen.recognize(audio,permitted=lambda:self.voice.allowed(request['_device'],request['generation']))
            if self.transcriber==self.transcribe and request.get('_addressed') is True and doubao_speech.selected(self.root)=='doubao':
                device,generation=request['_device'],request['generation']
                return doubao_speech.recognize(self.root,audio,
                    permitted=lambda:self.voice.allowed(device,generation),
                    on_text=lambda text:self.mac_voice.publish_transcript(device,generation,text))
            if self.transcriber == self.transcribe: return self.transcribe(audio,language=language,wake=True)
            return self.transcriber(audio)

    def refine_addressed(self, audio, request, local_text):
        return self.voice_transcribe(audio,request) if doubao_speech.selected(self.root)=='doubao' else local_text

    def discuss(self, request):
        if not hasattr(self.bridge,'discuss_result'):raise ValueError('Update the Mac companion for general and project discussion.')
        result=self.bridge.discuss_result({k:request.get(k) for k in ('text','projectId','selection')})
        self.cache_at=0
        return result

    def voice_ask(self, project, selection, text):
        self.target({'projectId': project['id'], 'selection': selection})
        return self.bridge.ask_result({'selection': selection, 'text': text, 'autoFollow': False})

    def close(self):
        if self.closed:return
        self.closed=True
        self.mac_voice.close()
        self.qwen.close()
        if self.thread.is_alive(): self.server.shutdown()
        self.server.server_close()
        self.executor.shutdown(wait=True,cancel_futures=True)
        self.store.close()
        self.lease.close()


def from_config(bridge, root=SUPPORT):
    config=Path(root)/'config.json'
    if not config.exists():return None
    data=json.loads(config.read_text())
    if not data.get('enabled'):return None
    return AndroidPortal(bridge,root,host=data.get('host') or None,port=int(data.get('port',47831))).start()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=SUPPORT)
    parser.add_argument('--enable',action='store_true')
    parser.add_argument('--host')
    parser.add_argument('--pair',action='store_true')
    parser.add_argument('--devices',action='store_true')
    parser.add_argument('--revoke')
    args=parser.parse_args()
    args.root.mkdir(mode=0o700,parents=True,exist_ok=True)
    if args.enable:
        (args.root/'config.json').write_text(json.dumps({'enabled':True,'host':args.host,'port':47831}))
        print('Android connection enabled for the next Motchi launch.')
    if args.devices or args.revoke or args.pair:
        store=PortalStore(args.root)
        if args.devices:
            print(json.dumps([dict(zip(('id','name','pairedAt','revoked'),r)) for r in store.db.execute('SELECT id,name,at,revoked FROM devices')]))
        if args.revoke:store.revoke(args.revoke);print('Device revoked.')
        if args.pair:
            config=json.loads((args.root/'config.json').read_text())
            _,_,fingerprint=certificate(args.root)
            print(store.issue('https://'+(config.get('host') or lan_address())+':'+str(config.get('port',47831)),fingerprint))
        store.close()

if __name__=='__main__':main()
