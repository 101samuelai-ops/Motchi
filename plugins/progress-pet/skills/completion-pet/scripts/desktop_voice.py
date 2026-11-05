"""App-owned listening and local UI fan-out. Never creates a network credential."""
import base64
from collections import deque
import json
import threading
import time

import microphone_policy

DEVICE = 'motchi-local-desktop'


class DesktopVoice:
    def __init__(self, portal, emit):
        self.portal, self.emit = portal, emit
        self.path = portal.root / 'desktop-voice.json'
        try:
            self.enabled = json.loads(self.path.read_text()).get('enabled') is True
        except (OSError, ValueError, AttributeError):
            self.enabled = False
        self.lock = threading.RLock()
        self.events = deque(maxlen=32)
        self.clients = {}
        self.stopped = threading.Event()
        self.context = {'projectId': None, 'selection': None}
        self.language = 'auto'
        self.retry_at = 0
        self.last_error = None
        portal.desktop_voice = self
        portal.mac_voice.event_listener = self.publish
        self.thread = threading.Thread(target=self.run, daemon=True, name='motchi-desktop-voice')

    def publish(self, event):
        # Called under MacVoice's lock. Never acquire that lock in reverse order.
        with self.lock:
            self.events.append(dict(event))
            for queue, _ in self.clients.values():
                if not event.get('audioOnly'):
                    queue.append(dict(event, spokenReply=False))

    def set_enabled(self, enabled):
        if type(enabled) is not bool:
            raise ValueError('Choose whether Motchi should listen.')
        with self.portal.mac_voice.lock:
            self.enabled = enabled
            temporary = self.path.with_suffix('.tmp')
            temporary.write_text(json.dumps({'enabled': enabled}))
            temporary.replace(self.path)
            # This control is native/local-only. Persist Pause at the shared
            # capture boundary so an older paired client cannot undo it.
            microphone_policy.save(self.portal.root, {'paused': not enabled})
            self.retry_at = 0
            if not enabled:
                self.portal.mac_voice.stop()
                with self.lock:
                    self.events.clear()
                    for queue, _ in self.clients.values(): queue.clear()

    def tick(self):
        voice = self.portal.mac_voice
        with voice.lock:
            if self.enabled and microphone_policy.allowed(self.portal.root, DEVICE):
                permitted_owner = voice.owner and self.portal.device_permitted(voice.owner)
                alive = voice.process and voice.process.poll() is None
                if permitted_owner and alive:
                    # Preserve an already active paired session and its question.
                    voice.lease = voice.clock() + 25
                elif time.monotonic() >= self.retry_at:
                    self.retry_at = time.monotonic() + 10
                    try:
                        owner = voice.owner if permitted_owner else DEVICE
                        context = voice.context if permitted_owner else self.context
                        language = voice.language if permitted_owner else self.language
                        voice.control(owner, dict(context, enabled=True,
                            conversationVersion=2, language=language))
                        self.last_error = None
                    except (OSError, ValueError) as error:
                        self.last_error = str(error)[:300]
            state = voice.snapshot()
            owner = voice.owner
            state['desktopManaged'] = True
            state['speaking'] = voice.playback_active
            if self.last_error and not state['enabled']: state['issue'] = self.last_error
            with self.lock:
                events = list(self.events); self.events.clear()
                self.clients = {k:v for k,v in self.clients.items()
                                if time.monotonic()-v[1]<60 and self.portal.device_permitted(k)}
            events = [event for event in events if event.get('turnId') == state.get('turnId')]
            for event in events:
                if event.get('audioOnly') and owner == DEVICE and voice.playback_ticket == (event.get('turnId'), event.get('operationId')):
                    with self.portal.lock:
                        audio = self.portal.voice_audio.get((DEVICE, event.get('operationId')))
                    if audio: event['wav'] = base64.b64encode(audio[1]).decode()
        self.emit({'type': 'desktopVoice', 'state': state, 'events': events,
                   'autoListen': self.enabled})

    def control(self, body):
        if 'enabled' in body and body.get('heartbeat') is not True:
            self.set_enabled(body['enabled'])
        voice = self.portal.mac_voice
        with voice.lock:
            if self.enabled and not voice.owner and body.get('enabled') is True and body.get('heartbeat') is not True:
                voice.control(DEVICE, dict(self.context, enabled=True,
                    language=self.language, conversationVersion=2))
            if voice.owner == DEVICE:
                if 'projectId' in body:
                    self.context = {key: body.get(key) or None for key in ('projectId', 'selection')}
                if body.get('language') in ('en', 'zh', 'auto'): self.language = body['language']
                if self.enabled:
                    voice.control(DEVICE, dict(body, **self.context, enabled=True,
                        language=self.language, conversationVersion=2))
            elif voice.owner and any(body.get(k) for k in ('activate', 'finish', 'playbackOperationId')):
                raise ValueError('The paired device owns this voice conversation. Use its voice controls or pause it first.')

    def poll(self, device, body=None):
        if not self.portal.device_permitted(device): raise ValueError('Device access revoked.')
        with self.lock:
            queue, _ = self.clients.setdefault(device, (deque(maxlen=32), time.monotonic()))
            self.clients[device] = (queue, time.monotonic())
        if body is not None:
            self.control({k:v for k,v in body.items() if k in
                ('enabled','heartbeat','projectId','selection','language','activate','finish')})
        voice = self.portal.mac_voice
        with voice.lock:
            state = dict(voice.snapshot(), desktopManaged=True, speaking=voice.playback_active)
            with self.lock:
                state['events'] = [e for e in queue if e.get('turnId') == state.get('turnId')]
                queue.clear()
        return state

    def run(self):
        while not self.stopped.wait(.35):
            try: self.tick()
            except (OSError, ValueError) as error: self.last_error = str(error)[:300]

    def close(self):
        self.stopped.set()
        if self.thread.is_alive(): self.thread.join(timeout=2)
        self.portal.mac_voice.event_listener = None
        self.portal.mac_voice.stop()
