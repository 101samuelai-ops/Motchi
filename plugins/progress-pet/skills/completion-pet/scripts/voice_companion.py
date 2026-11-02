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
    match = re.match(r"^\s*(?:(?:hey|hi|hello|okay|ok)[\s,.!，。！:：-]+|(?:你好|您好|嘿|嗨|喂)[，,。.!！:：\s]*)?(?:motchi|mochi|莫奇|莫琪|摩奇|麻糬|麻薯)(?=$|[\s,.!?，。！？:：'’的帮幫请請你])", text, re.I)
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


def unfinished(text):
    """Conservative extra hold for explicit unfinished clauses, not a turn model.

    Run only after the acoustic completion model. Manual Finish bypasses this
    guard; punctuation added by ASR cannot turn a dangling clause into a fact.
    """
    text = text.strip().rstrip(' ,.!?，。！？:：;；…').casefold()
    return bool(re.search(r"\b(?:and|or|but|because|especially|including|whether|such as|for example|if|although|unless|whereas)$", text)
                or re.search(r'(?:尤其是|特别是|特別是|因为|因為|所以|但是|可是|如果|以及|然后|然後|比如|例如|还有|還有|包括)$', text))


def explicit_question(text):
    """Bounded text confirmation for a hesitant acoustic end prediction.

    ASR punctuation alone is insufficient. This is a heuristic for explicit
    questions/requests, not a language model or main-speaker identification.
    """
    text = text.strip().rstrip(' ,.!?，。！？:：;；…').casefold()
    if unfinished(text) or re.search(r'\b(?:the|a|an|my|your|of|to|for|about|with|in|on|is|are|was|were)$|(?:的|关于|關於|是否|有没有|有沒有)$', text):
        return False
    english = len(re.findall(r'\b[a-z]+\b', text)) >= 5 and re.search(
        r'\b(?:what|which|when|where|why|how|who)\b|\b(?:can|could|would|will) you\b|\b(?:tell|show|explain|summarize)\b', text)
    chinese = len(re.findall(r'[\u3400-\u9fff]', text)) >= 8 and re.search(
        r'什么|什麼|哪些|多少|怎么|怎麼|如何|为什么|為什麼|吗|嗎|请|請|告诉|告訴', text)
    return bool(english or chinese)


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
        self.revisions = {}

    def cancel(self, device, generation):
        with self.lock:
            self.cancelled[(device, generation)] = self.clock()
            if self.sessions.get(device, {}).get('generation') == generation:
                self.sessions.pop(device, None)
            self.cancelled = {k: v for k, v in self.cancelled.items() if self.clock() - v < 3600}

    def allowed(self, device, generation):
        with self.lock:
            if (device, generation) in self.cancelled or not self.permitted(device):
                raise ValueError('Wake listening was paused or device access was revoked.')

    def replace(self, device, generation, replacement):
        """A fresh wake may retain an unresolved project choice, never a lease."""
        with self.lock:
            previous = self.sessions.get(device, {})
            self.cancel(device, generation)
            if previous.get('generation') == generation and previous.get('question') and previous.get('choiceUntil', 0) > self.clock():
                self.sessions[device] = {k: previous[k] for k in ('question', 'choices', 'choiceUntil') if k in previous}
                self.sessions[device].update(generation=replacement, id=secrets.token_urlsafe(24), awaiting=False, until=0)

    def run(self, device, request, audio, *, transcript=None):
        generation = request.get('generation')
        if not isinstance(generation, str) or not re.fullmatch(r'[a-zA-Z0-9-]{8,100}', generation):
            raise ValueError('A voice session generation is required.')
        self.allowed(device, generation)
        with self.lock:
            self.allowed(device, generation)
            previous = self.revisions.get(device, (generation, 0))
            revision = (previous[1] if previous[0] == generation else 0) + (request.get('preview') is not True)
            stamp = (generation, revision)
            self.revisions[device] = stamp
            old = self.sessions.get(device, {})
            continuing = bool(request.get('session') and request['session'] == old.get('id') and
                              generation == old.get('generation') and old.get('awaiting') is True and old.get('until', 0) > self.clock())
            same_session=bool(request.get('session') and request['session']==old.get('id') and generation==old.get('generation'))
            session = dict(old) if same_session else {'id': secrets.token_urlsafe(24), 'generation': generation}
            if generation==old.get('generation') and old.get('question') and old.get('choiceUntil',0)>self.clock():
                session['question']=old['question'];session['choices']=old.get('choices',[])
        def current():
            with self.lock:
                self.allowed(device, generation)
                if self.revisions.get(device) != stamp:
                    raise ValueError('Voice request was superseded by the completed question.')
        # Provider choice cannot turn ambient listening into cloud capture.
        # Only the server-validated follow-up lease, explicit Listen now, or a
        # locally recognized wake name authorizes cloud refinement.
        request = dict(request, _device=device, _addressed=continuing or request.get('activated') is True,
                       _permitted=current)
        # Only trusted in-process callers can reuse a checked endpoint transcript.
        # A JSON request field cannot bypass recognition.
        text = (transcript if transcript is not None else
                self.transcribe_request(audio,request) if self.transcribe_request else self.transcribe(audio)).strip()
        current()
        command = addressed(text)
        if command is None and not continuing and request.get('activated') is not True:
            return {'wake': False}
        if command is not None and not request['_addressed'] and self.refine_addressed:
            text = self.refine_addressed(audio, dict(request,_addressed=True), text).strip()
            current()
            command = addressed(text)
        command = text if command is None else command
        projects = self.projects()
        selected = next((p for p in projects if p['id'] == request.get('projectId')), None)
        named = project_matches(command, projects)
        result = {'wake': True, 'session': session['id'], 'sessionSeconds': 30, 'heard': command, 'transcript': text}
        if request.get('preview') is True:
            result.update(partial=True, text=command or "I'm listening. Go ahead.")
            with self.lock:
                current()
                session['until'] = self.clock() + 20
                session['awaiting'] = True
                self.sessions[device] = session
            return result
        if command and self.discuss:
            pending=session.pop('question',None)
            query=(pending+' Project: '+command) if pending else command
            answer=self.discuss({'text':query,
                                 'projectId':request.get('projectId'),'selection':request.get('selection'),
                                 '_permitted':current})
            current()
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
                current()
                answer = self.ask(selected, selection, question)
                current()
                result.update(text=answer.get('text') or 'No answer was returned. Please try again.',
                              projectId=selected['id'], selection=selection, projectName=selected['name'], question=question)
            else:
                candidates = named or projects
                session.update(question=session.get('question') or command, choices=[p['id'] for p in candidates],choiceUntil=self.clock()+60)
                result.update(choices=[{'id': p['id'], 'name': p['name'], 'folderLabel': p.get('folderLabel', '')} for p in candidates],
                              text='Which project do you mean? ' + ', '.join(p['name'] for p in candidates[:4]) +
                              ('. Say its name or choose it on the screen.' if candidates else 'Open a project in Codex on your Mac first.'))
        with self.lock:
            current()
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
