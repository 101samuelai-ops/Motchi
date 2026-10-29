"""Local wake-name routing. Unaddressed speech never reaches the answer provider.

Ambient wake detection stays on the Mac. The selected provider may refine
addressed speech. This controller asks read-only questions, never work or approvals.
"""
import re
import secrets
import subprocess
import tempfile
import threading
import time
from pathlib import Path


def addressed(text):
    # Require the name at the start, optionally preceded by a greeting. Do not
    # wake on someone mentioning Motchi in an unrelated conversation.
    match = re.match(r"^\s*(?:(?:hey|hi|hello|okay|ok)[\s,.!，。！:：-]+|(?:你好|您好|嘿|嗨|喂)[，,\s]*)?(?:motchi|mochi|莫奇|莫琪|摩奇|麻糬|麻薯)(?=$|[\s,.!?，。！？:：'’的帮幫请請你])", text, re.I)
    return text[match.end():].lstrip(' ,.!?，。！？:：') if match else None


def project_matches(text, projects):
    text = text.casefold().replace('’', "'")
    matches = []
    for project in projects:
        for alias in [project['name']] + project.get('aliases', []):
            alias = alias.casefold().strip()
            if not alias or (len(alias) < 3 and not re.search(r'[\u3400-\u9fff]', alias) and text.strip() != alias):
                continue
            pattern = re.escape(alias)
            if re.fullmatch(r"[\w .'-]+", alias, re.ASCII):
                pattern = r'(?<!\w)' + pattern + r'(?!\w)'
            if re.search(pattern, text):
                matches.append(project)
                break
    return matches


class VoiceCompanion:
    def __init__(self, transcribe, projects, ask, permitted, speak=None, clock=time.monotonic, transcribe_request=None, refine_addressed=None, discuss=None):
        self.transcribe, self.projects, self.ask = transcribe, projects, ask
        self.permitted, self.speak, self.clock = permitted, speak, clock
        self.transcribe_request = transcribe_request
        self.refine_addressed = refine_addressed
        self.discuss = discuss
        self.lock = threading.RLock()
        self.sessions = {}
        self.cancelled = {}

    def cancel(self, device, generation):
        with self.lock:
            self.cancelled[(device, generation)] = self.clock()
            self.sessions.pop(device, None)
            self.cancelled = {k: v for k, v in self.cancelled.items() if self.clock() - v < 3600}

    def allowed(self, device, generation):
        with self.lock:
            if (device, generation) in self.cancelled or not self.permitted(device):
                raise ValueError('Wake listening was paused or device access was revoked.')

    def run(self, device, request, audio):
        generation = request.get('generation')
        if not isinstance(generation, str) or not re.fullmatch(r'[a-zA-Z0-9-]{8,100}', generation):
            raise ValueError('A voice session generation is required.')
        self.allowed(device, generation)
        with self.lock:
            old = self.sessions.get(device, {})
            continuing = bool(request.get('session') and request['session'] == old.get('id') and
                              generation == old.get('generation') and old.get('awaiting') is True and old.get('until', 0) > self.clock())
            same_session=bool(request.get('session') and request['session']==old.get('id') and generation==old.get('generation'))
            session = dict(old) if same_session else {'id': secrets.token_urlsafe(24), 'generation': generation}
            if generation==old.get('generation') and old.get('question') and old.get('choiceUntil',0)>self.clock():
                session['question']=old['question'];session['choices']=old.get('choices',[])
        # Provider choice cannot turn ambient listening into cloud capture.
        # Only the server-validated follow-up lease, explicit Listen now, or a
        # locally recognized wake name authorizes cloud refinement.
        request = dict(request, _device=device, _addressed=continuing or request.get('activated') is True)
        text = (self.transcribe_request(audio,request) if self.transcribe_request else self.transcribe(audio)).strip()
        self.allowed(device, generation)
        command = addressed(text)
        if command is None and not continuing and request.get('activated') is not True:
            return {'wake': False}
        if command is not None and not request['_addressed'] and self.refine_addressed:
            text = self.refine_addressed(audio, dict(request,_addressed=True), text).strip()
            self.allowed(device, generation)
            command = addressed(text)
        command = text if command is None else command
        projects = self.projects()
        selected = next((p for p in projects if p['id'] == request.get('projectId')), None)
        named = project_matches(command, projects)
        result = {'wake': True, 'session': session['id'], 'sessionSeconds': 30, 'heard': command, 'transcript': text}
        if request.get('preview') is True:
            result.update(partial=True, text=command or "I'm listening. Go ahead.")
            self.allowed(device, generation)
            with self.lock:
                session['until'] = self.clock() + 20
                session['awaiting'] = True
                self.sessions[device] = session
            return result
        if command and self.discuss:
            pending=session.pop('question',None)
            query=(pending+' Project: '+command) if pending else command
            answer=self.discuss({'text':query,
                                 'projectId':request.get('projectId'),'selection':request.get('selection')})
            self.allowed(device,generation)
            result.update(answer,question=command)
            if answer.get('scope')=='choice':session.update(question=pending or command,choiceUntil=self.clock()+60)
        elif not command:
            result['text'] = "I'm here. What would you like to ask about your projects?"
        else:
            choices = session.get('choices', [])
            # A spoken project name can resolve the previous ambiguity while
            # retaining the original question, rather than asking it again.
            if len(named) == 1:
                selected = named[0]
            elif len(named) > 1:
                selected = None
            if not named and choices:
                selected = None
                ordinal = re.fullmatch(r'(?:(?:the|number)\s+)?(first|second|third|fourth|one|two|three|four|1|2|3|4)(?:\s+one)?[.!?]?', command.strip(), re.I)
                if ordinal:
                    index = {'first': 0, 'one': 0, '1': 0, 'second': 1, 'two': 1, '2': 1,
                             'third': 2, 'three': 2, '3': 2, 'fourth': 3, 'four': 3, '4': 3}[ordinal[1].lower()]
                    selected = next((p for p in projects if index < len(choices) and p['id'] == choices[index]), None)
            if selected:
                question = session.pop('question', None) or command
                session.pop('choices', None)
                selection = request.get('selection') if selected['id'] == request.get('projectId') else selected['selection']
                if not any(c['id'] == selection for c in selected['chats']):
                    raise ValueError('The selected chat changed. Refresh the project.')
                self.allowed(device, generation)
                answer = self.ask(selected, selection, question)
                self.allowed(device, generation)
                result.update(text=answer.get('text') or 'No answer was returned. Please try again.',
                              projectId=selected['id'], selection=selection, projectName=selected['name'], question=question)
            else:
                candidates = named or projects
                session.update(question=session.get('question') or command, choices=[p['id'] for p in candidates],choiceUntil=self.clock()+60)
                result.update(choices=[{'id': p['id'], 'name': p['name'], 'folderLabel': p.get('folderLabel', '')} for p in candidates],
                              text='Which project do you mean? ' + ', '.join(p['name'] for p in candidates[:4]) +
                              ('. Say its name or choose it on the screen.' if candidates else 'Open a project in Codex on your Mac first.'))
        self.allowed(device, generation)
        with self.lock:
            session['awaiting'] = not bool(command)
            session['until'] = self.clock() + (20 if session['awaiting'] else 0)
            result['sessionSeconds'] = 20 if session['awaiting'] else 0
            self.sessions[device] = session
        return result


def spoken_wav(text):
    """Offline macOS speech. The caller owns the short-lived output bytes."""
    text = str(text).strip()[:650]
    if not text:
        return None
    with tempfile.TemporaryDirectory(prefix='motchi-reply-') as directory:
        root = Path(directory)
        source, target = root / 'reply.aiff', root / 'reply.wav'
        # Passing stdin prevents text from becoming a command/option. Use a
        # locally installed Chinese voice when appropriate; never download it.
        args = ['/usr/bin/say', '-o', str(source)]
        if re.search(r'[\u3400-\u9fff]', text):
            voices = subprocess.run(['/usr/bin/say', '-v', '?'], capture_output=True, text=True, timeout=5).stdout
            match = re.search(r'^(.+?)\s+zh_CN\b', voices, re.M)
            voice = match[1].strip() if match else None
            if voice:
                args += ['-v', voice]
        subprocess.run(args, input=text.encode(), capture_output=True, check=True, timeout=40)
        subprocess.run(['/usr/bin/afconvert', '-f', 'WAVE', '-d', 'LEI16@22050', str(source), str(target)],
                       capture_output=True, check=True, timeout=15)
        data = target.read_bytes()
        return data if len(data) <= 4_000_000 else None
