"""Smart Turn v3.2 ONNX inference; no model downloads or audio files."""
import base64
import contextlib
import json
import os
import sys


def main():
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    with contextlib.redirect_stdout(sys.stderr):
        import numpy as np
        import onnxruntime as ort
        from transformers import WhisperFeatureExtractor
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        options.inter_op_num_threads = 1
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        session = ort.InferenceSession(sys.argv[1], sess_options=options, providers=['CPUExecutionProvider'])
        extractor = WhisperFeatureExtractor(chunk_length=8)
    for line in sys.stdin:
        if len(line) > 350000:
            break
        try:
            pcm = base64.b64decode(json.loads(line)['pcm'], validate=True)
            if not 0 < len(pcm) <= 256000 or len(pcm) % 2:
                raise ValueError()
            audio = np.frombuffer(pcm, dtype='<i2').astype(np.float32) / 32768
            audio = np.pad(audio, (max(0, 128000 - len(audio)), 0))[-128000:]
            with contextlib.redirect_stdout(sys.stderr):
                features = extractor(audio, sampling_rate=16000, return_tensors='np',
                                     padding='max_length', max_length=128000, truncation=True,
                                     do_normalize=True).input_features.astype(np.float32)
                probability = float(session.run(None, {'input_features': features})[0].reshape(-1)[0])
            print(json.dumps({'probability': probability}), flush=True)
        except Exception:
            print(json.dumps({'error': 'Local pause detection failed. Use Finish question.'}), flush=True)


if __name__ == '__main__':
    main()
