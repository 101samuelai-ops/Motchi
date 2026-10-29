"""Official wire protocol, cloud boundary, error privacy and setup checks."""
import gzip
import io
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
from unittest.mock import patch
import wave
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/completion-pet/scripts'))
import doubao_speech as D
from configure_doubao import save_private
from voice_companion import VoiceCompanion

checks=0
def check(value,label):
    global checks
    assert value,label
    checks+=1
def rejects(fn,contains=None):
    try:fn();return False
    except ValueError as error:return contains is None or contains in str(error)
def response(text='',final=False,gz=True):
    data=json.dumps({'result':{'text':text}}).encode()
    if gz:data=gzip.compress(data)
    return bytes((0x11,0x93 if final else 0x91,0x11 if gz else 0x10,0))+struct.pack('>iI',-1 if final else 1,len(data))+data
def audio(rate=16000):
    out=io.BytesIO()
    with wave.open(out,'wb') as f:
        f.setnchannels(1);f.setsampwidth(2);f.setframerate(rate);f.writeframes(struct.pack('<h',600)*6400)
    return out.getvalue()

check(D.parse(response('查看项目进度。',True))==('查看项目进度。',True),'Gzip final result and negative sequence decode correctly')
check(D.parse(response('How is Motchi?',False,False))==('How is Motchi?',False),'Uncompressed partial results decode correctly')
check(rejects(lambda:D.parse(b'invalid')),'Malformed provider frames are rejected')
check(rejects(lambda:D.parse(response('text')+b'extra')),'Declared lengths must match the entire frame')
bomb=gzip.compress(b'x'*(D.LIMIT+1))
check(rejects(lambda:D.parse(bytes((0x11,0x90,0x11,0))+struct.pack('>I',len(bomb))+bomb)),'Compressed responses have a strict expanded-size cap')
err=bytes((0x11,0xf0,0x10,0))+struct.pack('>II',45000001,0)
check(rejects(lambda:D.parse(err),'45000001'),'Provider errors expose an actionable code without echoing raw messages')
check(rejects(lambda:D.pcm_from_wav(audio(8000))),'Incorrect audio format cannot reach the cloud')
message=D.frame(2,b'pcm',True)
check(message[:4]==b'\x11\x22\x01\x00' and gzip.decompress(message[8:])==b'pcm','The final client audio packet uses the documented negative-packet flag')

class Socket:
    def __init__(self,replies):self.replies=iter(replies);self.sent=[];self.closed=False
    def send(self,data):self.sent.append(data)
    def recv(self,timeout=None):return next(self.replies)
    def close(self):self.closed=True
with tempfile.TemporaryDirectory() as directory:
    root=Path(directory)
    check(rejects(lambda:D.read_config(root),'API setup'),'A Doubao app login cannot be treated as API credentials')
    save_private(root/'doubao.json',{'api_key':'fixture-secret','resource_id':D.RESOURCES[0],'cloud_authorized':True})
    check((root/'doubao.json').stat().st_mode&0o777==0o600,'Saved API credentials are readable only by the Mac user')
    config=D.read_config(root)
    check(D.headers(config)['X-Api-Key']=='fixture-secret' and 'X-Api-App-Key' not in D.headers(config),'New-console API key authentication uses X-Api-Key')
    check(D.headers({'app_id':'123','access_token':'fixture','resource_id':D.RESOURCES[2]})['X-Api-Access-Key']=='fixture','Legacy speech credentials retain their documented headers')
    save_private(root/'speech-provider.json',{'provider':'doubao'})
    with patch.object(D,'dependency',return_value=lambda:None):public=D.info(root)
    check(public['provider']=='doubao' and public['providerReady'] and 'fixture-secret' not in json.dumps(public),'Public provider status contains no credentials')
    socket=Socket([response('How is'),response('How is Motchi doing?',True)])
    connections=[];updates=[]
    def connect(url,**options):connections.append((url,options));return socket
    result=D.recognize(root,audio(),on_text=updates.append,connector=connect,pace=False)
    check(result=='How is Motchi doing?' and updates[-1]==result and socket.closed,'Interim text is replaced by the final corrected transcript and the connection closes')
    options=json.loads(gzip.decompress(socket.sent[0][8:]))
    check(options['request']['enable_nonstream'] and options['request']['show_utterances'],'Optimized two-pass recognition and speech boundaries are enabled')
    check('language' not in options['audio'] and options['request']['enable_ddc'] is False,'Bilingual recognition keeps the utterance wording and avoids unsupported forced-language parameters')
    check(connections[0][0]==D.ENDPOINT and connections[0][1]['proxy'] is None,'Audio goes only to the fixed official WSS endpoint with normal TLS verification')
    def forbidden():raise ValueError('cancelled-generation')
    count=len(connections)
    check(rejects(lambda:D.recognize(root,audio(),permitted=forbidden,connector=connect),'cancelled') and len(connections)==count,'Cancellation prevents opening a cloud connection')
    os.chmod(root/'doubao.json',0o644)
    check(rejects(lambda:D.read_config(root),'private file'),'World-readable credential files are rejected')

# Validate the authorization boundary in the same router used by live audio.
transcript=['ambient speech'];cloud=[];asks=[];request={'generation':'cloud-boundary-1234'}
project={'id':'alpha','name':'Alpha','selection':'chat','chats':[{'id':'chat'}]}
def transcribe(data,req):
    if req['_addressed']:cloud.append('active')
    return transcript[0]
def refine(data,req,text):cloud.append('refine');return text
voice=VoiceCompanion(lambda _:transcript[0],lambda:[project],lambda *args:asks.append(args) or {'text':'answer'},lambda _:True,
                     transcribe_request=transcribe,refine_addressed=refine)
check(voice.run('calendar',request,b'audio')=={'wake':False} and not cloud,'Unaddressed background speech never reaches Doubao')
transcript[0]='Hey Motchi, how is Alpha?'
result=voice.run('calendar',request,b'audio')
check(cloud==['refine'] and len(asks)==1,'A locally recognized wake name authorizes cloud refinement and one read-only answer')
transcript[0]='What remains?'
voice.run('calendar',{**request,'session':result['session'],'projectId':'alpha','selection':'chat'},b'audio')
check(cloud[-1]=='active' and len(asks)==2,'Only a validated follow-up lease can continue cloud transcription')
before=len(cloud)
check(voice.run('other',{**request,'session':result['session']},b'audio')=={'wake':False} and len(cloud)==before,'Another device cannot reuse the follow-up lease to upload ambient speech')
voice.run('explicit',{**request,'activated':True,'preview':True},b'audio')
check(cloud[-1]=='active' and len(asks)==2,'Listen now authorizes cloud live text without asking the answer provider prematurely')
print(f'{checks} Doubao protocol, two-pass recognition, credentials and cloud-boundary checks passed')
