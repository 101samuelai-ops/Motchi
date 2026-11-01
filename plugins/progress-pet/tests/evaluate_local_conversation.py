"""Explicit local synthetic speech smoke test, not a human accuracy benchmark.

Uses installed macOS voices and private speech models. No microphone capture,
cloud audio, project questions or answer-provider calls. Temporary audio is
deleted on exit; only a requested JSON report of public fixtures is retained.
"""
import argparse
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/completion-pet/scripts'))
from qwen_speech import Recognizer
from smart_turn import Endpoint
from voice_companion import unfinished


def normalized(text, language):
    return re.findall(r"[a-z0-9]+", text.casefold()) if language == 'en' else re.findall(r"[\w]", text.casefold())


def errors(expected, actual):
    row = list(range(len(actual) + 1))
    for i, word in enumerate(expected, 1):
        following = [i]
        for j, found in enumerate(actual, 1):
            following.append(min(following[-1] + 1, row[j] + 1, row[j-1] + (word != found)))
        row = following
    return row[-1] / max(1, len(expected))


def wav(pcm):
    result = io.BytesIO()
    with wave.open(result, 'wb') as stream:
        stream.setnchannels(1); stream.setsampwidth(2); stream.setframerate(16000); stream.writeframes(pcm)
    return result.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true', help='Run the already installed local models')
    parser.add_argument('--root', type=Path, default=Path.home() / 'Library/Application Support/Mochi/android')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    if not args.run:
        parser.error('Use --run to opt in to local synthetic evaluation. No human speech is recorded.')
    recognizer, endpoint = Recognizer(args.root), Endpoint(args.root)
    report = {'kind': 'synthetic-smoke-only', 'humanAccuracyEstablished': False, 'cases': []}
    try:
        with tempfile.TemporaryDirectory(prefix='motchi-synthetic-voice-') as directory:
            directory = Path(directory)
            def synth(text, language):
                source, target = directory / 'fixture.aiff', directory / 'fixture.wav'
                subprocess.run(['/usr/bin/say', '-v', 'Samantha' if language == 'en' else 'Tingting',
                                '-o', str(source)], input=text, text=True, check=True, timeout=30)
                subprocess.run(['/usr/bin/afconvert', '-f', 'WAVE', '-d', 'LEI16@16000', '-c', '1',
                                str(source), str(target)], check=True, timeout=15)
                with wave.open(str(target), 'rb') as stream:
                    return stream.readframes(stream.getnframes())
            cases = [
                ('english-complete', 'en', True, 'What still needs attention in the calendar project?'),
                ('english-unfinished', 'en', False, 'Could you tell me about the project, especially'),
                ('chinese-complete', 'zh', True, '请告诉我这个项目还有哪些任务没有完成？'),
                ('chinese-unfinished', 'zh', False, '我想了解这个项目的进度，尤其是'),
            ]
            for name, language, complete, text in cases:
                pcm = synth(text, language)
                start = time.monotonic(); probability = endpoint.predict(pcm + bytes(19200))
                endpoint_ms = round((time.monotonic() - start)*1000)
                start = time.monotonic(); transcript = recognizer.recognize(wav(pcm), 'auto')
                item = {'name': name, 'expectedComplete': complete, 'probability': round(probability, 5),
                        'acousticAutoFinish': probability >= .65, 'guardHeld': unfinished(transcript),
                        'autoFinishes': probability >= .65 and not unfinished(transcript), 'endpointMs': endpoint_ms,
                        'asrMs': round((time.monotonic() - start)*1000), 'expected': text, 'transcript': transcript,
                        'syntheticTokenErrorRate': round(errors(normalized(text, language), normalized(transcript, language)), 4)}
                report['cases'].append(item)
                print(json.dumps(item, ensure_ascii=False), flush=True)
    finally:
        recognizer.close(); endpoint.close()
    report['endpointCasesCorrect'] = sum(c['expectedComplete'] == c['autoFinishes'] for c in report['cases'])
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print('Synthetic endpoint cases correct:', report['endpointCasesCorrect'], '/', len(report['cases']))
    print('This is not a human speech, noise, speaker or echo acceptance result.')


if __name__ == '__main__':
    main()
