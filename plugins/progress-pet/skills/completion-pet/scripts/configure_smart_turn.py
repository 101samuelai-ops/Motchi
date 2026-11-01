"""Install the optional local bilingual pause detector, separately from Git."""
import argparse
import hashlib
from pathlib import Path
import subprocess
import tempfile
from configure_doubao import save_private
from qwen_speech import config as qwen_config
from smart_turn import configuration, REVISION, SHA256

URL = 'https://huggingface.co/pipecat-ai/smart-turn-v3/resolve/' + REVISION + '/smart-turn-v3.2-cpu.onnx'
RUNTIME = 'onnxruntime==1.31.1'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.home() / 'Library/Application Support/Mochi/android')
    parser.add_argument('--install', action='store_true')
    args = parser.parse_args()
    if args.install:
        python, _ = qwen_config(args.root)
        subprocess.run([str(python), '-m', 'pip', 'install', RUNTIME], check=True)
        target = args.root / 'models/smart-turn-v3.2-cpu.onnx'
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='motchi-turn-setup-', dir=args.root) as directory:
            download = Path(directory) / 'model.onnx'
            subprocess.run(['curl', '--fail', '--location', '--retry', '2', '--max-time', '180',
                            URL, '--output', str(download)], check=True)
            if hashlib.sha256(download.read_bytes()).hexdigest() != SHA256:
                raise ValueError('Pause model checksum does not match the pinned official release.')
            download.replace(target)
        save_private(args.root / 'smart-turn.json', {'python': str(python), 'model': str(target),
                     'sha256': SHA256, 'revision': REVISION, 'runtime': RUNTIME, 'source': URL})
    configuration(args.root)
    print('Local Smart Turn configured. Real bilingual pause accuracy still needs a microphone test.')


if __name__ == '__main__':
    main()
