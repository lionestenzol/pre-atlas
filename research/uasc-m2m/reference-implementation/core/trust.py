"""
UASC-M2M Trust Verification Module

Handles the verification of authority chains and glyph binding signatures.
Ensures that only authorized glyphs from trusted authorities are executed.
"""

import hashlib
from dataclasses import dataclass
from typing import Optional, List, Tuple
from datetime import datetime


@dataclass
class Certificate:
    """
    Authority certificate.

    Represents the cryptographic identity of an authority
    and its authorization to issue glyph bindings.
    """
    authority_id: int
    domain: int
    name: str
    public_key: str
    valid_from: datetime
    valid_until: datetime
    issuer_id: int
    signature: str

    def is_valid(self) -> bool:
        """Check if certificate is currently valid."""
        now = datetime.utcnow()
        return self.valid_from <= now <= self.valid_until

    def is_expired(self) -> bool:
        """Check if certificate has expired."""
        return datetime.utcnow() > self.valid_until


@dataclass
class VerificationResult:
    """Result of trust verification."""
    valid: bool
    reason: str = ""
    authority_name: str = ""
    chain_length: int = 0


class TrustVerifier:
    """
    Verify glyph trust chain.

    Ensures that:
    1. The authority is certified by a domain authority
    2. The domain authority is certified by root
    3. The glyph binding is signed by the authority
    4. All certificates are valid and not expired
    """

    def __init__(self, root_public_key: str = "ROOT_PUBLIC_KEY"):
        self.root_key = root_public_key
        self.domain_certs: dict[int, Certificate] = {}
        self.authority_certs: dict[Tuple[int, int], Certificate] = {}
        self.revoked_authorities: set[Tuple[int, int]] = set()

    def add_domain_certificate(self, cert: Certificate):
        """Add a domain authority certificate."""
        self.domain_certs[cert.domain] = cert

    def add_authority_certificate(self, cert: Certificate):
        """Add a local authority certificate."""
        key = (cert.domain, cert.authority_id)
        self.authority_certs[key] = cert

    def revoke_authority(self, domain: int, authority_id: int):
        """Revoke an authority's certification."""
        self.revoked_authorities.add((domain, authority_id))

    def get_authority_chain(self, domain: int, authority: int) -> List[Certificate]:
        """
        Get the certificate chain for an authority.

        Returns: [local_cert, domain_cert] (root is implicit)
        """
        chain = []

        # Get local authority cert
        local_cert = self.authority_certs.get((domain, authority))
        if local_cert:
            chain.append(local_cert)

        # Get domain cert
        domain_cert = self.domain_certs.get(domain)
        if domain_cert:
            chain.append(domain_cert)

        return chain

    def verify(
        self,
        domain: int,
        authority: int,
        binding_signature: str
    ) -> VerificationResult:
        """
        Verify the trust chain for a glyph.

        Checks:
        1. Authority exists and is certified
        2. Authority is not revoked
        3. All certificates are valid
        4. Binding signature is present
        """

        # Check if authority is revoked
        if (domain, authority) in self.revoked_authorities:
            return VerificationResult(
                valid=False,
                reason="Authority has been revoked"
            )

        # Step 1: Get authority certificate
        auth_cert = self.authority_certs.get((domain, authority))
        if not auth_cert:
            return VerificationResult(
                valid=False,
                reason=f"Unknown authority: domain={domain}, authority={authority}"
            )

        if not auth_cert.is_valid():
            if auth_cert.is_expired():
                return VerificationResult(
                    valid=False,
                    reason="Authority certificate expired"
                )
            return VerificationResult(
                valid=False,
                reason="Authority certificate not yet valid"
            )

        # Step 2: Get domain certificate
        domain_cert = self.domain_certs.get(domain)
        if not domain_cert:
            return VerificationResult(
                valid=False,
                reason=f"Unknown domain: {domain}"
            )

        if not domain_cert.is_valid():
            return VerificationResult(
                valid=False,
                reason="Domain certificate expired or not valid"
            )

        # Step 3: Verify authority cert was issued by domain
        if auth_cert.issuer_id != domain_cert.authority_id:
            return VerificationResult(
                valid=False,
                reason="Authority not certified by domain authority"
            )

        # Step 4: Verify domain cert was issued by root (issuer_id = 0)
        if domain_cert.issuer_id != 0:
            return VerificationResult(
                valid=False,
                reason="Domain not certified by root authority"
            )

        # Step 5: Verify binding has a signature
        if not binding_signature:
            return VerificationResult(
                valid=False,
                reason="Glyph binding signature missing"
            )

        # In production, would verify actual cryptographic signatures here

        return VerificationResult(
            valid=True,
            reason="Trust chain verified",
            authority_name=auth_cert.name,
            chain_length=2
        )

    def verify_signature(
        self,
        data: bytes,
        signature: str,
        public_key: str
    ) -> bool:
        """
        Verify a cryptographic signature.

        In production, this would use proper cryptographic verification.
        This is a placeholder that always returns True.
        """
        # Placeholder - in production use proper crypto
        return True


def create_mock_trust_chain(
    domain: int,
    authority: int,
    authority_name: str
) -> TrustVerifier:
    """
    Create a mock trust chain for testing.

    Sets up:
    - Root authority (implicit)
    - Domain authority certificate
    - Local authority certificate
    """
    verifier = TrustVerifier()

    # Create domain certificate
    domain_names = {
        0x1: "International Smart City Consortium",
        0x2: "International Aerospace Authority",
        0x3: "International Maritime Organization",
        0x4: "Allied Defense Authority",
        0x5: "Global Medical AI Consortium"
    }

    domain_cert = Certificate(
        authority_id=0,
        domain=domain,
        name=domain_names.get(domain, f"Domain {domain} Authority"),
        public_key="DOMAIN_PUBLIC_KEY_PLACEHOLDER",
        valid_from=datetime(2024, 1, 1),
        valid_until=datetime(2030, 12, 31),
        issuer_id=0,  # Issued by root
        signature="ROOT_SIGNATURE_PLACEHOLDER"
    )
    verifier.add_domain_certificate(domain_cert)

    # Create local authority certificate
    auth_cert = Certificate(
        authority_id=authority,
        domain=domain,
        name=authority_name,
        public_key="AUTHORITY_PUBLIC_KEY_PLACEHOLDER",
        valid_from=datetime(2024, 1, 1),
        valid_until=datetime(2028, 12, 31),
        issuer_id=0,  # Issued by domain authority (id=0 within domain)
        signature="DOMAIN_SIGNATURE_PLACEHOLDER"
    )
    verifier.add_authority_certificate(auth_cert)

    return verifier
