"""Minimal polling client — ported from harvest blocks 12/15/19/27.

Polls the chatlog and prints new entries. Also supports sending a message.

Usage:
    python client.py poll
    python client.py send "hello AI"
"""
from __future__ import annotations

import os
import sys
import time

import requests

SERVER = os.environ.get("PIPELINE_SERVER", "http://127.0.0.1:5000")
API_KEY = os.environ.get("PIPELINE_API_KEY", "DEV_KEY")
DEVICE_ID = os.environ.get("PIPELINE_DEVICE_ID", "Device_A")
HEADERS = {"X-API-KEY": API_KEY}


def poll(interval: float = 5.0) -> None:
    seen = 0
    while True:
        try:
            r = requests.get(f"{SERVER}/chatlog", headers=HEADERS, timeout=5)
            r.raise_for_status()
            msgs = r.json().get("messages", [])
            for msg in msgs[seen:]:
                print(f"{msg['timestamp']} {msg['device_id']}: {msg['user_input']}")
                print(f"    -> {msg['gpt_response']}")
            seen = len(msgs)
        except requests.RequestException as exc:
            print(f"[poll error] {exc}")
        time.sleep(interval)


def send(text: str) -> None:
    r = requests.post(
        f"{SERVER}/update_chat",
        headers={**HEADERS, "Content-Type": "application/json"},
        json={"device_id": DEVICE_ID, "user_input": text},
        timeout=15,
    )
    print(r.status_code, r.text)


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "poll":
        poll()
    elif cmd == "send":
        send(" ".join(sys.argv[2:]) or "ping")
    else:
        print(f"unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
