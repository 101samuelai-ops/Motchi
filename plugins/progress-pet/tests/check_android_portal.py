"""Paired Android service: routing, TLS, revocation and durable command safety."""
import base64
import concurrent.futures
import io
import math
import struct
import json
from pathlib import Path
import ssl
import sys
import tempfile
import threading
import os
import time
import urllib.error
import urllib.request
import wave
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/completion-pet/scripts'))
from android_host import AndroidPortal, PortalStore, project_id
checks=[]
def check(value,label):
 assert value,label
 checks.append(label)
def rejects(fn):
 try:fn();return False
 except (ValueError,RuntimeError,urllib.error.HTTPError):return True
with tempfile.TemporaryDirectory(prefix='motchi-android-test-') as directory:
 root=Path(directory);a=root/'alpha';a.mkdir();b=root/'beta';b.mkdir()
 (a/'.progress-pet.json').write_text(json.dumps({'name':'Alpha','tasks':[{'id':'a','title':'Build export','done':True},{'id':'b','title':'Verify export','done':False}]}))
 class Bridge:
  def __init__(self):self.calls=[]
  def snapshot(self):return {'items':[
   {'id':'chat-a','cwd':str(a),'title':'Alpha build','updatedAt':3,'status':'active','managedCodex':True,'checklist':{'coverage':{'reviewed':3,'total':4}},'questions':[]},
   {'id':'chat-a-2','cwd':str(a),'title':'Alpha review','updatedAt':4,'status':'idle','managedCodex':False},
   {'id':'chat-b','cwd':str(b),'title':'Beta','updatedAt':5,'status':'idle','managedCodex':False,'approvals':[{'reason':'Access request'}]}]}
  def resolve(self,identity):return next(i for i in self.snapshot()['items'] if i['id']==identity)
  def ask_result(self,request):self.calls.append(request);return {'text':'Recorded project answer','routedSelection':request['selection']}
  def handle_action(self,request):self.calls.append(request);return {'text':'Confirmed work delivery','routedSelection':request['selection']}
 bridge=Bridge();portal=AndroidPortal(bridge,root/'private',host='127.0.0.1',port=0,transcriber=lambda data:'How is Alpha doing?').start()
 context=ssl.create_default_context(cafile=str(root/'private/server.pem'));context.check_hostname=False
 def http(path,method='GET',body=None,token=None,headers=None):
  h={'Content-Type':'application/json'}
  if token:h['Authorization']='Bearer '+token
  h.update(headers or {})
  data=json.dumps(body).encode() if body is not None else None
  request=urllib.request.Request('https://'+portal.authority+path,data=data,headers=h,method=method)
  with urllib.request.urlopen(request,context=context,timeout=5) as response:return json.load(response)
 check(rejects(lambda:http('/v1/projects')),'Project data requires authentication')
 check(rejects(lambda:http('/v1/pair','POST',{'code':'wrong'},headers={'Origin':'https://malicious.example'})),'Browser origins cannot pair or control projects')
 ticket=portal.pairing()['ticket'];details=json.loads(base64.urlsafe_b64decode(ticket[8:]+'='*(-len(ticket[8:])%4)))
 check(details['pin']==portal.fingerprint and details['url'].startswith('https://'),'Pairing ticket binds the exact TLS certificate and endpoint')
 paired=http('/v1/pair','POST',{'code':details['code'],'name':'Test calendar'});token=paired['token'];device=paired['deviceId']
 check(portal.store.authenticate(token)==device,'One-time pairing creates an authenticated device')
 check(rejects(lambda:portal.store.pair(details['code'],'another')),'A consumed pairing code cannot be reused')
 exp=portal.pairing()['ticket'];exp=json.loads(base64.urlsafe_b64decode(exp[8:]+'='*(-len(exp[8:])%4)))
 with portal.store.lock,portal.store.db:portal.store.db.execute('UPDATE pairing SET expires=0')
 check(rejects(lambda:portal.store.pair(exp['code'],'late')),'Expired pairing codes cannot grant access')
 portal.snapshot(force=True)
 snapshot=http('/v1/projects',token=token);projects=snapshot['projects'];alpha=next(p for p in projects if p['name']=='Alpha');beta=next(p for p in projects if p['name']=='beta')
 check(len(projects)==2 and len(alpha['chats'])==2,'Chats in the same folder become one project card')
 check(alpha['progress']['percent']==50 and alpha['progress']['total']==2,'Project progress counts its shared checklist only once')
 check(beta['progress']['percent'] is None,'Missing checklists keep progress unknown')
 check(projects[0]['id']==beta['id'] and projects[0]['needsInput'],'Projects needing input rank before active projects')
 check('cwd' not in alpha and 'token' not in json.dumps(snapshot),'Project snapshots omit filesystem routes and credentials')
 def wait(identity):
  for _ in range(100):
   job=http('/v1/operations/'+identity,token=token)
   if job['status'] not in ('queued','running'):return job
   time.sleep(.01)
  raise AssertionError('Job never completed')
 request={'action':'comment','operationId':'comment-1234','projectId':alpha['id'],'selection':'chat-a','text':'Export needs review.'}
 http('/v1/operations','POST',request,token);result=wait(request['operationId'])
 check(result['status']=='done' and not bridge.calls,'Saving a comment never starts a Codex task')
 http('/v1/operations','POST',request,token);wait(request['operationId'])
 check(len(portal.store.comments(alpha['id']))==1 and not portal.store.comments(beta['id']),'Comment retries are idempotent and scoped to their project')
 check(rejects(lambda:portal.submit(device,{**request,'text':'Different content'})),'Operation IDs cannot be reused with changed payloads')
 check(rejects(lambda:portal.submit(device,{**request,'operationId':'cross-project','selection':'chat-b'})),'Another project chat cannot receive this project action')
 ask={**request,'action':'ask','operationId':'ask-123456'};portal.submit(device,ask);wait(ask['operationId'])
 check(bridge.calls[-1]['selection']=='chat-a' and not bridge.calls[-1]['autoFollow'],'Discussion uses the exact chosen chat without automatic topic drift')
 send={**request,'action':'send','operationId':'send-123456'};portal.submit(device,send);wait(send['operationId'])
 check(bridge.calls[-1]['action']=='addWork' and bridge.calls[-1]['operationId']==send['operationId'],'Explicit work retains the exact selection and stable submission ID')
 portal.submit(device,send);wait(send['operationId'])
 check(sum(c.get('action')=='addWork' for c in bridge.calls)==1,'Repeated network submission cannot send duplicate work')
 unsupported={**send,'selection':'chat-a-2','operationId':'tracked-only'};portal.submit(device,unsupported)
 check(wait(unsupported['operationId'])['status']=='failed','Tracked-only desktop chats cannot receive injected instructions')
 check(rejects(lambda:portal.submit(device,{**request,'action':'start','operationId':'start-123456'})),'Starting a connected chat requires explicit confirmation')
 check(rejects(lambda:portal.submit(device,{**request,'action':'decideApproval','operationId':'approval-123'})),'Remote clients cannot request approval decisions')
 other_device=portal.store.pair(json.loads(base64.urlsafe_b64decode(portal.pairing()['ticket'][8:]+'=='))['code'],'other')['deviceId']
 check(rejects(lambda:portal.job(other_device,request['operationId'])),'Another paired device cannot read private request results')
 with portal.store.lock,portal.store.db:
  portal.store.db.execute("INSERT INTO jobs VALUES ('interrupted-job',?,'x','send',?,'running','{}',0)",(device,alpha['id']))
 admin=PortalStore(root/'private');admin.close()
 check(portal.job(device,'interrupted-job')['status']=='running','Opening administration does not rewrite active jobs')
 check(rejects(lambda:AndroidPortal(bridge,root/'private',host='127.0.0.1',port=0)),'A second service cannot acquire the same private state or rewrite live jobs')
 check(portal.job(device,'interrupted-job')['status']=='running','Rejected duplicate startup preserves a live operation')
 check(rejects(lambda:portal.submit(device,{**request,'action':'toggle','done':'yes','operationId':'bad-checkbox'})),'Checkbox edits reject non-boolean states')
 # Exercise the actual WAV validation and local process boundary, without a cloud service.
 def wav(channels=1,rate=16000,seconds=.1,silent=False):
  stream=io.BytesIO()
  with wave.open(stream,'wb') as out:
   out.setnchannels(channels);out.setsampwidth(2);out.setframerate(rate);out.writeframes(b''.join(struct.pack('<h',0 if silent else int(1800*math.sin(n*.1))) for n in range(int(rate*seconds)*channels)))
  return stream.getvalue()
 model=root/'model.bin';model.write_bytes(b'fixture')
 binary=root/'whisper-test'
 binary.write_text('#!'+sys.executable+'\nimport sys\nfrom pathlib import Path\nassert sys.argv[sys.argv.index("-l")+1]=="auto"\nPath(sys.argv[sys.argv.index("-of")+1]+".txt").write_text("What is finished?")\n')
 binary.chmod(0o700)
 (root/'private/speech.json').write_text(json.dumps({'binary':str(binary),'model':str(model)}))
 previous=set((root/'private').glob('motchi-voice-*'))
 check(portal.transcribe(wav())=='What is finished?','Valid audio runs the configured local multilingual engine')
 check(set((root/'private').glob('motchi-voice-*'))==previous,'Temporary audio and transcripts are removed after processing')
 check(rejects(lambda:portal.transcribe(wav(silent=True))),'Silent recordings prompt the user to retry instead of hallucinating a transcript')
 check(rejects(lambda:portal.transcribe(wav(channels=2))),'Stereo recordings are rejected')
 check(rejects(lambda:portal.transcribe(wav(rate=8000))),'Unexpected sample rates are rejected')
 check(rejects(lambda:portal.transcribe(wav(seconds=61))),'Recordings over 60 seconds are rejected')

 discussions=[]
 def discuss_result(request):
  discussions.append(request)
  return {'scope':'general','text':'General conversation without executing work.'}
 bridge.discuss_result=discuss_result
 general={'action':'discuss','operationId':'general-discuss-123','text':'Hello Motchi'}
 before_work=len(bridge.calls)
 check(rejects(lambda:http('/v1/operations','POST',general)),'General discussion still requires device authentication')
 http('/v1/operations','POST',general,token);general_result=wait(general['operationId'])
 check(general_result['status']=='done' and general_result['result']['scope']=='general' and len(bridge.calls)==before_work,'General discussion needs no project and cannot silently submit work')
 http('/v1/operations','POST',general,token);wait(general['operationId'])
 check(len(discussions)==1 and discussions[0]['projectId'] is None,'Retrying general discussion preserves its single durable operation')

 # Revoke while identity resolution is blocked: the final delivery boundary
 # must check authorization again, rather than trusting the queued request.
 resolving=threading.Event();resume=threading.Event();original_resolve=bridge.resolve
 def delayed_resolve(identity):
  resolving.set();resume.wait(3);return original_resolve(identity)
 bridge.resolve=delayed_resolve
 pending={**send,'operationId':'revoke-during-resolve'}
 before_calls=len(bridge.calls);portal.submit(device,pending)
 assert resolving.wait(2),'Resolution did not start'

 http('/v1/device','DELETE',token=token)
 resume.set()
 for _ in range(100):
  revoked_job=portal.job(device,pending['operationId'])
  if revoked_job['status'] not in ('queued','running'):break
  time.sleep(.01)
 check(revoked_job['status']=='failed' and len(bridge.calls)==before_calls,'Revocation during slow resolution prevents work delivery')
 check(rejects(lambda:http('/v1/projects',token=token)),'Revocation immediately blocks project access')
 check(not portal.store.authenticate(token),'Revoked credentials cannot authenticate again')
 portal.close()
 store=PortalStore(root/'private',recover=True)
 row=store.db.execute("SELECT status FROM jobs WHERE id='interrupted-job'").fetchone()
 check(row[0]=='uncertain','Interrupted commands become uncertain on restart and never replay')
 check(len(store.comments(alpha['id']))==1,'Project comments survive a Mac service restart')
 store.close()
with tempfile.TemporaryDirectory(prefix='motchi-loading-test-') as directory:
 release=threading.Event()
 class SlowBridge:
  def snapshot(self):release.wait(3);return {'items':[]}
 portal=AndroidPortal(SlowBridge(),Path(directory),host='127.0.0.1',port=0).start()
 before=time.monotonic();value=portal.read_snapshot()
 check(value.get('loading') and time.monotonic()-before<.2,'Slow Mac discovery returns a loading state immediately')
 portal.refresh_started=time.monotonic()-21
 check('file-access' in portal.read_snapshot().get('catalogIssue',''),'Stalled initial discovery explains the Mac file-access check')
 release.set();portal.close()
print(f'{len(checks)} Android portal checks passed')
for label in checks:print('PASS',label)
