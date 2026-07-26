import json
import subprocess
from pathlib import Path
from typing import Optional, Union

from .models import Festival, ProgressReport, NextTask

FEST_BIN = "fest"
DEFAULT_ROOT = Path(r"C:\Users\bruke\festival-project")
FESTIVAL_BUCKETS = ("active", "planning", "ready")
DUNGEON_BUCKETS = ("dungeon/completed", "dungeon/archived", "dungeon/someday")


class FestError(RuntimeError):
    pass


class FestClient:
    def __init__(self, root: Path = DEFAULT_ROOT, bin: str = FEST_BIN):
        self.root = Path(root)
        self.bin = bin

    def _run(
        self,
        *args: str,
        json_out: bool = True,
        cwd: Optional[Path] = None,
    ) -> Union[dict, list, str]:
        cmd = [self.bin, *args]
        if json_out:
            cmd.append("--json")
        try:
            r = subprocess.run(
                cmd,
                cwd=str(cwd or self.root),
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            raise FestError(
                f"fest {' '.join(args)} failed (exit {e.returncode}): {e.stderr.strip()}"
            ) from e
        return json.loads(r.stdout) if json_out else r.stdout

    def list(self, status: Optional[str] = None, all_: bool = False) -> list[Festival]:
        args: list[str] = ["list"]
        if status:
            args.append(status)
        if all_:
            args.append("--all")
        raw = self._run(*args)
        out: list[Festival] = []
        if isinstance(raw, dict):
            for key, val in raw.items():
                if isinstance(val, list):
                    out.extend(Festival(**f) for f in val)
        return out

    def progress(self, festival: str) -> ProgressReport:
        return ProgressReport(**self._run("progress", cwd=self._path(festival)))

    def next(self, festival: str) -> NextTask:
        return NextTask(**self._run("next", cwd=self._path(festival)))

    def status(self) -> dict:
        return self._run("status")

    def commits(self, festival: str) -> list:
        raw = self._run("commits", cwd=self._path(festival))
        return raw if isinstance(raw, list) else [raw]

    def promote(self, festival: str, dungeon: Optional[str] = None, force: bool = False) -> str:
        args = ["promote"]
        if dungeon:
            args += ["--dungeon", dungeon]
        if force:
            args.append("--force")
        return self._run(*args, json_out=False, cwd=self._path(festival))

    def task_complete(self, festival: str, task_id: str) -> str:
        return self._run(
            "task", "complete", task_id, json_out=False, cwd=self._path(festival)
        )

    def _path(self, name: str) -> Path:
        for bucket in FESTIVAL_BUCKETS:
            p = self.root / "festivals" / bucket / name
            if p.exists():
                return p
        for bucket in DUNGEON_BUCKETS:
            root = self.root / "festivals" / bucket
            if not root.exists():
                continue
            for date_dir in root.iterdir():
                p = date_dir / name
                if p.exists():
                    return p
        raise FileNotFoundError(f"festival not found: {name}")
