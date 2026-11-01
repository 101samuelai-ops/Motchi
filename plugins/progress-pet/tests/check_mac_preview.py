"""Real loopback preview HTTP, read-only boundaries and microphone ownership."""
import json
from pathlib import Path
import sys
import threading
import urllib.error
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'android'))
from preview_live import LivePreview, NoRedirect

checks=0
def check(value,label):
    global checks
    assert value,label
    checks+=1

class Connection:
    token='PRIVATE_PAIR_TOKEN_NOT_FOR_THE_PAGE'
    def __init__(self):self.calls=[];self.enabled=False;self.turn='turn-initial';self.events=[];self.closed=False
    def request(self,path,body=None):
        self.calls.append((path,body))
        if path=='/v1/projects':return {'projects':[{'id':'alpha','name':'Alpha'}]}
        if path=='/v1/mac-voice':
            self.enabled=body.get('enabled',False)
            if body.get('activate'):self.turn='replacement-turn'
            events,self.events=self.events,[]
            return {'enabled':self.enabled,'running':self.enabled,'turnId':self.turn,'events':events}
        if path=='/v1/operations':return {'id':body['operationId'],'status':'queued'}
        return {'status':'done','result':{'text':'One task remains.'}}
    def close(self):self.closed=True

connection=Connection();preview=LivePreview(connection)
thread=threading.Thread(target=preview.server.serve_forever,daemon=True);thread.start()
def http(path='/',body=None,headers=None):
    supplied={'Origin':preview.url.rstrip('/'),'X-Motchi-Preview':preview.csrf,'Content-Type':'application/json'}
    if headers:supplied.update(headers)
    request=urllib.request.Request(preview.url.rstrip('/')+path,data=json.dumps(body).encode() if body is not None else None,headers=supplied)
    with urllib.request.urlopen(request,timeout=3) as response:return response.read(),response.headers
def call(action,**extra):return json.loads(http('/api',{'action':action,**extra})[0])
def status(body,headers):
    try:http('/api',body,headers);return 200
    except urllib.error.HTTPError as error:return error.code
try:
    page,headers=http()
    check(b'live Mac test' in page and b'motchi-preview' in page,'The page labels live data and carries a same-origin request nonce')
    check(connection.token.encode() not in page and connection.token.encode() not in http('/native.js')[0],
          'Pairing credentials are absent from browser assets')
    check(b"connect-src 'self'" in page and b"media-src 'self' blob:" in page,
          'The preview permits its own transport and local reply playback')
    check(headers['Cross-Origin-Resource-Policy']=='same-origin' and "frame-ancestors 'none'"==headers['Content-Security-Policy'],
          'Other origins cannot embed the preview or import its assets')
    check(status({'action':'snapshot'},{'Origin':'https://other.example'})==403,'An unrelated website cannot read projects')
    check(status({'action':'snapshot'},{'X-Motchi-Preview':'wrong'})==403,'A forged request cannot use the preview connection')
    check(status({'action':'snapshot'},{'Host':'other.example'})==403,'Host rebinding cannot reach live project data')
    check(call('snapshot')['data']['projects'][0]['id']=='alpha','Project cards come from the authenticated Mac service')
    before=len(connection.calls);state=call('voiceInfo')['data']
    check(not state['enabled'] and len(connection.calls)==before,'Opening the preview does not start microphone capture')
    call('voiceContext',projectId='alpha',selection='alpha-chat')
    state=call('wakeListening',enabled=True)['data'];payload=connection.calls[-1][1]
    check(state['running'] and payload['projectId']=='alpha' and payload['conversationVersion']==2,
          'Explicit listening uses the exact context and the updated Mac conversation protocol')
    connection.events=[{'wake':True,'partial':True,'heard':'What remains?','turnId':connection.turn}]
    call('voiceInfo',speaking=True)
    check(connection.calls[-1][1]['speaking'] is True,'Playback state reaches the Mac echo-muting control')
    check(call('voiceEvents')['data']['events'][0]['heard']=='What remains?' and not call('voiceEvents')['data']['events'],
          'Live captions drain once instead of creating duplicate messages')
    connection.events=[{'wake':True,'text':'old answer'}];call('voiceInfo');call('listenNow')
    check(not call('voiceEvents')['data']['events'],'Replacing a question discards previously queued preview events')
    before=len(connection.calls)
    for action in ('send','start','comment','toggle','undo','approve'):
        check(status({'action':'submit','request':{'action':action,'operationId':'test-operation'}},{})==400,
              'Preview rejects '+action+' before any Mac work request')
    check(len(connection.calls)==before,'Rejected writes never reach the real companion')
    result=call('submit',request={'action':'discuss','text':'What remains?','operationId':'test-operation','_permitted':'injected'})
    check(result['data']['status']=='queued' and '_permitted' not in connection.calls[-1][1],
          'Only read-only question fields reach the answer provider')
    check(status({'action':'job','id':'../../private'},{})==400,'Operation IDs cannot become arbitrary API paths')
    preview.state.update(issue='Question reached 60 seconds.', stage='listening', rms=100)
    paused=call('wakeListening',enabled=False)['data']
    check(not connection.enabled,'Pause ends the preview-owned microphone session')
    check(not paused['issue'] and paused['stage']=='idle' and paused['rms']==0,
          'Pause clears stale listening errors and input levels')
    try:NoRedirect().redirect_request(None,None,None,None,None,None);redirected=True
    except ValueError:redirected=False
    check(not redirected,'Pair credentials cannot follow a redirect to another endpoint')
finally:
    preview.server.shutdown();preview.close();thread.join(timeout=2)
check(connection.closed,'Closing the preview revokes its temporary connection')
print(f'{checks} live Mac preview HTTP, voice and read-only checks passed')
