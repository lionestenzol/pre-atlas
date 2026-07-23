"""AI Execution Pipeline — Flask spine.

Ported from harvest/487_marketing-for-beginners. The strongest blocks were
the Flask chat-log server variants that gained JSON persistence, API-key
auth, CORS, and optional OpenAI response generation. This file fuses them
into one runnable server and adds the execution-pipeline tracker from
final_output.md (iteration + workflow_status).
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from pipeline import ExecutionPipeline

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
CHAT_LOG_PATH = DATA_DIR / "chat_history.json"
PIPELINE_PATH = DATA_DIR / "pipeline_state.json"

VALID_API_KEYS = set(
    k.strip() for k in os.environ.get("PIPELINE_API_KEYS", "DEV_KEY").split(",") if k.strip()
)
CLAUDE_CLI = os.environ.get("CLAUDE_CLI", "claude")
CLAUDE_TIMEOUT = int(os.environ.get("CLAUDE_TIMEOUT", "120"))

app = Flask(__name__)
CORS(app)

pipeline = ExecutionPipeline(PIPELINE_PATH)


def _load_chat() -> dict:
    if CHAT_LOG_PATH.exists():
        try:
            return json.loads(CHAT_LOG_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {
        "conversation_id": "AI_EXEC_001",
        "session_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "summary": "AI Execution Pipeline log.",
        "messages": [],
    }


def _save_chat(chat: dict) -> None:
    CHAT_LOG_PATH.write_text(json.dumps(chat, indent=2), encoding="utf-8")


chat_history = _load_chat()


def _require_key() -> tuple[dict, int] | None:
    key = request.headers.get("X-API-KEY")
    if key not in VALID_API_KEYS:
        return {"error": "Unauthorized"}, 403
    return None


def _generate_response(user_input: str) -> str:
    try:
        result = subprocess.run(
            [CLAUDE_CLI, "-p", user_input],
            capture_output=True,
            text=True,
            timeout=CLAUDE_TIMEOUT,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            return f"[claude error {result.returncode}] {result.stderr.strip()[:500]}"
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        return f"[claude timeout after {CLAUDE_TIMEOUT}s]"
    except FileNotFoundError:
        return f"[claude CLI not found at: {CLAUDE_CLI}]"
    except Exception as exc:  # pragma: no cover
        return f"[error: {exc}]"


@app.get("/")
def index():
    return send_from_directory(Path(__file__).parent / "static", "index.html")


@app.get("/health")
def health():
    return {"status": "ok", "chat_count": len(chat_history["messages"])}


@app.get("/chatlog")
def get_chatlog():
    if (err := _require_key()):
        body, code = err
        return jsonify(body), code
    return jsonify(chat_history)


@app.post("/update_chat")
def update_chat():
    if (err := _require_key()):
        body, code = err
        return jsonify(body), code
    data = request.get_json(silent=True) or {}
    if not {"device_id", "user_input"} <= data.keys():
        return jsonify({"error": "Invalid data format"}), 400

    ai_response = data.get("gpt_response") or _generate_response(data["user_input"])
    entry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "device_id": data["device_id"],
        "user_input": data["user_input"],
        "gpt_response": ai_response,
    }
    chat_history["messages"].append(entry)
    _save_chat(chat_history)
    return jsonify({"status": "ok", "entry": entry})


@app.get("/pipeline")
def pipeline_state():
    if (err := _require_key()):
        body, code = err
        return jsonify(body), code
    return jsonify(pipeline.state())


@app.post("/pipeline/step")
def pipeline_step():
    if (err := _require_key()):
        body, code = err
        return jsonify(body), code
    data = request.get_json(silent=True) or {}
    step = data.get("step")
    status = data.get("status", "completed")
    if not step:
        return jsonify({"error": "step required"}), 400
    pipeline.record(step, status, note=data.get("note"))
    return jsonify(pipeline.state())


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=bool(os.environ.get("DEBUG")))
