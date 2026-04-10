#!/usr/bin/env python3
"""
UASC Executor Service — Port 3008

Accepts command tokens from delta-kernel and executes profiles.
Bridge between governance (what to do) and execution (how to do it).
"""

import json
import sqlite3
import os
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from datetime import datetime
from typing import Optional, Tuple

from auth import Authenticator, AuthResult
from executor import ProfileExecutor, ExecutionResult


# Configuration
DB_PATH = os.path.join(os.path.dirname(__file__), 'storage', 'registry.db')
PROFILES_DIR = os.path.join(os.path.dirname(__file__), 'profiles')
DEFAULT_PORT = 3008
DEFAULT_HOST = 'localhost'


class UASCDatabase:
    """SQLite database interface for UASC registry."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        schema_path = os.path.join(os.path.dirname(__file__), 'storage', 'schema.sql')
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            if os.path.exists(schema_path):
                with open(schema_path) as f:
                    conn.executescript(f.read())

    def get_client(self, client_id: str) -> Optional[Tuple[str, str, bool]]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                'SELECT secret_hash, roles, enabled FROM clients WHERE client_id = ?',
                (client_id,)
            )
            row = cursor.fetchone()
            if row:
                return (row[0], row[1], bool(row[2]))
            return None

    def get_command(self, cmd: str) -> Optional[dict]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                'SELECT profile_id, version, enabled, allowed_roles FROM commands WHERE cmd = ?',
                (cmd,)
            )
            row = cursor.fetchone()
            if row:
                return {
                    'profile_id': row[0],
                    'version': row[1],
                    'enabled': bool(row[2]),
                    'allowed_roles': row[3].split(',')
                }
            return None

    def create_run(self, run_id: str, cmd: str, profile_id: str, version: int, client_id: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                '''INSERT INTO runs (run_id, cmd, profile_id, version, client_id, status)
                   VALUES (?, ?, ?, ?, ?, 'running')''',
                (run_id, cmd, profile_id, version, client_id)
            )

    def complete_run(self, run_id: str, status: str, error: Optional[str] = None) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                '''UPDATE runs SET status = ?, ended_at = datetime('now'), error = ?
                   WHERE run_id = ?''',
                (status, error, run_id)
            )

    def log_event(self, run_id: str, step_idx: int, step_type: str, event_type: str, payload: dict) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                '''INSERT INTO run_events (run_id, step_idx, step_type, event_type, payload)
                   VALUES (?, ?, ?, ?, ?)''',
                (run_id, step_idx, step_type, event_type, json.dumps(payload))
            )

    def update_client_seen(self, client_id: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE clients SET last_seen_at = datetime('now') WHERE client_id = ?",
                (client_id,)
            )

    def list_commands(self) -> list:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                'SELECT cmd, profile_id, version, enabled FROM commands ORDER BY cmd'
            )
            return [{'cmd': r[0], 'profile_id': r[1], 'version': r[2], 'enabled': bool(r[3])}
                    for r in cursor.fetchall()]

    def get_recent_runs(self, limit: int = 20) -> list:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                '''SELECT run_id, cmd, status, started_at, ended_at, error
                   FROM runs ORDER BY started_at DESC LIMIT ?''',
                (limit,)
            )
            return [{'run_id': r[0], 'cmd': r[1], 'status': r[2],
                     'started_at': r[3], 'ended_at': r[4], 'error': r[5]}
                    for r in cursor.fetchall()]


class UASCServer:
    """UASC command execution server."""

    def __init__(self, db_path: str = DB_PATH, profiles_dir: str = PROFILES_DIR) -> None:
        self.db = UASCDatabase(db_path)
        self.profiles_dir = profiles_dir
        self.authenticator = Authenticator(self.db.get_client)
        self.executor = ProfileExecutor()

    def execute_command(
        self,
        cmd: str,
        auth: AuthResult,
        inputs: Optional[dict] = None
    ) -> Tuple[dict, int]:
        command = self.db.get_command(cmd)
        if not command:
            return {'error': f'Unknown command: {cmd}'}, 404

        if not command['enabled']:
            return {'error': f'Command disabled: {cmd}'}, 403

        if not self.authenticator.check_permission(auth, command['allowed_roles']):
            return {'error': 'Permission denied'}, 403

        profile_path = os.path.join(
            self.profiles_dir,
            f"{command['profile_id']}.json"
        )
        if not os.path.exists(profile_path):
            return {'error': f"Profile not found: {command['profile_id']}"}, 500

        with open(profile_path) as f:
            profile = json.load(f)

        run_id = str(uuid.uuid4())
        self.db.create_run(
            run_id, cmd, command['profile_id'],
            command['version'], auth.client_id
        )

        try:
            result = self.executor.execute(profile, inputs or {})

            for idx, step in enumerate(result.steps):
                self.db.log_event(
                    run_id, idx, step.step_type,
                    step.status,
                    {'output': step.output, 'error': step.error, 'duration_ms': step.duration_ms}
                )

            self.db.complete_run(run_id, result.status, result.error)
            self.db.update_client_seen(auth.client_id)

            return {
                'run_id': run_id,
                'cmd': cmd,
                'status': result.status,
                'duration_ms': result.total_duration_ms,
                'steps': [
                    {
                        'name': s.name,
                        'status': s.status,
                        'duration_ms': s.duration_ms
                    }
                    for s in result.steps
                ],
                'outputs': result.outputs,
                'error': result.error
            }, 200 if result.status == 'success' else 500

        except Exception as e:
            self.db.complete_run(run_id, 'failed', str(e))
            return {'run_id': run_id, 'error': str(e)}, 500


# Global server instance
uasc_server: Optional[UASCServer] = None


class RequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for UASC API."""

    def do_POST(self) -> None:
        if self.path == '/exec':
            self._handle_exec()
        else:
            self._send_json({'error': 'Not found'}, 404)

    def do_GET(self) -> None:
        if self.path == '/commands':
            self._handle_list_commands()
        elif self.path == '/health':
            self._send_json({'status': 'ok', 'service': 'uasc-executor', 'port': DEFAULT_PORT}, 200)
        elif self.path == '/runs':
            self._handle_list_runs()
        else:
            self._send_json({'error': 'Not found'}, 404)

    def _handle_exec(self) -> None:
        client_id = self.headers.get('X-UASC-Client', '')
        timestamp = self.headers.get('X-UASC-Timestamp', '')
        signature = self.headers.get('X-UASC-Signature', '')

        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8') if content_length else ''

        auth = uasc_server.authenticator.authenticate(client_id, timestamp, signature, body)
        if not auth.valid:
            self._send_json({'error': auth.error}, 401)
            return

        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self._send_json({'error': 'Invalid JSON'}, 400)
            return

        cmd = data.get('cmd', '')
        if not cmd:
            self._send_json({'error': 'Missing cmd'}, 400)
            return

        inputs = {k: v for k, v in data.items() if k != 'cmd'}

        response, status = uasc_server.execute_command(cmd, auth, inputs)
        self._send_json(response, status)

    def _handle_list_commands(self) -> None:
        commands = uasc_server.db.list_commands()
        self._send_json({'commands': commands}, 200)

    def _handle_list_runs(self) -> None:
        runs = uasc_server.db.get_recent_runs()
        self._send_json({'runs': runs}, 200)

    def _send_json(self, data: dict, status: int) -> None:
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())

    def log_message(self, format: str, *args) -> None:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {args[0]}")


def main() -> None:
    global uasc_server

    import argparse
    parser = argparse.ArgumentParser(description='UASC Executor Service')
    parser.add_argument('--port', type=int, default=DEFAULT_PORT)
    parser.add_argument('--host', default=DEFAULT_HOST)
    args = parser.parse_args()

    uasc_server = UASCServer()

    print("=" * 60)
    print("  UASC Executor Service")
    print("=" * 60)
    print(f"\n  Listening on: http://{args.host}:{args.port}")
    print(f"  Database: {DB_PATH}")
    print(f"  Profiles: {PROFILES_DIR}")
    print(f"\n  Endpoints:")
    print(f"    POST /exec      - Execute a command")
    print(f"    GET  /commands   - List available commands")
    print(f"    GET  /runs       - Recent execution history")
    print(f"    GET  /health     - Health check")
    print(f"\n  Commands:")
    for cmd in uasc_server.db.list_commands():
        status = '[ON]' if cmd['enabled'] else '[OFF]'
        print(f"    {status} {cmd['cmd']} -> {cmd['profile_id']}")
    print()

    class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
        daemon_threads = True

    server = ThreadedHTTPServer((args.host, args.port), RequestHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == '__main__':
    main()
