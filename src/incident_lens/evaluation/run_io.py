"""Small durable file primitives for development execution, without provider I/O."""

import json
import os
import time
from pathlib import Path
from uuid import uuid4


def atomic_bytes(path, content, *, exclusive=False):
    """Publish complete bytes; tolerate bounded Windows reader sharing locks.

    Exclusive publication never overwrites an existing artifact. A same-volume
    hard link provides atomic no-clobber publication; unsupported filesystems
    fail visibly rather than falling back to a partially visible write.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid4().hex + ".tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        for attempt in range(5):
            try:
                if exclusive:
                    os.link(temporary, path)
                else:
                    os.replace(temporary, path)
                return
            except PermissionError:
                if attempt == 4:
                    raise
                time.sleep(0.05 * (attempt + 1))
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            # A scanner may still hold the temporary inode. Do not replace the
            # publication exception or turn a successful publication into failure.
            pass


def atomic_json(path, value, *, exclusive=False):
    atomic_bytes(path, (json.dumps(value, ensure_ascii=False, indent=2,
                                  allow_nan=False) + "\n").encode("utf-8"),
                 exclusive=exclusive)


def append_json(path, value):
    """A single-writer append; a damaged tail is never silently truncated."""
    with Path(path).open("ab") as stream:
        stream.write((json.dumps(value, ensure_ascii=False, allow_nan=False) + "\n").encode())
        stream.flush()
        os.fsync(stream.fileno())
