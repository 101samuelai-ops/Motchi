"""Wake privacy, bounded sessions, exact routing and cancellation regressions."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/completion-pet/scripts'))
from voice_companion import VoiceCompanion, addressed, project_matches

checks = 0
def check(value, label):
    global checks
    assert value, label
    checks += 1

def rejected(fn):
    try: fn(); return False
    except ValueError: return True

alpha = {'id': 'alpha', 'name': 'Alpha', 'aliases': ['Alpha'], 'selection': 'alpha-chat', 'chats': [{'id': 'alpha-chat'}]}
beta = {'id': 'beta', 'name': 'Beta', 'aliases': ['Beta'], 'selection': 'beta-chat', 'chats': [{'id': 'beta-chat'}]}
time = [1.0]; transcript = ['']; calls = []; permission = [True]
def ask(p, selection, text):
    calls.append((p['id'], selection, text)); return {'text': 'Recorded answer'}
voice = VoiceCompanion(lambda _: transcript[0], lambda: [alpha, beta], ask, lambda _: permission[0], clock=lambda: time[0])
request = {'generation': 'generation-1234'}
def run(text, **extra):
    transcript[0] = text
    return voice.run('calendar-a', {**request, **extra}, b'local test audio')

check(addressed('Hey Motchi, how is Alpha?') == 'how is Alpha?', 'A greeted wake name extracts the question')
check(addressed('Mochi!') == '', 'A standalone spoken name wakes Motchi')
check(addressed('嗨莫奇，请问项目进度') == '请问项目进度', 'Chinese wake aliases are supported')
check(addressed('We discussed Motchi yesterday') is None, 'A name mentioned inside ambient speech does not wake')
check(addressed('Hey Mochington') is None, 'A name prefix cannot activate listening')
result = run('How is Alpha?', projectId='alpha', selection='alpha-chat')
check(result == {'wake': False} and not calls, 'Unaddressed speech is discarded even with a project selected')
result = run('Hey Motchi')
check(result['wake'] and not calls and 'heard' in result, 'A wake alone responds locally without an answer-provider request')
token = result['session']
result = run('How is Alpha doing?', session=token)
check(calls[-1] == ('alpha', 'alpha-chat', 'How is Alpha doing?'), 'An addressed follow-up chooses the explicitly named project')
before_calls=len(calls)
check(run('What remains?',session=token,projectId='alpha',selection='alpha-chat')=={'wake':False} and len(calls)==before_calls,'After answering once, the old follow-up token cannot capture background speech')
result = run('Hey Motchi, What remains?', session=token, projectId='alpha', selection='alpha-chat')
check(calls[-1] == ('alpha', 'alpha-chat', 'What remains?'), 'A newly addressed follow-up stays on the selected project')
result = run('Hey Motchi, How is Beta doing?', session=token, projectId='alpha', selection='alpha-chat')
check(calls[-1][0:2] == ('beta', 'beta-chat'), 'An explicit new project can switch discussion without cross-chat delivery')
before = len(calls)
run('What remains?', session='another-device-token', projectId='alpha', selection='alpha-chat')
check(len(calls) == before, 'An unrelated session token cannot turn ambient speech into a question')
time[0] += 31
run('What remains?', session=token, projectId='alpha', selection='alpha-chat')
check(len(calls) == before, 'Follow-up sessions expire; a new wake name is required')
result = run('Hey Motchi, what needs my attention?')
check(len(result['choices']) == 2 and len(calls) == before, 'An unnamed home question asks for a project')
result = run('Hey Motchi, Beta', session=result['session'])
check(calls[-1] == ('beta', 'beta-chat', 'what needs my attention?'), 'Spoken project clarification retains the original question')
result = run('Hey Motchi, compare Alpha and Beta', projectId='alpha', selection='alpha-chat')
before = len(calls)
result2 = run('Hey Motchi, not sure', session=result['session'], projectId='alpha', selection='alpha-chat')
check(result2.get('choices') and len(calls) == before, 'A pending ambiguous choice cannot silently revert to the old project')
run('Hey Motchi, the second one', session=result2['session'])
check(calls[-1] == ('beta', 'beta-chat', 'compare Alpha and Beta'), 'Spoken ordinals can resolve a presented project list')
check(rejected(lambda: run('Hey Motchi, what remains?', projectId='alpha', selection='beta-chat')), 'A stale foreign chat identity is rejected')
before = len(calls)
result = run('Hey Motchi, add tablet support to Alpha')
check(len(calls) == before + 1 and calls[-1][0] == 'alpha', 'An imperative voice question uses only the read-only answer function')
voice.cancel('calendar-a', request['generation'])
check(rejected(lambda: run('Hey Motchi, how is Alpha?')), 'Pausing invalidates in-flight voice generations')
permission[0] = False
check(rejected(lambda: voice.run('new-calendar', {'generation': 'generation-new'}, b'audio')), 'Revoked devices cannot run recognition')
permission[0] = True
def cancelling(_):
    voice2.cancel('calendar-a', 'cancel-generation'); return 'Hey Motchi, how is Alpha?'
voice2 = VoiceCompanion(cancelling, lambda: [alpha, beta], ask, lambda _: True)
before = len(calls)
check(rejected(lambda: voice2.run('calendar-a', {'generation': 'cancel-generation'}, b'audio')) and len(calls) == before,
      'Cancellation during transcription prevents a later provider request')
duplicate = {**beta, 'name': 'Alpha', 'aliases': ['Alpha']}
check(len(project_matches('Alpha', [alpha, duplicate])) == 2, 'Identical project names remain ambiguous')
check(not project_matches('alphabetical', [alpha]), 'Project substring matches cannot steal a question')
live = VoiceCompanion(lambda _: transcript[0], lambda: [alpha, beta], ask, lambda _: True, clock=lambda: time[0])
live_request = {'generation': 'live-generation', 'projectId': 'alpha', 'selection': 'alpha-chat'}
before = len(calls)
transcript[0] = 'an unrelated conversation about Alpha'
check(live.run('live-calendar', {**live_request, 'preview': True}, b'audio') == {'wake': False},
      'Live previews do not expose ambient conversation')
transcript[0] = 'Hey Motchi, how is Alpha'
preview = live.run('live-calendar', {**live_request, 'preview': True}, b'audio')
check(preview.get('partial') and preview['heard'] == 'how is Alpha' and len(calls) == before,
      'A live transcript wakes the UI without calling the answer provider')
transcript[0] = 'Hey Motchi, how is Alpha doing today?'
finished = live.run('live-calendar', {**live_request, 'session': preview['session']}, b'audio')
check(not finished.get('partial') and calls[-1] == ('alpha', 'alpha-chat', 'how is Alpha doing today?') and len(calls) == before + 1,
      'Only the final full utterance asks the project question once')
transcript[0] = 'What remains?'
manual = live.run('manual-calendar', {**live_request, 'preview': True, 'activated': True}, b'audio')
check(manual['partial'] and manual['heard'] == 'What remains?' and len(calls) == before + 1,
      'Explicit Listen now permits live text without a wake word and never executes work')
check(live.run('another-calendar', {**live_request, 'activated': 'true'}, b'audio') == {'wake': False},
      'Activation must be an explicit boolean')
print(f'{checks} wake privacy, routing, expiry and cancellation checks passed')
