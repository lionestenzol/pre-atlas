"""
UASC-M2M Glyph Encoding/Decoding Module

Handles the encoding and decoding of UASC glyph frames for transmission
and interpretation by the execution engine.
"""

import struct
from dataclasses import dataclass
from typing import Optional, Dict, Any
from enum import IntEnum


class Domain(IntEnum):
    """UASC Domain identifiers (4-bit)."""
    RESERVED = 0x0
    SMART_CITY = 0x1
    AEROSPACE = 0x2
    MARITIME = 0x3
    MILITARY = 0x4
    MEDICAL = 0x5
    INDUSTRIAL = 0x6
    FINANCIAL = 0x7
    ENERGY = 0x8
    TRANSPORT = 0x9
    TELECOM = 0xA
    AGRICULTURE = 0xB
    CUSTOM = 0xF


# Glyph Token Mappings
# UASC tokens are machine-native symbolic opcodes, not tied to any human script.
# The format @XX, #NAME, or $XX provides compact, portable command addresses.
GLYPH_TOKENS = {
    0x8001: '@A1',      # Sequential execution
    0x8002: '@A2',      # Conditional check
    0x8003: '@C3',      # Control/Emergency priority
    0x8004: '@N4',      # Network/Zone optimization
    0x8005: '@X5',      # Transfer/Data operations
    0x8006: '@I6',      # AI/Intelligent processing
    0x8007: '@S7',      # Integrated system
}

# Human-readable aliases (optional, for logging/debugging)
GLYPH_NAMES = {
    0x8001: 'SEQ',
    0x8002: 'COND',
    0x8003: 'CTRL',
    0x8004: 'NET',
    0x8005: 'XFER',
    0x8006: 'AI',
    0x8007: 'SYS',
}


@dataclass
class GlyphFrame:
    """Represents a decoded UASC glyph frame."""
    domain: int
    authority: int
    glyph_code: int
    context: Optional[Dict[str, Any]] = None

    @property
    def full_address(self) -> str:
        """Return full glyph address as hex string."""
        return f"{self.domain:01X}.{self.authority:03X}.{self.glyph_code:04X}"

    def to_token(self) -> str:
        """Return the symbolic opcode token."""
        return GLYPH_TOKENS.get(self.glyph_code, f'@{self.glyph_code:04X}')

    def to_name(self) -> str:
        """Return human-readable name for logging."""
        return GLYPH_NAMES.get(self.glyph_code, f'G{self.glyph_code:04X}')

    def __repr__(self) -> str:
        return f"GlyphFrame({self.to_token()} @ {self.full_address})"


class GlyphCodec:
    """Encode and decode UASC glyph frames."""

    @staticmethod
    def encode(frame: GlyphFrame) -> bytes:
        """
        Encode glyph frame to binary format.

        Compact format (4 bytes):
            Byte 0: [DDDD][AAAA] - Domain (4 bits) + Authority high (4 bits)
            Byte 1: [AAAA AAAA] - Authority low (8 bits)
            Bytes 2-3: [GGGG GGGG GGGG GGGG] - Glyph code (16 bits)

        Extended format (8 bytes):
            Bytes 0-3: Compact format
            Bytes 4-7: Context data
        """
        packed = (frame.domain & 0xF) << 28
        packed |= (frame.authority & 0xFFF) << 16
        packed |= (frame.glyph_code & 0xFFFF)

        if frame.context:
            context_packed = GlyphCodec._encode_context(frame.context)
            return struct.pack('>II', packed, context_packed)
        return struct.pack('>I', packed)

    @staticmethod
    def decode(data: bytes) -> GlyphFrame:
        """Decode binary data to glyph frame."""
        if len(data) < 4:
            raise ValueError("Frame too short: minimum 4 bytes required")

        packed = struct.unpack('>I', data[:4])[0]

        frame = GlyphFrame(
            domain=(packed >> 28) & 0xF,
            authority=(packed >> 16) & 0xFFF,
            glyph_code=packed & 0xFFFF
        )

        if len(data) >= 8:
            context_packed = struct.unpack('>I', data[4:8])[0]
            frame.context = GlyphCodec._decode_context(context_packed)

        return frame

    @staticmethod
    def _encode_context(context: Dict[str, Any]) -> int:
        """
        Encode context dict to 32-bit integer.

        Format:
            Bits 24-31: zone (8 bits)
            Bits 16-23: priority (8 bits)
            Bits 8-15: mode (8 bits)
            Bits 0-7: reserved
        """
        packed = 0

        if 'zone' in context:
            packed |= (int(context['zone']) & 0xFF) << 24
        if 'priority' in context:
            packed |= (int(context['priority']) & 0xFF) << 16
        if 'mode' in context:
            modes = {'normal': 0, 'emergency': 1, 'maintenance': 2, 'test': 3}
            packed |= (modes.get(context['mode'], 0) & 0xFF) << 8

        return packed

    @staticmethod
    def _decode_context(packed: int) -> Dict[str, Any]:
        """Decode 32-bit integer to context dict."""
        modes = {0: 'normal', 1: 'emergency', 2: 'maintenance', 3: 'test'}
        return {
            'zone': (packed >> 24) & 0xFF,
            'priority': (packed >> 16) & 0xFF,
            'mode': modes.get((packed >> 8) & 0xFF, 'normal')
        }

    @staticmethod
    def to_text(frame: GlyphFrame) -> str:
        """
        Convert frame to text URI format.

        Format: UASC://{domain}.{authority}/{glyph}[?context]
        """
        domains = {v: k.lower() for k, v in Domain.__members__.items()}
        domain_name = domains.get(frame.domain, f"domain_{frame.domain}")
        authority_name = f"auth_{frame.authority:03X}"

        uri = f"UASC://{domain_name}.{authority_name}/{frame.to_token()}"

        if frame.context:
            params = "&".join(f"{k}={v}" for k, v in frame.context.items())
            uri += f"?{params}"

        return uri

    @staticmethod
    def from_text(uri: str) -> GlyphFrame:
        """Parse text URI format to glyph frame."""
        # Basic parsing - production would be more robust
        if not uri.startswith("UASC://"):
            raise ValueError("Invalid UASC URI format")

        # Remove protocol
        path = uri[7:]

        # Split path and query
        if '?' in path:
            path, query = path.split('?', 1)
        else:
            query = None

        # Parse path
        parts = path.split('/')
        if len(parts) != 2:
            raise ValueError("Invalid UASC URI path")

        domain_auth, glyph_char = parts

        # Parse domain.authority
        domain_str, auth_str = domain_auth.split('.')

        # Map domain name to code
        domain_map = {k.lower(): v for k, v in Domain.__members__.items()}
        domain = domain_map.get(domain_str, Domain.RESERVED)

        # Parse authority
        if auth_str.startswith("auth_"):
            authority = int(auth_str[5:], 16)
        else:
            authority = 0

        # Map glyph token to code
        token_to_code = {v: k for k, v in GLYPH_TOKENS.items()}
        glyph_code = token_to_code.get(glyph_char, 0xFFFF)

        # Parse context
        context = None
        if query:
            context = {}
            for param in query.split('&'):
                key, value = param.split('=')
                # Try to convert to int
                try:
                    context[key] = int(value)
                except ValueError:
                    context[key] = value

        return GlyphFrame(
            domain=domain,
            authority=authority,
            glyph_code=glyph_code,
            context=context
        )
