"""
UASC Executor — HMAC-SHA256 Authentication

Verifies requests from delta-kernel and other authorized clients.
"""

import hmac
import hashlib
import time
from dataclasses import dataclass
from typing import Optional, Tuple, Callable

MAX_TIMESTAMP_AGE = 300  # 5 minutes (relaxed for local services)


@dataclass
class AuthResult:
    """Result of authentication check."""
    valid: bool
    client_id: Optional[str] = None
    roles: Optional[list] = None
    error: Optional[str] = None

    def __post_init__(self) -> None:
        if self.roles is None:
            self.roles = []


def compute_signature(secret: str, timestamp: str, body: str) -> str:
    message = f"{timestamp}{body}".encode('utf-8')
    return hmac.new(
        secret.encode('utf-8'),
        message,
        hashlib.sha256,
    ).hexdigest()


def verify_signature(secret: str, timestamp: str, body: str, provided_signature: str) -> bool:
    expected = compute_signature(secret, timestamp, body)
    return hmac.compare_digest(expected, provided_signature)


def verify_timestamp(timestamp: str, max_age: int = MAX_TIMESTAMP_AGE) -> Tuple[bool, str]:
    try:
        ts = int(timestamp)
    except (ValueError, TypeError):
        return False, "Invalid timestamp format"

    now = int(time.time())
    age = abs(now - ts)

    if age > max_age:
        return False, f"Timestamp too old: {age}s > {max_age}s"

    return True, ""


class Authenticator:
    """HMAC-based request authenticator."""

    def __init__(self, get_client_func: Callable[[str], Optional[Tuple[str, str, bool]]]) -> None:
        self.get_client = get_client_func

    def authenticate(
        self,
        client_id: str,
        timestamp: str,
        signature: str,
        body: str,
    ) -> AuthResult:
        if not client_id:
            return AuthResult(valid=False, error="Missing client ID")

        ts_valid, ts_error = verify_timestamp(timestamp)
        if not ts_valid:
            return AuthResult(valid=False, error=ts_error)

        client_info = self.get_client(client_id)
        if not client_info:
            return AuthResult(valid=False, error="Unknown client")

        secret_hash, roles, enabled = client_info

        if not enabled:
            return AuthResult(valid=False, error="Client disabled")

        secret = secret_hash

        if not verify_signature(secret, timestamp, body, signature):
            return AuthResult(valid=False, error="Invalid signature")

        return AuthResult(
            valid=True,
            client_id=client_id,
            roles=roles.split(',') if isinstance(roles, str) else roles,
        )

    def check_permission(self, auth_result: AuthResult, required_roles: list) -> bool:
        if not auth_result.valid:
            return False

        if '*' in required_roles:
            return True

        if 'admin' in (auth_result.roles or []):
            return True

        return bool(set(auth_result.roles or []) & set(required_roles))
