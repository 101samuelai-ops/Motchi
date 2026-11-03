"""Explicit local synthetic speech smoke test, not a human accuracy benchmark.

Uses installed macOS voices and private speech models. No microphone capture
or cloud audio. --live-answer explicitly permits a read-only project question
to the configured answer provider. Temporary audio is deleted on exit.
"""
import argparse
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/completion-pet/scripts'))
from qwen_speech import Recognizer
from smart_turn import Endpoint
from voice_companion import unfinished, turn_text


def joined_turn(root, pcm, recognizer, continuation_at=None, connection=None, fixture_delay=0):
    """Paced public synthetic PCM through the real wake/turn controller.

    Does not open a microphone. An explicitly supplied connection permits one
    read-only live answer; the default uses a local routing fixture.
    """
    from mac_voice import MacVoice
    from voice_companion import VoiceCompanion
    sample_position = [0]
    class Portal:
        def __init__(self):
            self.root = Path(scratch.name)
            for name in ('wake.json', 'smart-turn.json', 'speech-provider.json'):
                if (root/name).is_file(): shutil.copy2(root/name, self.root/name)
            self.questions = []
            self.voice = VoiceCompanion(lambda _: '', lambda: [], lambda *a: {}, lambda _: True,
                                        transcribe_request=self.voice_transcribe,
                                        discuss=self.discuss)
        def discuss(self, request):
            self.questions.append({'sample': sample_position[0], 'text': request['text']})
            if connection is None:
                deadline = time.monotonic()+fixture_delay
                while time.monotonic() < deadline:
                    request['_permitted'](); time.sleep(.05)
                return {'scope': 'general', 'text': 'Synthetic routing received.'}
            job = connection.request('/v1/operations', {'action': 'discuss', 'text': request['text'],
                                                       'operationId': str(uuid.uuid4())})
            deadline = time.monotonic()+80
            while job['status'] in ('queued', 'running') and time.monotonic() < deadline:
                request['_permitted']()
                time.sleep(.2)
                job = connection.request('/v1/operations/'+job['id'])
            if job['status'] != 'done': raise ValueError('Live read-only answer did not complete.')
            return job['result']
        def device_permitted(self, device): return True
        def voice_transcribe(self, audio, request):
            return recognizer.recognize(audio, 'auto', request['_permitted'])
        def run_mac_voice(self, device, request, audio, **extra):
            return self.voice.run(device, request, audio, **extra)
    class Input:
        def __init__(self): self.position = 0
        def read(self, length):
            time.sleep(.02)
            data = pcm[self.position:self.position+length]
            self.position += length
            sample_position[0] = self.position
            if len(data) != length:
                # A finite fixture ended normally, not a failed microphone.
                with voice.lock: voice.process = None
            return data
    class Child:
        stdout = Input()
        stderr = io.BytesIO()
        def poll(self): return None
        def terminate(self): pass
        def wait(self, timeout=None): pass
    scratch = tempfile.TemporaryDirectory(prefix='motchi-paced-controller-')
    portal = Portal(); voice = MacVoice(portal)
    try:
        voice.wake_detector.start()
        deadline = time.monotonic()+12
        while not voice.wake_detector.ready:
            if time.monotonic() >= deadline: raise ValueError('Synthetic wake startup timed out.')
            time.sleep(.05)
        recognizer.warm(); voice.endpoint.start()
        voice.owner = 'synthetic-device'; voice.epoch = str(uuid.uuid4())
        voice.lease = time.monotonic()+60; voice.process = Child()
        voice.capture(voice.owner, voice.epoch, voice.process)
        deadline = time.monotonic()+(85 if connection else 8)
        while (voice.busy or voice.endpoint_pending or voice.preview) and time.monotonic() < deadline: time.sleep(.05)
        events = list(voice.events)
        final = next((event for event in reversed(events) if not event.get('partial') and event.get('heard')), {})
        return {'wakeReceived': bool(voice.last_wake), 'questionSubmitted': bool(final),
                'heard': final.get('heard'), 'answer': final.get('text'), 'timings': voice.timings,
                'questionCount': len(portal.questions), 'endpointProbability': voice.endpoint_score,
                'answerCount': sum(not e.get('partial') and bool(e.get('heard')) for e in events),
                'attemptedQuestions': [q['text'] for q in portal.questions],
                'stage': voice.stage, 'issue': voice.issue, 'endpointIssue': voice.endpoint_issue,
                'lastCheckedTranscript': voice.checked_transcript[2] if voice.checked_transcript else None,
                'submittedDuringThinkingPause': bool(continuation_at and any(q['sample'] < continuation_at for q in portal.questions))}
    finally:
        voice.close()
        scratch.cleanup()


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
    parser.add_argument('--joined', action='store_true', help='Also test public joined wake/question audio through the real controller')
    parser.add_argument('--pause-cases', action='store_true', help='Exercise unfinished phrases with a one-second pause before continuing')
    parser.add_argument('--conversation-cases', action='store_true', help='Exercise article-style short, indirect, stacked and repaired turns')
    parser.add_argument('--name-only', action='store_true', help='Test name-only English/Chinese and similar pronunciations at quiet microphone levels')
    parser.add_argument('--live-answer', action='store_true', help='Use the running Mac read-only answer provider for one public synthetic project question')
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
            if args.conversation_cases:
                cases += [
                    ('short-question', 'en', True, 'Why that database?'),
                    ('indirect-request', 'en', True, 'Walk me through your project.'),
                    ('missing-question-object', 'en', False, 'How would you scale'),
                    ('missing-instruction-object', 'en', False, 'Walk me through'),
                    ('stacked-question', 'en', True, 'What did you build, and what would you change?'),
                    ('short-chinese', 'zh', True, '项目进度怎么样？'),
                    ('missing-chinese-object', 'zh', False, '请告诉我这个项目的'),
                ]
            for name, language, complete, text in cases:
                pcm = synth(text, language)
                start = time.monotonic(); probability = endpoint.predict(pcm + bytes(19200))
                endpoint_ms = round((time.monotonic() - start)*1000)
                start = time.monotonic(); transcript = recognizer.recognize(wav(pcm), 'auto')
                item = {'name': name, 'expectedComplete': complete, 'probability': round(probability, 5),
                        'acousticAutoFinish': probability >= .65, 'guardHeld': unfinished(transcript),
                        'autoFinishes': ((probability >= .65 or probability >= .4 and turn_text(transcript)['state']=='request')
                                         and turn_text(transcript)['state'] not in ('unfinished','filler','acknowledgment')),
                        'textState': turn_text(transcript)['state'], 'endpointMs': endpoint_ms,
                        'asrMs': round((time.monotonic() - start)*1000), 'expected': text, 'transcript': transcript,
                        'syntheticTokenErrorRate': round(errors(normalized(text, language), normalized(transcript, language)), 4)}
                report['cases'].append(item)
                print(json.dumps(item, ensure_ascii=False), flush=True)
            if args.joined:
                report['joinedTurns'] = []
                for language, text in [('en', 'Hey Mochi, what still needs attention in the calendar project?'),
                                       ('zh', '你好莫奇，请告诉我这个项目还有哪些任务没有完成？')]:
                    result = joined_turn(args.root, synth(text, language)+bytes(96000), recognizer)
                    result.update(language=language, expected=text)
                    report['joinedTurns'].append(result)
                    print(json.dumps(result, ensure_ascii=False), flush=True)
            if args.name_only:
                report['nameOnlyTurns'] = []
                for language, text, level in [('en','Mochi, what remains in this project?',1),
                                               ('zh','莫奇，项目进度怎么样？',1),
                                               ('en','Moji, what is finished?',.02),
                                               ('zh','默契，请告诉我项目进度。',.02)]:
                    from array import array
                    pcm=array('h',(int(n*level) for n in array('h',synth(text,language)))).tobytes()
                    result=joined_turn(args.root,pcm+bytes(128000),recognizer)
                    result.update(language=language,expected=text,fixtureLevel=level)
                    report['nameOnlyTurns'].append(result)
                    print(json.dumps(result,ensure_ascii=False),flush=True)
                report['wakeNegatives'] = []
                for language,text in [('en','Hello, how is everyone doing today?'),
                                      ('en','The calendar project is finished.'),
                                      ('zh','我们今天下午讨论项目进度。'),
                                      ('zh','这个项目还有哪些任务没有完成？')]:
                    result=joined_turn(args.root,synth(text,language)+bytes(64000),recognizer)
                    result.update(language=language,expectedWake=False)
                    report['wakeNegatives'].append(result)
                    print(json.dumps(result,ensure_ascii=False),flush=True)
                report['noiseTails'] = []
                import math,random
                rng=random.Random(194)
                noise=array('h',(int(130*math.sin(n*2*math.pi*200/16000)+rng.uniform(-170,170))
                                 for n in range(128000))).tobytes()
                for language,text in [('en','Mochi, what is finished?'),('zh','莫奇，项目进度怎么样？')]:
                    result=joined_turn(args.root,synth(text,language)+noise,recognizer)
                    result.update(language=language,kind='speech-then-room-noise')
                    report['noiseTails'].append(result)
                    print(json.dumps(result,ensure_ascii=False),flush=True)
            if args.conversation_cases:
                report['conversationTurns'] = []
                for language, first, last, delay in [
                    ('en', 'Hey Mochi, how would you scale', 'this project to ten million users?', 0),
                    ('en', 'Hey Mochi, what is finished?', 'and what still needs my attention?', 3),
                    ('zh', '你好莫奇，哪些任务完成了？', '还有哪些任务需要我处理？', 3),
                ]:
                    beginning=synth(first,language)+bytes(38400)
                    result=joined_turn(args.root,beginning+synth(last,language)+bytes(128000),recognizer,
                                       continuation_at=len(beginning),fixture_delay=delay)
                    result.update(language=language, kind='unfinished-clause' if not delay else 'resumed-after-complete-clause')
                    result['continuationIncluded'] = (''.join(normalized(last,language)) in
                                                     ''.join(normalized(result.get('heard') or '',language)))
                    report['conversationTurns'].append(result)
                    print(json.dumps(result,ensure_ascii=False),flush=True)
                report['wakeAliases'] = []
                for language, text in [('en','Hello Mochi, what remains in this project?'),
                                       ('zh','你好默契，请告诉我这个项目的进度。')]:
                    pcm=synth(text,language)
                    # Compare a quieter fixture to the measured microphone
                    # signal range; this is still synthesized speech, not a
                    # human wake-accuracy result.
                    from array import array
                    quiet=array('h',(int(n*.15) for n in array('h',pcm))).tobytes()
                    result=joined_turn(args.root,quiet+bytes(96000),recognizer)
                    result.update(language=language,expected=text)
                    report['wakeAliases'].append(result)
                    print(json.dumps(result,ensure_ascii=False),flush=True)
                report['wakeNegatives'] = []
                for language, text in [('en','Hello, how is everyone doing today?'),
                                       ('zh','我们今天下午讨论项目进度。')]:
                    result=joined_turn(args.root,synth(text,language)+bytes(64000),recognizer)
                    result.update(language=language,expectedWake=False)
                    report['wakeNegatives'].append(result)
                    print(json.dumps(result,ensure_ascii=False),flush=True)
            if args.pause_cases:
                report['thinkingPauses'] = []
                for language, first, last in [
                    ('en', 'Hey Mochi, could you tell me about the project, especially', 'what still needs attention?'),
                    ('zh', '你好莫奇，我想了解这个项目的进度，尤其是', '还有哪些任务没有完成？')]:
                    beginning = synth(first, language) + bytes(32000)
                    result = joined_turn(args.root, beginning+synth(last, language)+bytes(96000), recognizer,
                                         continuation_at=len(beginning))
                    result.update(language=language)
                    report['thinkingPauses'].append(result)
                    print(json.dumps(result, ensure_ascii=False), flush=True)
            if args.live_answer:
                sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'android'))
                from preview_live import MacConnection
                connection = MacConnection(args.root)
                try:
                    report['liveAnswer'] = joined_turn(args.root, synth('Hey Mochi, how is the Motchi project progressing?', 'en')+bytes(96000),
                                                      recognizer, connection=connection)
                    print(json.dumps(report['liveAnswer'], ensure_ascii=False), flush=True)
                finally:
                    connection.close()
    finally:
        recognizer.close(); endpoint.close()
    report['endpointCasesCorrect'] = sum(c['expectedComplete'] == c['autoFinishes'] for c in report['cases'])
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print('Synthetic endpoint cases correct:', report['endpointCasesCorrect'], '/', len(report['cases']))
    print('This is not a human speech, noise, speaker or echo acceptance result.')
    correct = report['endpointCasesCorrect'] == len(report['cases'])
    for key in ('joinedTurns', 'thinkingPauses', 'conversationTurns', 'wakeAliases', 'nameOnlyTurns', 'noiseTails'):
        for result in report.get(key, []):
            correct = correct and result['wakeReceived'] and result['questionSubmitted'] and result['answerCount'] == 1
            if key == 'thinkingPauses' or result.get('kind') == 'unfinished-clause':
                correct = correct and not result['submittedDuringThinkingPause']
            if result.get('kind') == 'resumed-after-complete-clause':
                # With slower scheduling, speech can resume before finalizing
                # the first clause. Holding it naturally is also correct.
                correct = correct and result.get('continuationIncluded') and (
                    result['timings'].get('resumedQuestion') is True or result['questionCount']==1)
    correct = correct and all(not r['wakeReceived'] and not r['questionSubmitted'] for r in report.get('wakeNegatives', []))
    if not correct: raise SystemExit('Some synthetic conversation checks failed; inspect the report before claiming success.')


if __name__ == '__main__':
    main()
