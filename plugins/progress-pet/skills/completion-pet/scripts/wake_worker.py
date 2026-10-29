"""CPU-only bilingual keyword spotting from a private 16 kHz PCM pipe."""
import json
from pathlib import Path
import sys


def main():
    import numpy as np
    import sherpa_onnx
    root=Path(sys.argv[1]);stem='-epoch-13-avg-2-chunk-16-left-64'
    kws=sherpa_onnx.KeywordSpotter(tokens=str(root/'tokens.txt'),
        encoder=str(root/('encoder'+stem+'.int8.onnx')),
        decoder=str(root/('decoder'+stem+'.onnx')),
        joiner=str(root/('joiner'+stem+'.int8.onnx')),
        keywords_file=str(root/'motchi-keywords.txt'),num_threads=2,
        sample_rate=16000,feature_dim=80,provider='cpu',
        keywords_score=1.5,keywords_threshold=.25,num_trailing_blanks=1)
    stream=kws.create_stream()
    print(json.dumps({'ready':True}),flush=True)
    while True:
        frame=sys.stdin.buffer.read(640)
        if len(frame)!=640:return
        samples=np.frombuffer(frame,dtype='<i2').astype(np.float32)/32768
        stream.accept_waveform(16000,samples)
        while kws.is_ready(stream):
            kws.decode_stream(stream);keyword=kws.get_result(stream)
            if keyword:
                print(json.dumps({'keyword':keyword},ensure_ascii=False),flush=True)
                kws.reset_stream(stream)

if __name__=='__main__':main()
