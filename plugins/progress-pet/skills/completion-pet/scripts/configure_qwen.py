"""Install/select the free local Qwen3-ASR engine; models stay outside Git."""
import argparse
import json
from pathlib import Path
import platform
import subprocess
import venv
from configure_doubao import save_private
from qwen_speech import config

MODEL='mlx-community/Qwen3-ASR-0.6B-8bit'
RUNTIME='mlx-audio[stt]==0.6.3'
REVISION='89e96d92ba34aca20b3e29fb10cc284097d1219f'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path.home()/'Library/Application Support/Mochi/android')
    p.add_argument('--install',action='store_true',help='Download the runtime from PyPI and public model from Hugging Face.')
    p.add_argument('--select',action='store_true',help='Select an already configured Qwen engine.')
    a=p.parse_args()
    if a.install:
        if platform.system()!='Darwin' or platform.machine()!='arm64':p.error('This MLX setup requires an Apple Silicon Mac.')
        env=a.root/'qwen-python';model=a.root/'models/qwen3-asr-0.6b-8bit'
        a.root.mkdir(parents=True,exist_ok=True,mode=0o700)
        venv.create(env,with_pip=True)
        python=env/'bin/python'
        subprocess.run([str(python),'-m','pip','install','--timeout','90',RUNTIME,'truststore==0.10.5'],check=True)
        code=('import truststore;truststore.inject_into_ssl();from huggingface_hub import snapshot_download;'
              'import sys;snapshot_download(sys.argv[1],local_dir=sys.argv[2],'
              'allow_patterns=["*.json","*.safetensors","*.txt","*.model"],revision=sys.argv[3],max_workers=3)')
        subprocess.run([str(python),'-c',code,MODEL,str(model),REVISION],check=True)
        save_private(a.root/'qwen.json',{'python':str(python),'model':str(model),'source':MODEL,'runtime':RUNTIME,'revision':REVISION})
    if a.install or a.select:
        config(a.root)
        save_private(a.root/'speech-provider.json',{'provider':'qwen'})
        print('Qwen3-ASR selected. Audio is recognized on your Mac; no speech API key or per-minute API fee.')
    else:
        try:config(a.root);print('Local Qwen runtime/model configured. This does not establish human speech accuracy.')
        except ValueError as error:print(str(error))

if __name__=='__main__':main()
