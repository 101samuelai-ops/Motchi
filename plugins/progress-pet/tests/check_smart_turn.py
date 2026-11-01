"""Local endpoint process bounds, verified setup and cancellation (no models)."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/completion-pet/scripts'))
from smart_turn import Endpoint, configuration, SHA256

checks=0
def check(value,label):
    global checks
    assert value,label
    checks+=1

with tempfile.TemporaryDirectory() as directory:
    root=Path(directory);model=root/'model.onnx';model.write_bytes(b'altered model')
    (root/'smart-turn.json').write_text(json.dumps({'python':sys.executable,'model':str(model),'sha256':SHA256}))
    try:configuration(root);corrupt=False
    except ValueError:corrupt=True
    check(corrupt,'An altered model cannot start under the pinned release checksum')
    worker=root/'fixture.py'
    worker.write_text('import base64,json,sys,time\nfor line in sys.stdin:\n pcm=base64.b64decode(json.loads(line)["pcm"]);assert len(pcm)<=256000\n if pcm[:2]==b"xx":time.sleep(5)\n score=float("nan") if pcm[:2]==b"nn" else .91\n print(json.dumps({"probability":score}),flush=True)\n')
    original=subprocess.Popen
    def spawn(command,**options):return original([sys.executable,'-u',str(worker)],**options)
    endpoint=Endpoint(root)
    try:
        with patch('smart_turn.configuration',return_value=(Path(sys.executable),model)),patch('smart_turn.subprocess.Popen',side_effect=spawn):
            check(endpoint.predict(bytes(500000))==.91,'Only bounded current-turn audio reaches the local worker')
            child=endpoint.process
            endpoint.predict(bytes(1000))
            check(endpoint.process is child,'Warm endpoint checks reuse the local model process')
            try:endpoint.predict(b'nn'*1000);invalid=False
            except ValueError:invalid=True
            check(invalid and child.poll() is not None and endpoint.process is None,
                  'A nonfinite result stops the worker instead of finalizing speech')
            calls=[0]
            def permitted():
                calls[0]+=1
                if calls[0]>3:raise ValueError('Question replaced')
            try:endpoint.predict(b'xx'*1000,permitted);cancelled=False
            except ValueError:cancelled=True
            check(cancelled and endpoint.process is None,'Supersession terminates a delayed endpoint computation')
            check(endpoint.predict(bytes(1000))==.91,'A later activation recovers after cancellation')
    finally:endpoint.close()
    check(not list(root.glob('*.wav')),'Endpoint checks never create temporary audio files')

print(f'{checks} local endpoint checksum, process, bounds and cancellation checks passed')
