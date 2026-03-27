"""
ContextMemory — Mémoire contextuelle AI persistante cross-audit
Permet de stocker, récupérer et enrichir dynamiquement le contexte partagé entre audits, agents et hooks AI.
Stockage sur disque (JSON) pour persistance, accès thread-safe, API simple.
"""

import json
import threading
from pathlib import Path
from typing import Any


class ContextMemory:
    _lock = threading.Lock()
    _memory_file = Path("persistence/context_memory.json")

    def __init__(self):
        self._data = {}
        self._load()

    def _load(self):
        if self._memory_file.exists():
            try:
                with self._memory_file.open("r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except Exception:
                self._data = {}
        else:
            self._data = {}

    def save(self):
        with self._lock:
            with self._memory_file.open("w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any):
        with self._lock:
            self._data[key] = value
            self.save()

    def append(self, key: str, value: Any):
        with self._lock:
            if key not in self._data or not isinstance(self._data[key], list):
                self._data[key] = []
            self._data[key].append(value)
            self.save()

    def all(self) -> dict:
        return dict(self._data)
