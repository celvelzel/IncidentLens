"""Opt-in recording of public pre-decision payloads; no environment or secret reads."""

from pathlib import Path
from threading import Lock

from .resolver import canonical


class SnapshotRecorder:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = Lock()

    def __call__(self, event):
        with self.lock, self.path.open("a", encoding="utf-8") as handle:
            handle.write(canonical(event) + "\n")
