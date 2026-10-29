"""Private local MLX worker. Input/output is a bounded JSON-lines pipe."""
import contextlib
import json
from pathlib import Path
import sys


def main():
    # Diagnostics cannot mix with the private result protocol.
    with contextlib.redirect_stdout(sys.stderr):
        from mlx_audio.stt import load
        model=load(sys.argv[1])
    for line in sys.stdin:
        if len(line)>8192:break
        try:
            request=json.loads(line)
            audio=Path(request['audio'])
            language={'en':'English','zh':'Chinese','auto':None}.get(request.get('language','auto'))
            with contextlib.redirect_stdout(sys.stderr):
                result=model.generate(str(audio),language=language,max_tokens=512)
            text=result.text.strip()
            if not isinstance(text,str) or len(text)>12000:raise ValueError('Invalid transcript')
            print(json.dumps({'text':text[:3000]},ensure_ascii=False),flush=True)
        except Exception:
            print(json.dumps({'error':'Local Qwen recognition failed. Try a shorter question near your Mac.'}),flush=True)

if __name__=='__main__':main()
