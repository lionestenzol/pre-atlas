#!/usr/bin/env python3
"""
UASC-M2M MVP Server

Single /exec endpoint that accepts command tokens and executes profiles.
"""

import json
import sqlite3
import os
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
from typing import Optional, Tuple

from auth import Authenticator, AuthResult
from executor import ProfileExecutor, ExecutionResult


# Configuration
DB_PATH = os.path.join(os.path.dirname(__file__), 'storage', 'registry.db')
PROFILES_DIR = os.path.join(os.path.dirname(__file__), 'profiles')
DEFAULT_PORT = 8420


class UASCDatabase:
    """SQLite database interface for UASC registry."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize database with schema."""
        schema_path = os.path.join(os.path.dirname(__file__), 'storage', 'schema.sql')

        # Create storage directory if needed
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            if os.path.exists(schema_path):
                with open(schema_path) as f:
                    conn.executescript(f.read())

    def get_client(self, client_id: str) -> Optional[Tuple[str, str, bool]]:
        """Get client info for authentication."""
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
        """Get command info from registry."""
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

    def create_run(self, run_id: str, cmd: str, profile_id: str, version: int, client_id: str):
        """Create a new run record."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                '''INSERT INTO runs (run_id, cmd, profile_id, version, client_id, status)
                   VALUES (?, ?, ?, ?, ?, 'running')''',
                (run_id, cmd, profile_id, version, client_id)
            )

    def complete_run(self, run_id: str, status: str, error: str = None):
        """Update run as completed."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                '''UPDATE runs SET status = ?, ended_at = datetime('now'), error = ?
                   WHERE run_id = ?''',
                (status, error, run_id)
            )

    def log_event(self, run_id: str, step_idx: int, step_type: str, event_type: str, payload: dict):
        """Log a run event."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                '''INSERT INTO run_events (run_id, step_idx, step_type, event_type, payload)
                   VALUES (?, ?, ?, ?, ?)''',
                (run_id, step_idx, step_type, event_type, json.dumps(payload))
            )

    def update_client_seen(self, client_id: str):
        """Update client last seen timestamp."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE clients SET last_seen_at = datetime('now') WHERE client_id = ?",
                (client_id,)
            )

    def add_client(self, client_id: str, name: str, secret: str, roles: str = 'user'):
        """Add a new client."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                '''INSERT OR REPLACE INTO clients (client_id, client_name, secret_hash, roles, enabled)
                   VALUES (?, ?, ?, ?, 1)''',
                (client_id, name, secret, roles)
            )

    def list_commands(self) -> list:
        """List all registered commands."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                'SELECT cmd, profile_id, version, enabled FROM commands ORDER BY cmd'
            )
            return [{'cmd': r[0], 'profile_id': r[1], 'version': r[2], 'enabled': bool(r[3])}
                    for r in cursor.fetchall()]


class UASCServer:
    """UASC command execution server."""

    def __init__(self, db_path: str = DB_PATH, profiles_dir: str = PROFILES_DIR):
        self.db = UASCDatabase(db_path)
        self.profiles_dir = profiles_dir
        self.authenticator = Authenticator(self.db.get_client)
        self.executor = ProfileExecutor()

    def execute_command(
        self,
        cmd: str,
        auth: AuthResult,
        inputs: dict = None
    ) -> Tuple[dict, int]:
        """
        Execute a command.

        Returns:
            (response_dict, http_status_code)
        """
        # Get command from registry
        command = self.db.get_command(cmd)
        if not command:
            return {'error': f'Unknown command: {cmd}'}, 404

        if not command['enabled']:
            return {'error': f'Command disabled: {cmd}'}, 403

        # Check permission
        if not self.authenticator.check_permission(auth, command['allowed_roles']):
            return {'error': 'Permission denied'}, 403

        # Load profile
        profile_path = os.path.join(
            self.profiles_dir,
            f"{command['profile_id']}.json"
        )
        if not os.path.exists(profile_path):
            return {'error': f"Profile not found: {command['profile_id']}"}, 500

        with open(profile_path) as f:
            profile = json.load(f)

        # Create run record
        run_id = str(uuid.uuid4())
        self.db.create_run(
            run_id, cmd, command['profile_id'],
            command['version'], auth.client_id
        )

        # Execute profile
        try:
            result = self.executor.execute(profile, inputs or {})

            # Log step events
            for idx, step in enumerate(result.steps):
                self.db.log_event(
                    run_id, idx, step.step_type,
                    step.status,
                    {'output': step.output, 'error': step.error, 'duration_ms': step.duration_ms}
                )

            # Complete run
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
uasc_server = None


class RequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for UASC API."""

    def do_POST(self):
        if self.path == '/exec':
            self._handle_exec()
        elif self.path == '/register':
            self._handle_register()
        else:
            self._send_json({'error': 'Not found'}, 404)

    def do_GET(self):
        if self.path == '/commands':
            self._handle_list_commands()
        elif self.path == '/health':
            self._send_json({'status': 'ok'}, 200)
        else:
            self._send_json({'error': 'Not found'}, 404)

    def _handle_exec(self):
        """Handle /exec endpoint."""
        # Get headers
        client_id = self.headers.get('X-UASC-Client', '')
        timestamp = self.headers.get('X-UASC-Timestamp', '')
        signature = self.headers.get('X-UASC-Signature', '')

        # Read body
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8') if content_length else ''

        # Authenticate
        auth = uasc_server.authenticator.authenticate(client_id, timestamp, signature, body)
        if not auth.valid:
            self._send_json({'error': auth.error}, 401)
            return

        # Parse request
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

        # Execute
        response, status = uasc_server.execute_command(cmd, auth, inputs)
        self._send_json(response, status)

    def _handle_list_commands(self):
        """Handle /commands endpoint."""
        commands = uasc_server.db.list_commands()
        self._send_json({'commands': commands}, 200)

    def _handle_register(self):
        """Handle /register endpoint (admin only, for adding clients)."""
        # Simple registration - in production, this would be more secure
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')

        try:
            data = json.loads(body)
            client_id = data.get('client_id')
            name = data.get('name', client_id)
            secret = data.get('secret')
            roles = data.get('roles', 'user')

            if not client_id or not secret:
                self._send_json({'error': 'Missing client_id or secret'}, 400)
                return

            uasc_server.db.add_client(client_id, name, secret, roles)
            self._send_json({'status': 'registered', 'client_id': client_id}, 200)

        except Exception as e:
            self._send_json({'error': str(e)}, 500)

    def _send_json(self, data: dict, status: int):
        """Send JSON response."""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())

    def log_message(self, format, *args):
        """Custom log format."""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {args[0]}")


def main():
    global uasc_server

    import argparse
    parser = argparse.ArgumentParser(description='UASC-M2M Server')
    parser.add_argument('--port', type=int, default=DEFAULT_PORT, help='Port to listen on')
    parser.add_argument('--host', default='localhost', help='Host to bind to')
    args = parser.parse_args()

    # Initialize server
    uasc_server = UASCServer()

    print("=" * 60)
    print("  UASC-M2M Server")
    print("=" * 60)
    print(f"\n  Listening on: http://{args.host}:{args.port}")
    print(f"  Database: {DB_PATH}")
    print(f"  Profiles: {PROFILES_DIR}")
    print(f"\n  Endpoints:")
    print(f"    POST /exec     - Execute a command")
    print(f"    GET  /commands - List available commands")
    print(f"    GET  /health   - Health check")
    print(f"\n  Commands registered:")
    for cmd in uasc_server.db.list_commands():
        status = '[ON]' if cmd['enabled'] else '[OFF]'
        print(f"    {status} {cmd['cmd']} -> {cmd['profile_id']}")
    print()

    # Start server
    server = HTTPServer((args.host, args.port), RequestHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == '__main__':
    main()
