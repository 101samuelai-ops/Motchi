"""Official Doubao streaming ASR, two-pass final recognition, no ambient upload.

Protocol: https://www.volcengine.com/docs/6561/1354869
Credentials stay in private Mac state. This module never logs provider frames,
keys, audio or transcripts, and never substitutes local recognition on failure.
"""
import gzip
import io
import json
from pathlib import Path
import struct
import sys
import threading
import time
import uuid
import wave

ENDPOINT = 'wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_async'
RESOURCES = ('volc.seedasr.sauc.duration', 'volc.seedasr.sauc.concurrent',
             'volc.bigasr.sauc.duration', 'volc.bigasr.sauc.concurrent')
LIMIT = 1_000_000


def read_config(root):
    path = Path(root)/'doubao.json'
    try:
        if path.is_symlink() or path.stat().st_mode & 0o077:
            raise ValueError('Doubao credentials must be a private file readable only by your Mac user.')
        config = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        raise ValueError('Doubao needs API setup on your Mac. A Doubao app login is not an API key.') from None
    if config.get('cloud_authorized') is not True:
        raise ValueError('Complete Doubao setup on your Mac before sending speech to its API.')
    resource = config.get('resource_id', RESOURCES[0])
    if resource not in RESOURCES:
        raise ValueError('Choose a supported Doubao streaming ASR resource.')
    fields = ('api_key',) if config.get('api_key') else ('app_id', 'access_token')
    for field in fields:
        value = config.get(field)
        if not isinstance(value, str) or not value.strip() or len(value)>4096 or any(ord(c)<33 or ord(c)>126 for c in value):
            raise ValueError('Complete the Doubao API credentials on your Mac.')
    return {**config, 'resource_id': resource}


def dependency(root):
    private = Path(root)/'speech-python'
    if private.is_dir() and str(private) not in sys.path: sys.path.insert(0,str(private))
    try:
        from websockets.sync.client import connect
        return connect
    except ImportError:
        raise ValueError('Install the Doubao speech dependency on your Mac before connecting.') from None


def headers(config):
    value = {'X-Api-Resource-Id':config['resource_id'], 'X-Api-Connect-Id':str(uuid.uuid4())}
    if config.get('api_key'): value['X-Api-Key'] = config['api_key']
    else: value.update({'X-Api-App-Key':config['app_id'],'X-Api-Access-Key':config['access_token']})
    return value


def frame(kind, payload, final=False):
    compressed = gzip.compress(payload,mtime=0)
    return bytes((0x11,(kind<<4)|(2 if final else 0),0x11 if kind==1 else 0x01,0)) + struct.pack('>I',len(compressed)) + compressed


def parse(data):
    if not isinstance(data,bytes) or not 8 <= len(data) <= LIMIT: raise ValueError('Invalid Doubao speech response.')
    offset=(data[0]&15)*4; kind=data[1]>>4; flags=data[1]&15
    serialization,compression=data[2]>>4,data[2]&15
    if data[0]>>4!=1 or offset<4 or offset+4>len(data): raise ValueError('Invalid Doubao speech header.')
    if kind==15:
        code=struct.unpack_from('>I',data,offset)[0]
        raise ValueError(f'Doubao rejected speech (code {code}). Check the enabled service and API quota on your Mac.')
    if kind!=9 or serialization!=1 or compression not in (0,1): raise ValueError('Unsupported Doubao speech response.')
    sequence=None
    if flags & 1:
        if offset+8>len(data): raise ValueError('Incomplete Doubao speech response.')
        sequence=struct.unpack_from('>i',data,offset)[0];offset+=4
    size=struct.unpack_from('>I',data,offset)[0];offset+=4
    if size>LIMIT or offset+size!=len(data): raise ValueError('Invalid Doubao speech payload size.')
    payload=data[offset:]
    if compression:
        try:
            with gzip.GzipFile(fileobj=io.BytesIO(payload)) as stream:payload=stream.read(LIMIT+1)
        except (OSError,EOFError): raise ValueError('Invalid compressed Doubao speech response.') from None
    if len(payload)>LIMIT: raise ValueError('Doubao speech response is too large.')
    try: value=json.loads(payload)
    except (ValueError,UnicodeError): raise ValueError('Invalid Doubao speech result.') from None
    if not isinstance(value,dict): raise ValueError('Invalid Doubao speech result.')
    if value.get('code') not in (None,0,20000000):
        raise ValueError('Doubao could not recognize this recording. Try again or check your API service.')
    result=value.get('result') or {}
    if isinstance(result,list): result=result[-1] if result else {}
    if not isinstance(result,dict): raise ValueError('Invalid Doubao transcript.')
    text=result.get('text') or ''
    if not isinstance(text,str) or len(text)>12000: raise ValueError('Invalid Doubao transcript.')
    return text.strip(),bool(flags&2 or (sequence is not None and sequence<0))


def pcm_from_wav(audio):
    try:
        with wave.open(io.BytesIO(audio),'rb') as source:
            if source.getnchannels()!=1 or source.getsampwidth()!=2 or source.getframerate()!=16000 or not 0<source.getnframes()<=960000:
                raise ValueError('Doubao requires mono 16 kHz PCM audio, up to 60 seconds.')
            pcm=source.readframes(source.getnframes())
    except (wave.Error,EOFError): raise ValueError('Record valid mono PCM speech before using Doubao.') from None
    return pcm


def recognize(root, audio, permitted=lambda:None, on_text=None, connector=None, pace=True):
    config=read_config(root)
    pcm=pcm_from_wav(audio)
    connect=connector or dependency(root)
    permitted()
    options={'user':{'uid':'motchi-calendar'},'audio':{'format':'pcm','codec':'raw','rate':16000,'bits':16,'channel':1},
             'request':{'model_name':'bigmodel','enable_nonstream':True,'enable_itn':True,'enable_punc':True,
                        'enable_ddc':False,'show_utterances':True,'result_type':'full','end_window_size':900,
                        'corpus':{'context':json.dumps({'hotwords':[{'word':'Motchi'},{'word':'Mochi'},{'word':'Codex'}]})}}}
    # The optimized bilingual/two-pass endpoint does not support a forced
    # language field. Do not silently send the local Whisper language setting.
    finished=threading.Event(); send_error=[]
    connection=None
    try:
        connection=connect(ENDPOINT,additional_headers=headers(config),open_timeout=10,close_timeout=1,
                           max_size=LIMIT,proxy=None)
        permitted(); connection.send(frame(1,json.dumps(options).encode()))
        def send():
            try:
                start=time.monotonic()
                for index,offset in enumerate(range(0,len(pcm),6400)):
                    if finished.is_set(): return
                    permitted()
                    if pace:
                        delay=start+index*.2-time.monotonic()
                        if delay>0 and finished.wait(delay): return
                    connection.send(frame(2,pcm[offset:offset+6400],final=offset+6400>=len(pcm)))
            except Exception: send_error.append(True)
        sender=threading.Thread(target=send,name='motchi-doubao-audio',daemon=True);sender.start()
        text='';deadline=time.monotonic()+len(pcm)/32000+25
        try:
            while time.monotonic()<deadline:
                permitted()
                if send_error: raise ValueError('Doubao connection was interrupted. Your question was not submitted.')
                try:data=connection.recv(timeout=.25)
                except TimeoutError:continue
                candidate,final=parse(data)
                if candidate:
                    text=candidate
                    if on_text:on_text(text)
                if final:
                    if not text: raise ValueError('Doubao heard no clear speech. Speak near your Mac and try again.')
                    permitted();return text[:3000]
            raise ValueError('Doubao speech recognition timed out. Try again when the connection is stable.')
        finally:
            finished.set();connection.close();sender.join(timeout=2)
    except ValueError: raise
    except Exception as error:
        code=getattr(getattr(error,'response',None),'status_code',None)
        if code in (401,403):raise ValueError('Doubao API access was rejected. Check your speech key and enabled resource on the Mac.') from None
        if code==429:raise ValueError('Doubao speech quota or concurrency limit reached. Check your Volcengine service.') from None
        raise ValueError('Cannot connect to Doubao speech. Check internet access and your Mac API setup.') from None
    finally:
        finished.set()
        if connection:
            try:connection.close()
            except Exception:pass


def selected(root):
    try:value=json.loads((Path(root)/'speech-provider.json').read_text()).get('provider','local')
    except (OSError,ValueError):return 'local'
    return value if value in ('local','doubao','qwen') else 'local'


def info(root):
    provider=selected(root);issue=None;ready=True
    if provider=='qwen':
        try:
            from qwen_speech import config
            config(root)
        except ValueError as error:ready=False;issue=str(error)
    if provider=='doubao':
        try:read_config(root);dependency(root)
        except ValueError as error:ready=False;issue=str(error)
    return {'provider':provider,'providerLabel':{'doubao':'Doubao Speech · cloud','qwen':'Qwen3-ASR · free local Mac','local':'Whisper · local Mac'}[provider],
            'providerReady':ready,'providerIssue':issue,'cloudSpeech':provider=='doubao','providerAutoLanguage':provider in ('qwen','doubao')}
