"""
TestClient smoke for FastAPI swap (2026-05-30 Session 3).

Pure dispatch parity — verifies URL paths, status codes, JSON body shapes,
HMAC ordering, and the CORS header land byte-identical to the prior
BaseHTTPRequestHandler. The database + auth crypto are mocked to keep the
smoke focused on the swap; auth.py and executor.py are untouched and have
their own coverage paths.

Run: pytest test_server_smoke.py -v
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

import server
from auth import AuthResult


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Build a TestClient with the global uasc_server replaced by a mock."""
    mock_db = MagicMock()
    mock_db.list_commands.return_value = [
        {'cmd': '@PING', 'profile_id': 'PING_v1', 'version': 1, 'enabled': True}
    ]
    mock_db.get_recent_runs.return_value = []

    def fake_authenticate(client_id: str, timestamp: str, signature: str, body: str) -> AuthResult:
        if not client_id:
            return AuthResult(valid=False, error="Missing client ID")
        if signature == "valid-sig":
            return AuthResult(valid=True, client_id=client_id, roles=['admin'])
        return AuthResult(valid=False, error="Invalid signature")

    mock_auth = MagicMock()
    mock_auth.authenticate.side_effect = fake_authenticate

    mock_server = MagicMock()
    mock_server.db = mock_db
    mock_server.authenticator = mock_auth
    mock_server.execute_command.return_value = (
        {
            'run_id': 'run-abc',
            'cmd': '@PING',
            'status': 'success',
            'duration_ms': 1,
            'steps': [],
            'outputs': {},
            'error': None,
        },
        200,
    )

    monkeypatch.setattr(server, 'uasc_server', mock_server)
    return TestClient(server.app)


# --- GET endpoints (no auth) -------------------------------------------------

def test_health_returns_legacy_body(client: TestClient) -> None:
    r = client.get('/health')
    assert r.status_code == 200
    assert r.json() == {'status': 'ok', 'service': 'uasc-executor', 'port': 3008}
    assert r.headers['access-control-allow-origin'] == '*'


def test_commands_returns_envelope(client: TestClient) -> None:
    r = client.get('/commands')
    assert r.status_code == 200
    body = r.json()
    assert 'commands' in body
    assert body['commands'][0]['cmd'] == '@PING'
    assert r.headers['access-control-allow-origin'] == '*'


def test_runs_returns_envelope(client: TestClient) -> None:
    r = client.get('/runs')
    assert r.status_code == 200
    assert r.json() == {'runs': []}
    assert r.headers['access-control-allow-origin'] == '*'


def test_unknown_path_returns_legacy_404(client: TestClient) -> None:
    r = client.get('/does-not-exist')
    assert r.status_code == 404
    assert r.json() == {'error': 'Not found'}
    assert r.headers['access-control-allow-origin'] == '*'


# --- POST /exec (HMAC gate) --------------------------------------------------

def test_exec_no_headers_returns_401_missing_client(client: TestClient) -> None:
    r = client.post('/exec', json={'cmd': '@PING'})
    assert r.status_code == 401
    assert r.json() == {'error': 'Missing client ID'}


def test_exec_bad_signature_returns_401_invalid_signature(client: TestClient) -> None:
    headers = {
        'X-UASC-Client': 'delta-kernel',
        'X-UASC-Timestamp': '0',
        'X-UASC-Signature': 'wrong',
    }
    r = client.post('/exec', json={'cmd': '@PING'}, headers=headers)
    assert r.status_code == 401
    assert r.json() == {'error': 'Invalid signature'}


def test_exec_valid_auth_but_malformed_body_returns_400_invalid_json(client: TestClient) -> None:
    headers = {
        'X-UASC-Client': 'delta-kernel',
        'X-UASC-Timestamp': '0',
        'X-UASC-Signature': 'valid-sig',
        'Content-Type': 'application/json',
    }
    r = client.post('/exec', content=b'{not valid json', headers=headers)
    assert r.status_code == 400
    assert r.json() == {'error': 'Invalid JSON'}


def test_exec_valid_auth_but_missing_cmd_returns_400_missing_cmd(client: TestClient) -> None:
    headers = {
        'X-UASC-Client': 'delta-kernel',
        'X-UASC-Timestamp': '0',
        'X-UASC-Signature': 'valid-sig',
    }
    r = client.post('/exec', json={}, headers=headers)
    assert r.status_code == 400
    assert r.json() == {'error': 'Missing cmd'}


def test_exec_happy_path_returns_run_envelope(client: TestClient) -> None:
    headers = {
        'X-UASC-Client': 'delta-kernel',
        'X-UASC-Timestamp': '0',
        'X-UASC-Signature': 'valid-sig',
    }
    r = client.post('/exec', json={'cmd': '@PING', 'extra': 'arg'}, headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body['run_id'] == 'run-abc'
    assert body['cmd'] == '@PING'
    assert body['status'] == 'success'
    assert 'steps' in body
    assert 'outputs' in body


def test_exec_inputs_split_from_cmd(client: TestClient) -> None:
    """`cmd` field is stripped from data before passing as inputs."""
    headers = {
        'X-UASC-Client': 'delta-kernel',
        'X-UASC-Timestamp': '0',
        'X-UASC-Signature': 'valid-sig',
    }
    r = client.post(
        '/exec',
        json={'cmd': '@PING', 'foo': 1, 'bar': 'two'},
        headers=headers,
    )
    assert r.status_code == 200
    # execute_command was called with cmd='@PING', auth=..., inputs={'foo': 1, 'bar': 'two'}
    call_args = server.uasc_server.execute_command.call_args
    assert call_args.args[0] == '@PING'
    assert call_args.args[2] == {'foo': 1, 'bar': 'two'}


def test_hmac_dependency_sees_raw_body(client: TestClient) -> None:
    """HMAC verification must see the exact body string the client sent (not parsed JSON)."""
    headers = {
        'X-UASC-Client': 'delta-kernel',
        'X-UASC-Timestamp': '1234',
        'X-UASC-Signature': 'valid-sig',
    }
    raw_body = b'{"cmd":"@PING","x":1}'
    r = client.post('/exec', content=raw_body, headers={**headers, 'Content-Type': 'application/json'})
    assert r.status_code == 200
    # authenticator.authenticate(client_id, timestamp, signature, body) — verify body parity
    auth_call = server.uasc_server.authenticator.authenticate.call_args
    assert auth_call.args[3] == raw_body.decode('utf-8')
