"""Text/acoustic agreement and bounded same-question repair; no microphone."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import struct
import sys
import tempfile
import threading
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/completion-pet/scripts'))
from mac_voice import MacVoice
from voice_companion import turn_text, VoiceCompanion
from android_host import AndroidPortal

checks = 0
def check(value, label):
    global checks
    assert value, label
    checks += 1
def frame(n): return struct.pack('<h', n)*320

cases = {
    'unfinished': [
        "How would you scale?", "How can I?", "Walk me through...", "Tell me about.",
        "What remains for the?", "I'm calling because.", "I want to.",
        "我想知道。", "你能不能？", "请告诉我这个项目的。", "尤其是。", "怎么把？",
    ],
    'request': [
        "Why that database?", "What remains?", "Walk me through your architecture.",
        "Describe your last project.", "How would you scale it to ten million users?",
        "What did you build, and what would you change?", "How does it work?",
        "I need an update on this project.", "完成了吗？", "项目进度？",
        "介绍一下这个项目。", "哪些完成了，还有哪些需要我处理？",
        "这个项目还有哪个任务没有完成？", "哪一个任务没完成？", "哪个项目还需要处理？",
        "這個項目哪項還沒完成？", "哪里需要修改？",
    ],
    'filler': ["Um...", "嗯。", ""],
    'acknowledgment': ["Yeah.", "Okay!", "好的。", "谢谢。"],
    'unknown': ["We use Kafka heavily here.", "The weather is pleasant today.", "Alpha"],
    'greeting': ["Hey Motchi!", "你好，莫奇。"],
}
for expected, texts in cases.items():
    for text in texts:
        check(turn_text(text)['state'] == expected, expected+': '+text)

class Portal:
    def __init__(self, transcript='and what still needs attention?'):
        self.voice = self; self.cancelled = []; self.transcript = transcript
    def cancel(self, *args): self.cancelled.append(args)
    def device_permitted(self, device): return True
    def voice_transcribe(self, audio, request):
        request['_permitted']()
        return self.transcript
    def run_mac_voice(self, device, request, audio, **extra):
        return {'wake': True, 'heard': 'What is finished?', 'text': 'OBSOLETE answer'}

with tempfile.TemporaryDirectory() as directory:
    binary = Path(directory)/'MacMicrophone'; binary.touch()
    def ready(transcript='and what still needs attention?'):
        portal = Portal(transcript); now = [100.]
        voice = MacVoice(portal, binary, clock=lambda: now[0])
        voice.owner = 'preview'; voice.epoch = 'original-generation'; voice.lease = 200
        voice.activate()
        for _ in range(90): voice.segmenter.push(frame(300))
        for _ in range(28): voice.segmenter.push(frame(0))
        original = voice.segmenter.finish()
        with patch.object(voice.worker, 'submit'):
            voice.finalize(original, 'What is finished?')
        return portal, voice, now, original
    def continuation(voice):
        with patch.object(voice.worker, 'submit') as submitted:
            for _ in range(40): voice.processing_frame('preview', frame(620))
            for _ in range(8): voice.processing_frame('preview', frame(0))
        return submitted.call_args.args

    portal, voice, now, original = ready()
    old = voice.epoch
    args = continuation(voice)
    check(not voice.answer_gate.is_set(), 'A possible continuation withholds the speculative answer')
    voice.check_continuation(*args[1:])
    check(voice.epoch != old and ('preview', old) in portal.cancelled and not voice.busy,
          'A meaningful continuation cancels the old provider and returns to listening')
    check(frame(300) in voice.segmenter.speech and frame(620) in voice.segmenter.speech,
          'Recovery keeps both the original question and the continuation audio')
    check(voice.events[-1].get('resumed') and voice.events[-1]['stopPlayback'],
          'The main-stage event explains recovery and invalidates obsolete playback')
    check(voice.timings['resumedQuestion'] and voice.active_until <= now[0]+30,
          'Recovery is the same bounded question, not an unrestricted follow-up session')
    voice.close()

    for text in ('Um.', 'Yeah.', '好的。'):
        portal, voice, now, original = ready(text); old = voice.epoch
        args = continuation(voice); voice.check_continuation(*args[1:])
        check(not voice.answer_gate.is_set(), 'An outdated acknowledgment cannot release subsequently captured words: '+text)
        candidate=voice.continuation; buffer=candidate['buffer']
        candidate['checked']=buffer.version
        voice.check_continuation('preview',voice.epoch,candidate,buffer.version,bytes(buffer.speech))
        for _ in range(30): voice.processing_frame('preview', frame(0))
        check(voice.epoch == old and voice.busy and voice.answer_gate.is_set(),
              'A thinking sound/acknowledgment releases the pending answer: '+text)
        voice.close()

    portal, voice, now, original = ready(); now[0] += 2.1
    with patch.object(voice.worker, 'submit') as submitted:
        for _ in range(80): voice.processing_frame('preview', frame(620))
    check(not submitted.called and voice.continuation['buffer'].speech is None,
          'Speech beginning outside the repair window cannot become a new question')
    voice.close()

    portal, voice, now, original = ready(); old = voice.epoch
    args = continuation(voice)
    started = threading.Event()
    def fast_result(*args, **extra):
        started.set()
        return {'wake': True, 'heard': 'What is finished?', 'text': 'OBSOLETE answer'}
    portal.run_mac_voice = fast_result
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(voice.recognize, 'preview', old, original, False, True, 'What is finished?')
        check(started.wait(1) and not future.done(),
              'Even an immediately finished provider waits while a continuation is checked')
        voice.check_continuation(*args[1:]); future.result(timeout=2)
    check(not any(e.get('text') == 'OBSOLETE answer' for e in voice.events) and voice.epoch != old,
          'A superseded answer cannot escape after continuation recovery')
    voice.close()

    portal, voice, now, original = ready()
    args = continuation(voice); voice.stop()
    check(voice.answer_gate.is_set() and voice.pending_audio is None and voice.continuation is None,
          'Pause releases waiting workers and discards all continuation audio')
    voice.close()

    portal, voice, now, original = ready()
    voice.activate()
    for _ in range(90): voice.segmenter.push(frame(300))
    for _ in range(28): voice.segmenter.push(frame(0))
    version = voice.segmenter.version
    inner_allowed = []
    def resumed_while_transcribing(audio, request):
        voice.segmenter.push(frame(620))
        request['_permitted'](); inner_allowed.append(True)
        return 'An old snapshot'
    portal.voice_transcribe = resumed_while_transcribing
    def exact_revision():
        voice.valid('preview', voice.epoch)
        if voice.segmenter.version != version: raise ValueError('Speech resumed')
    try:
        voice.transcribe_candidate('preview', voice.epoch, version, original, exact_revision)
        stale_rejected = False
    except ValueError: stale_rejected = True
    check(inner_allowed and stale_rejected and voice.checked_transcript is None,
          'Resumed words reject the stale snapshot without cancelling/reloading the warm ASR worker')
    voice.close()

    class Endpoint:
        def predict(self, pcm, permitted): return .2
        def close(self): pass
    portal, voice, now, original = ready('How would you scale?')
    voice.activate()
    for _ in range(90): voice.segmenter.push(frame(300))
    for _ in range(60): voice.segmenter.push(frame(0))
    voice.endpoint = Endpoint()
    voice.assess_endpoint('preview', voice.epoch, voice.segmenter.version, voice.segmenter.endpoint_audio())
    check(not voice.busy and voice.events[-1]['transcript'] == 'How would you scale?' and
          voice.text_decision['state'] == 'unfinished',
          'Uncertain acoustic candidates still display their caption while holding the question')
    voice.close()

    for choice in (False, True):
        portal, voice, now, original = ready('Alpha')
        voice.activate()
        for _ in range(90): voice.segmenter.push(frame(300))
        for _ in range(60): voice.segmenter.push(frame(0))
        class Confident:
            def predict(self, pcm, permitted): return .99
            def close(self): pass
        voice.endpoint=Confident(); portal.choice_pending=lambda *_:choice
        with patch.object(voice.worker,'submit'):
            voice.assess_endpoint('preview',voice.epoch,voice.segmenter.version,voice.segmenter.endpoint_audio())
        check(voice.busy == choice,
              'A short unrecognized name needs a pending project-choice context before auto-submission: '+str(choice))
        voice.close()

    # Reproduce the reported Chinese wording using a generic fixture and a hesitant .48 endpoint. Manual
    # Finish must not be needed, nor may an unrelated standalone statement
    # remain listening forever after explicit activation.
    for text,score,frames,expected in [
        ('这个项目还有哪个任务没有完成？',.48,28,False),
        ('这个项目还有哪个任务没有完成？',.48,60,True),
        ('这个项目还有哪个任务没有完成？',.1,100,True),
        ('I feel tired today.',.2,100,False),
        ('I feel tired today.',.2,150,True),
        ('我今天感觉有点累。',.2,150,True),
        ('Tell me about the project, especially.',.99,150,False),
        ('我想了解这个项目，尤其是。',.99,150,False),
        ('Alpha',.2,150,False),
    ]:
        portal,voice,now,original=ready(text);voice.activate()
        for _ in range(90):voice.segmenter.push(frame(300))
        for _ in range(frames):voice.segmenter.push(frame(0))
        class Hesitant:
            def predict(self,pcm,permitted):return score
            def close(self):pass
        voice.endpoint=Hesitant()
        with patch.object(voice.worker,'submit') as submitted:
            voice.assess_endpoint('preview',voice.epoch,voice.segmenter.version,voice.segmenter.endpoint_audio())
        check(voice.busy==expected and submitted.call_count==int(expected),
              'Automatic completion after real silence: '+text+' / '+str(frames*20)+' ms')
        if expected:
            check(voice.timings['finishMode']=='automatic','Automatic completion is observable separately from manual Finish')
        voice.close()

    # The permission callback must not hold the companion session lock. A fresh
    # activation needs that lock to cancel the exact generation it is replacing.
    entered = threading.Event(); release = threading.Event()
    companion = VoiceCompanion(lambda _: 'What remains?', lambda: [], lambda *a: None, lambda _: True,
                               discuss=lambda r: {'scope': 'general', 'text': 'A task remains.'})
    def guard(): entered.set(); release.wait(2)
    request = {'generation': 'guard-generation', 'activated': True, '_permitted': guard}
    with ThreadPoolExecutor(max_workers=2) as executor:
        old = executor.submit(companion.run, 'preview', request, b'audio')
        check(entered.wait(1), 'The in-process answer guard runs outside the session lock')
        cancelled = executor.submit(companion.cancel, 'preview', 'guard-generation')
        cancelled.result(timeout=1); release.set()
        try: old.result(timeout=2); rejected = False
        except ValueError: rejected = True
    check(rejected, 'Cancellation can acquire the session lock while an answer waits')

    portal = object.__new__(AndroidPortal)
    portal.root = Path(directory); portal.speech_lock = threading.Lock()
    portal.transcriber = portal.transcribe
    class Qwen:
        def recognize(self, audio, language, permitted): return language
    portal.qwen = Qwen()
    with patch('android_host.doubao_speech.selected', return_value='qwen'):
        for language in ('en', 'zh', 'auto'):
            result = portal.voice_transcribe(b'fixture', {'language': language, '_permitted': lambda: None})
            check(result == language, 'Qwen honors the selected speech language: '+language)

print(f'{checks} bilingual turn cues, continuation, caption, language and cancellation checks passed')
