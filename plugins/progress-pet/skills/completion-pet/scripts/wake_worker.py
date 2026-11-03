"""CPU-only bilingual keyword spotting from a private 16 kHz PCM pipe."""
import json
from pathlib import Path
import sys

class SpeechModel:
    """Silero's recurrent 512-sample CPU inference; no torch or audio files."""
    def __init__(self,path):
        import numpy as np
        import onnxruntime as ort
        self.np=np
        options=ort.SessionOptions();options.intra_op_num_threads=1;options.inter_op_num_threads=1
        self.session=ort.InferenceSession(str(path),sess_options=options,providers=['CPUExecutionProvider'])
        self.state=np.zeros((2,1,128),dtype=np.float32)
        self.context=np.zeros((1,64),dtype=np.float32)
        self.pending=np.empty(0,dtype=np.float32)

    def feed(self,samples):
        np=self.np;self.pending=np.concatenate((self.pending,samples));probability=None
        while len(self.pending)>=512:
            chunk=self.pending[:512].reshape(1,512);self.pending=self.pending[512:]
            combined=np.concatenate((self.context,chunk),axis=1)
            output,self.state=self.session.run(None,{'input':combined,'state':self.state,'sr':np.array(16000,dtype=np.int64)})
            self.context=combined[:,-64:]
            probability=float(output[0,0])
        return probability


def main():
    import numpy as np
    import sherpa_onnx
    root=Path(sys.argv[1]);stem='-epoch-13-avg-2-chunk-16-left-64'
    kws=sherpa_onnx.KeywordSpotter(tokens=str(root/'tokens.txt'),
        encoder=str(root/('encoder'+stem+'.int8.onnx')),
        decoder=str(root/('decoder'+stem+'.onnx')),
        joiner=str(root/('joiner'+stem+'.int8.onnx')),
        keywords_file=str(root/'motchi-keywords.txt'),num_threads=2,max_active_paths=16,
        sample_rate=16000,feature_dim=80,provider='cpu',
        # Keep competing English/Chinese pronunciation paths alive. The old
        # four-path beam dropped valid names when the alias list expanded.
        keywords_score=1.0,keywords_threshold=.1,num_trailing_blanks=1)
    stream=kws.create_stream()
    speech=SpeechModel(sys.argv[2]) if len(sys.argv)>2 else None
    print(json.dumps({'ready':True,'speechReady':bool(speech)}),flush=True)
    while True:
        frame=sys.stdin.buffer.read(640)
        if len(frame)!=640:return
        samples=np.frombuffer(frame,dtype='<i2').astype(np.float32)/32768
        if speech:
            probability=speech.feed(samples)
            if probability is not None:print(json.dumps({'speechProbability':probability}),flush=True)
        stream.accept_waveform(16000,samples)
        while kws.is_ready(stream):
            kws.decode_stream(stream);keyword=kws.get_result(stream)
            if keyword:
                print(json.dumps({'keyword':keyword},ensure_ascii=False),flush=True)
                kws.reset_stream(stream)

if __name__=='__main__':main()
