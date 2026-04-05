"""
Atomic file write utility for cognitive-sensor.

Uses temp-file-then-rename pattern to prevent partial reads.
On POSIX, os.replace() is atomic. On Windows, it is atomic
for same-volume renames (which temp files in same dir guarantee).
"""
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


def atomic_write_text(path: Path, content: str) -> None:
    """Write content atomically via temp file + rename."""
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(dir=parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_path, str(path))
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def atomic_write_json(path: Path, data: Any, **kwargs: Any) -> None:
    """Write JSON atomically. Accepts same kwargs as json.dump (indent, etc)."""
    kwargs.setdefault("indent", 2)
    content = json.dumps(data, **kwargs)
    atomic_write_text(path, content)
