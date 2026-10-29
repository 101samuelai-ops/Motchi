"""Configure Doubao in a local Mac terminal; secret input is never echoed."""
import argparse
import getpass
import json
import os
from pathlib import Path
import tempfile
from doubao_speech import RESOURCES, info


def save_private(path, value):
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    fd,name=tempfile.mkstemp(dir=path.parent,prefix='.speech-')
    try:
        with os.fdopen(fd,'w') as stream:json.dump(value,stream);stream.write('\n')
        os.replace(name,path)
    finally:
        if os.path.exists(name):os.unlink(name)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path.home()/'Library/Application Support/Mochi/android')
    parser.add_argument('--status',action='store_true')
    parser.add_argument('--local',action='store_true')
    args=parser.parse_args()
    if args.status:print(json.dumps(info(args.root),ensure_ascii=False));return
    if args.local:
        save_private(args.root/'speech-provider.json',{'provider':'local'});print('Local speech selected.');return
    if not os.isatty(0):parser.error('Run this setup in your Mac terminal so your key stays private.')
    print('Enable Doubao streaming ASR in your Volcengine account first.')
    print('Speech after Listen now or a recognized wake name will go to Doubao for transcription.')
    print('Background wake detection stays on your Mac. API usage is billed by your Volcengine service.')
    if input('Configure and enable Doubao? [yes/no] ').strip().lower()!='yes':return
    legacy=input('Use legacy App ID + Access Token? [y/N] ').strip().lower()=='y'
    config={'cloud_authorized':True}
    if legacy:
        config['app_id']=input('Speech App ID: ').strip()
        config['access_token']=getpass.getpass('Speech Access Token (hidden): ').strip()
    else:config['api_key']=getpass.getpass('Speech API Key (hidden): ').strip()
    print('1: Doubao ASR 2.0 hours; 2: ASR 2.0 concurrency; 3: ASR 1.0 hours; 4: ASR 1.0 concurrency')
    choice=input('Enabled resource [1]: ').strip() or '1'
    if choice not in ('1','2','3','4'):parser.error('Choose the resource enabled in your account.')
    config['resource_id']=RESOURCES[int(choice)-1]
    values=[config.get('api_key')] if not legacy else [config['app_id'],config['access_token']]
    if any(not v or len(v)>4096 or any(ord(c)<33 or ord(c)>126 for c in v) for v in values):
        parser.error('Credentials are empty or malformed; nothing was saved.')
    save_private(args.root/'doubao.json',config)
    save_private(args.root/'speech-provider.json',{'provider':'doubao'})
    print('Doubao selected. Motchi will reload it automatically. This has not tested or charged the API.')


if __name__=='__main__':main()
