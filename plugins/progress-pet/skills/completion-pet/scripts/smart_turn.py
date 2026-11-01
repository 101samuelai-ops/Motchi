"""Optional local endpoint worker. Audio stays in bounded private pipes."""
import base64
import hashlib
import json
import math
from pathlib import Path
import queue
import subprocess
import threading
import time

REVISION = 'f766f81d3cfdf7737ac64aad813d91bbfd56bf93'
SHA256 = '2bb026316b14a660486a75b1733cd3fbab8c2fd0314dc9af7be49f8cca967e4f'


def configuration(root):
    try:
        value = json.loads((Path(root) / 'smart-turn.json').read_text())
        python, model = Path(value['python']), Path(value['model'])
        if not python.is_absolute() or not python.is_file() or not model.is_absolute() or not model.is_file():
            raise ValueError()
        if value.get('sha256') != SHA256 or hashlib.sha256(model.read_bytes()).hexdigest() != SHA256:
            raise ValueError()
        return python, model
    except (OSError, KeyError, TypeError, ValueError):
        raise ValueError('Local pause detection is not configured. Use Finish question.') from None


class Endpoint:
    def __init__(self, root):
        self.root = Path(root)
        self.lock = threading.Lock()
        self.process = None
        self.responses = None

    def start(self):
        if self.process and self.process.poll() is None:
            return
        python, model = configuration(self.root)
        self.process = subprocess.Popen(
            [str(python), '-u', str(Path(__file__).with_name('smart_turn_worker.py')), str(model)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        process, responses = self.process, queue.Queue(maxsize=2)
        self.responses = responses

        def receive():
            try:
                for line in process.stdout:
                    if len(line) > 2048:
                        break
                    responses.put(json.loads(line), timeout=1)
            except (OSError, ValueError, queue.Full):
                pass
            finally:
                try:
                    responses.put_nowait({'error': 'Local pause detector stopped. Use Finish question.'})
                except queue.Full:
                    pass
        threading.Thread(target=receive, daemon=True, name='motchi-endpoint-results').start()

    def predict(self, pcm, permitted=lambda: None):
        with self.lock:
            permitted()
            self.start()
            try:
                # Only current-turn context; never a previous question or a file.
                self.process.stdin.write(json.dumps({'pcm': base64.b64encode(pcm[-256000:]).decode()}) + '\n')
                self.process.stdin.flush()
                deadline = time.monotonic() + 25
                while time.monotonic() < deadline:
                    permitted()
                    try:
                        result = self.responses.get(timeout=.1)
                    except queue.Empty:
                        continue
                    score = result.get('probability')
                    if isinstance(score, bool) or not isinstance(score, (float, int)) or not math.isfinite(score) or not 0 <= score <= 1:
                        raise ValueError('Local pause detection failed. Use Finish question.')
                    return score
                raise ValueError('Local pause detection timed out. Use Finish question.')
            except BaseException:
                self.close()
                raise

    def close(self):
        process, self.process = self.process, None
        if process:
            try:
                process.terminate()
                process.wait(timeout=2)
            except (OSError, subprocess.TimeoutExpired):
                try:
                    process.kill()
                    process.wait(timeout=2)
                except OSError:
                    pass
