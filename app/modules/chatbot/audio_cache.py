"""Bounded, process-local audio reuse. Keys never contain the narrated text."""
from collections import OrderedDict
import hashlib
import hmac
import json
from threading import RLock
import time

from flask import current_app
from app.modules.chatbot.recordings import STYLE
from app.modules.chatbot import settings

TTL = 600
MAX_BYTES = 16 * 1024 * 1024
MAX_ENTRIES = 32


class AudioCache:
    def __init__(self):
        self.entries = OrderedDict()
        self.pending = set()
        self.size = 0
        self.lock = RLock()

    def get(self, key):
        with self.lock:
            now = time.monotonic()
            for old in [old for old, (_, expires) in self.entries.items() if expires <= now]:
                self.size -= len(self.entries.pop(old)[0])
            if key not in self.entries:
                return None
            self.entries.move_to_end(key)
            return self.entries[key][0]

    def put(self, key, data):
        if not data or len(data) > MAX_BYTES:
            return
        with self.lock:
            previous = self.entries.pop(key, None)
            self.size -= len(previous[0]) if previous else 0
            self.entries[key] = (data, time.monotonic() + TTL)
            self.size += len(data)
            while self.size > MAX_BYTES or len(self.entries) > MAX_ENTRIES:
                _, (evicted, _) = self.entries.popitem(last=False)
                self.size -= len(evicted)

    def claim(self, key):
        with self.lock:
            if key in self.pending:
                return False
            self.pending.add(key)
            return True

    def release(self, key):
        with self.lock:
            self.pending.discard(key)


def cache_key(text, scope):
    payload = json.dumps([scope, settings.get('voice_name'), settings.get('voice_model'),
                          STYLE, text], ensure_ascii=False).encode()
    secret = current_app.secret_key
    if not isinstance(secret, bytes):
        secret = str(secret).encode()
    return hmac.new(secret, payload, hashlib.sha256).hexdigest()


def current():
    return current_app.extensions.setdefault('azul_voice_audio_cache', AudioCache())
