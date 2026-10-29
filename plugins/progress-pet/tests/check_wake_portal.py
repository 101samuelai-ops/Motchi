"""Actual HTTPS wake endpoint, ephemeral output, auth and cancellation checks."""
import base64, io, json, math, ssl, struct, sys, tempfile, time, urllib.error, urllib.request, wave
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/completion-pet/scripts'))
from android_host import AndroidPortal

checks = 0
def check(value, label):
    global checks
    assert value, label
    checks += 1
def rejects(fn):
    try: fn(); return False
    except (ValueError, urllib.error.HTTPError): return True
with tempfile.TemporaryDirectory(prefix='motchi-wake-test-') as directory:
    root=Path(directory); project=root/'Alpha'; project.mkdir(); calls=[]; transcript=['ordinary ambient conversation']
    class Bridge:
        def snapshot(self): return {'items':[{'id':'alpha-chat','cwd':str(project),'title':'Alpha','status':'idle','updatedAt':1}]}
        def resolve(self, selection): return self.snapshot()['items'][0]
        def ask_result(self, request): calls.append(request); return {'text':'One recorded task remains.'}
    portal=AndroidPortal(Bridge(), root/'private', host='127.0.0.1', port=0,
                         transcriber=lambda _:transcript[0], speaker=lambda _:b'RIFFspoken-test').start()
    portal.snapshot(force=True)
    context=ssl.create_default_context(cafile=str(root/'private/server.pem'));context.check_hostname=False
    def http(path, body=None, token=None):
        headers={'Content-Type':'application/json'}
        if token:headers['Authorization']='Bearer '+token
        data=json.dumps(body).encode() if body is not None else None
        with urllib.request.urlopen(urllib.request.Request('https://'+portal.authority+path,data=data,headers=headers),context=context,timeout=5) as response:return json.load(response)
    def pair():
        ticket=portal.pairing()['ticket'][8:];d=json.loads(base64.urlsafe_b64decode(ticket+'='*(-len(ticket)%4)))
        return portal.store.pair(d['code'],'Fixture device')
    paired=pair(); token=paired['token']; device=paired['deviceId']
    buf=io.BytesIO()
    with wave.open(buf,'wb') as f:
        f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000);f.writeframes(b''.join(struct.pack('<h',int(1800*math.sin(n/10))) for n in range(1600)))
    payload={'audio':base64.b64encode(buf.getvalue()).decode(),'generation':'test-generation','operationId':'voice-operation-1234'}
    check(rejects(lambda:http('/v1/voice',payload)), 'Wake audio cannot be submitted without device authentication')
    check(rejects(lambda:http('/v1/mac-voice',{'enabled':True})), 'Mac microphone activation requires a paired device')
    check(not http('/v1/mac-voice',token=token)['enabled'], 'A paired device initially sees a paused Mac microphone')
    check(rejects(lambda:http('/v1/speech-provider',{'provider':'doubao'})), 'Unauthenticated callers cannot change the speech provider')
    provider=http('/v1/speech-provider',{'provider':'doubao'},token)
    check(provider['provider']=='doubao' and not provider['providerReady'] and 'api_key' not in provider,
          'Selecting Doubao without API credentials reports setup needed without leaking credential fields')
    http('/v1/speech-provider',{'provider':'local'},token)
    check(rejects(lambda:http('/v1/voice',{**payload,'audio':'bad base64'},token)), 'Malformed audio encoding is rejected')
    check(rejects(lambda:http('/v1/voice',{**payload,'audio':base64.b64encode(b'fake'*20).decode()},token)), 'Non-WAV data cannot bypass microphone validation')
    def finish(p):
        http('/v1/voice',p,token)
        for _ in range(100):
            job=http('/v1/operations/'+p['operationId'],token=token)
            if job['status'] not in ('queued','running'):return job
            time.sleep(.01)
        raise AssertionError('voice job stalled')
    result=finish(payload)
    check(result['status']=='done' and result['result']=={'wake':False} and not calls, 'Ambient speech leaves no transcript in the durable receipt or answer provider')
    transcript[0]='Hey Motchi, how is Alpha doing?'
    preview={**payload,'operationId':'voice-operation-preview','preview':True}
    partial=finish(preview)
    check(partial['result']['partial'] and not calls, 'Live transcript endpoint never invokes the answer provider')
    check(http('/v1/voice-audio/'+preview['operationId'],token=token)['wav'] is None, 'Partial transcripts never trigger spoken answer playback')
    named={**payload,'operationId':'voice-operation-5678'}
    result=finish(named)
    check(result['result']['projectName']=='Alpha' and calls[-1]['selection']=='alpha-chat' and not calls[-1]['autoFollow'], 'Wake questions take the exact read-only project route')
    finish(named)
    check(len(calls)==1, 'Retrying a voice operation receipt does not ask twice')
    audio=http('/v1/voice-audio/'+named['operationId'],token=token)
    check(base64.b64decode(audio['wav'])==b'RIFFspoken-test', 'The originating paired device can play its ephemeral spoken reply')
    other=pair()
    check(http('/v1/voice-audio/'+named['operationId'],token=other['token'])['wav'] is None, 'Another paired device cannot read a spoken project answer')
    with portal.lock: portal.voice_audio[(device,named['operationId'])]=(time.monotonic()-121,b'expired')
    check(http('/v1/voice-audio/'+named['operationId'],token=token)['wav'] is None, 'Spoken output expires rather than persisting as an audio archive')
    http('/v1/voice',{'cancel':True,'generation':'test-generation'},token)
    stopped=finish({**payload,'operationId':'voice-operation-stop'})
    check(stopped['status']=='failed' and len(calls)==1, 'Pausing prevents late questions from the old microphone generation')
    portal.store.revoke(device)
    check(rejects(lambda:http('/v1/voice',payload,token)), 'Revocation also blocks wake audio and follow-ups')
    portal.close()
print(f'{checks} paired wake HTTPS, audio privacy and cancellation checks passed')
