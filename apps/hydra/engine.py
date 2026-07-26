#!/usr/bin/env python3
"""HYDRA engine — the snake's stomach.

The browser game cannot clone repos, can't run delta-scp, and must never hold
delta-scp's API key. This thin local service is the missing organ between them:

    HYDRA (browser :8898)  --POST /eat {repo_url}-->  HYDRA engine (:8899)
                                                          | holds the key, server-side
                                                          v
                                            delta-scp demo gateway (:3012)
                                            clones + digests -> compressed_state
                                                          |
                                                          v
        a real digest lands in the tail  <-- compact summary + full digest cached to vault/

Stdlib only — no pip install. Run:  python apps/hydra/engine.py
"""

import json
import os
import re
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# ---- config (env-overridable) ------------------------------------------------
PORT = int(os.environ.get("HYDRA_ENGINE_PORT", "8899"))
SCP_URL = os.environ.get("HYDRA_SCP_URL", "http://127.0.0.1:3012")
SCP_ENV = os.environ.get(
    "HYDRA_SCP_ENV",
    r"C:\Users\bruke\pre-atlas\services\delta-scp\.env",
)
VAULT = Path(__file__).resolve().parent / "vault"
VAULT.mkdir(exist_ok=True)


def scp_key() -> str:
    """Read delta-scp's Bearer key from its .env — the key stays on this side."""
    env = os.environ.get("SCP_API_KEY")
    if env:
        return env
    try:
        for line in Path(SCP_ENV).read_text(encoding="utf-8").splitlines():
            if line.startswith("SCP_API_KEY="):
                return line.split("=", 1)[1].strip()
    except OSError:
        pass
    return ""


def slug(repo_url: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", repo_url.lower()).strip("-")


def summarize(job: dict, repo_url: str) -> dict:
    """Reduce delta-scp's compressed_state to what the tail shows — the bite."""
    cs = job.get("compressed_state") or {}
    nodes = cs.get("symbolic_nodes") or []
    graph = job.get("graph") or {}

    files = []
    total_symbols = 0
    for n in nodes:
        syms = n.get("symbols") or []
        total_symbols += len(syms)
        files.append({
            "path": n.get("path"),
            "language": n.get("language"),
            "symbols": len(syms),
            "names": [s.get("name") for s in syms[:6] if s.get("name")],
        })
    top = sorted(files, key=lambda f: f["symbols"], reverse=True)[:8]

    return {
        "repo_url": repo_url,
        "status": job.get("status"),
        "generated_at": cs.get("generated_at"),
        "languages": cs.get("languages") or {},
        "file_count": len(nodes),
        "symbol_count": total_symbols,
        "top_files": top,
        "graph": {"nodes": graph.get("node_count"), "edges": graph.get("edge_count")},
        "stats": cs.get("stats") or {},
    }


def digest_repo(repo_url: str) -> dict:
    """Send the repo to delta-scp, cache the full digest, return the summary."""
    key = scp_key()
    body = json.dumps({"repo_url": repo_url}).encode()
    req = urllib.request.Request(
        SCP_URL + "/jobs", data=body, method="POST",
        headers={"Content-Type": "application/json",
                 **({"Authorization": "Bearer " + key} if key else {})},
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        payload = json.loads(resp.read().decode())
    job = payload.get("job") or payload
    if job.get("status") != "complete":
        raise RuntimeError("delta-scp did not complete: " + str(job.get("error_log") or job.get("status")))

    # cache the FULL digest to the vault — real bytes landing on disk
    (VAULT / (slug(repo_url) + ".json")).write_text(json.dumps(job, indent=1), encoding="utf-8")
    return summarize(job, repo_url)


# ---- HTTP --------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, obj: dict):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self._send(204, {})

    def do_GET(self):
        if self.path == "/health":
            return self._send(200, {"ok": True, "service": "hydra-engine", "scp": SCP_URL})
        if self.path == "/vault":
            items = []
            for f in sorted(VAULT.glob("*.json")):
                try:
                    job = json.loads(f.read_text(encoding="utf-8"))
                    items.append(summarize(job, job.get("repo_url", f.stem)))
                except Exception:
                    continue
            return self._send(200, {"ok": True, "digests": items})
        self._send(404, {"ok": False, "error": "not found"})

    def do_POST(self):
        if self.path != "/eat":
            return self._send(404, {"ok": False, "error": "not found"})
        try:
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n).decode() or "{}")
        except Exception:
            return self._send(400, {"ok": False, "error": "bad JSON body"})
        repo_url = (body.get("repo_url") or "").strip()
        if not repo_url:
            return self._send(400, {"ok": False, "error": "repo_url required"})
        if not repo_url.startswith("http"):
            repo_url = "https://github.com/" + repo_url.strip("/")
        try:
            return self._send(200, {"ok": True, "digest": digest_repo(repo_url)})
        except urllib.error.URLError as e:
            return self._send(502, {"ok": False, "error": "delta-scp unreachable on " + SCP_URL + " (" + str(e.reason) + ")"})
        except Exception as e:  # noqa: BLE001 — surface the real failure to the UI
            return self._send(500, {"ok": False, "error": str(e)})

    def log_message(self, *a):  # quiet
        pass


if __name__ == "__main__":
    print(f"[hydra-engine] listening on :{PORT}  ->  delta-scp {SCP_URL}  ·  vault {VAULT}")
    print(f"[hydra-engine] key {'loaded' if scp_key() else 'MISSING (set SCP_API_KEY or HYDRA_SCP_ENV)'}")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
