"""
UASC-M2M MVP Authentication Module

HMAC-SHA256 signature verification for secure command execution.
"""

import hmac
import hashlib
import time
from dataclasses import dataclass
from typing import Optional, Tuple


# Maximum age of a request in seconds (replay protection)
MAX_TIMESTAMP_AGE = 60


@dataclass
class AuthResult:
    """Result of authentication check."""
    valid: bool
    client_id: Optional[str] = None
    roles: list = None
    error: Optional[str] = None

    def __post_init__(self):
        if self.roles is None:
            self.roles = []


def compute_signature(secret: str, timestamp: str, body: str) -> str:
    """
    Compute HMAC-SHA256 signature.

    Args:
        secret: Shared secret key
        timestamp: Unix timestamp as string
        body: Request body (JSON string)

    Returns:
        Hex-encoded signature
    """
    message = f"{timestamp}{body}".encode('utf-8')
    signature = hmac.new(
        secret.encode('utf-8'),
        message,
        hashlib.sha256
    ).hexdigest()
    return signature


def verify_signature(
    secret: str,
    timestamp: str,
    body: str,
    provided_signature: str
) -> bool:
    """
    Verify HMAC-SHA256 signature.

    Args:
        secret: Shared secret key
        timestamp: Unix timestamp from request
        body: Request body
        provided_signature: Signature from request header

    Returns:
        True if signature is valid
    """
    expected = compute_signature(secret, timestamp, body)
    return hmac.compare_digest(expected, provided_signature)


def verify_timestamp(timestamp: str, max_age: int = MAX_TIMESTAMP_AGE) -> Tuple[bool, str]:
    """
    Verify timestamp is recent (replay protection).

    Args:
        timestamp: Unix timestamp as string
        max_age: Maximum age in seconds

    Returns:
        (is_valid, error_message)
    """
    try:
        ts = int(timestamp)
    except (ValueError, TypeError):
        return False, "Invalid timestamp format"

    now = int(time.time())
    age = abs(now - ts)

    if age > max_age:
        return False, f"Timestamp too old: {age}s > {max_age}s"

    return True, ""


def hash_secret(secret: str) -> str:
    """Hash a secret for storage."""
    return hashlib.sha256(secret.encode('utf-8')).hexdigest()


class Authenticator:
    """
    HMAC-based request authenticator.

    Headers required:
        X-UASC-Client: client_id
        X-UASC-Timestamp: unix_timestamp
        X-UASC-Signature: hmac_sha256_hex
    """

    def __init__(self, get_client_func):
        """
        Args:
            get_client_func: Function(client_id) -> (secret_hash, roles, enabled)
        """
        self.get_client = get_client_func

    def authenticate(
        self,
        client_id: str,
        timestamp: str,
        signature: str,
        body: str
    ) -> AuthResult:
        """
        Authenticate a request.

        Args:
            client_id: Client identifier from header
            timestamp: Unix timestamp from header
            signature: HMAC signature from header
            body: Request body

        Returns:
            AuthResult with validation status
        """
        # Check client_id
        if not client_id:
            return AuthResult(valid=False, error="Missing client ID")

        # Check timestamp
        ts_valid, ts_error = verify_timestamp(timestamp)
        if not ts_valid:
            return AuthResult(valid=False, error=ts_error)

        # Get client info
        client_info = self.get_client(client_id)
        if not client_info:
            return AuthResult(valid=False, error="Unknown client")

        secret_hash, roles, enabled = client_info

        # Check if client is enabled
        if not enabled:
            return AuthResult(valid=False, error="Client disabled")

        # For MVP: We store the secret directly (not hash) for simplicity
        # In production, you'd use a proper key derivation
        secret = secret_hash  # In MVP, this IS the secret

        # Verify signature
        if not verify_signature(secret, timestamp, body, signature):
            return AuthResult(valid=False, error="Invalid signature")

        return AuthResult(
            valid=True,
            client_id=client_id,
            roles=roles.split(',') if isinstance(roles, str) else roles
        )

    def check_permission(self, auth_result: AuthResult, required_roles: list) -> bool:
        """
        Check if authenticated client has required role.

        Args:
            auth_result: Result from authenticate()
            required_roles: List of roles that can access (or ['*'] for any)

        Returns:
            True if client has permission
        """
        if not auth_result.valid:
            return False

        # Wildcard allows any authenticated client
        if '*' in required_roles:
            return True

        # Admin role has access to everything
        if 'admin' in auth_result.roles:
            return True

        # Check for role intersection
        return bool(set(auth_result.roles) & set(required_roles))


# Convenience function for generating client credentials
def generate_credentials(client_id: str) -> dict:
    """
    Generate new client credentials.

    Returns:
        {
            'client_id': str,
            'secret': str (keep this safe!),
            'secret_hash': str (store this)
        }
    """
    import secrets
    secret = secrets.token_urlsafe(32)
    return {
        'client_id': client_id,
        'secret': secret,
        'secret_hash': hash_secret(secret)
    }


if __name__ == '__main__':
    # Demo: Generate credentials and test signing
    print("=== UASC-M2M Auth Demo ===\n")

    # Generate credentials
    creds = generate_credentials('test-client')
    print(f"Client ID: {creds['client_id']}")
    print(f"Secret: {creds['secret']}")
    print(f"Secret Hash: {creds['secret_hash']}")

    # Test signing
    timestamp = str(int(time.time()))
    body = '{"cmd": "@WORK"}'
    signature = compute_signature(creds['secret'], timestamp, body)

    print(f"\nTimestamp: {timestamp}")
    print(f"Body: {body}")
    print(f"Signature: {signature}")

    # Verify
    is_valid = verify_signature(creds['secret'], timestamp, body, signature)
    print(f"\nVerification: {'PASS' if is_valid else 'FAIL'}")
