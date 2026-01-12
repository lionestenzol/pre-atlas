"""
UASC-M2M Registry Module

The registry stores execution graphs and their bindings to glyphs.
This is the authoritative source for what a glyph means and does.
"""

import json
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta


@dataclass
class ExecutionGraph:
    """
    Represents an execution graph - the deterministic logic
    that a glyph invokes when executed.
    """
    graph_id: str
    name: str
    version: str
    domain: str
    inputs: List[Dict[str, Any]]
    outputs: List[Dict[str, Any]]
    nodes: Dict[str, Dict[str, Any]]
    error_handling: Dict[str, Any] = field(default_factory=dict)
    constraints: Dict[str, Any] = field(default_factory=dict)

    @property
    def checksum(self) -> str:
        """Compute integrity checksum of the graph."""
        content = json.dumps({
            'graph_id': self.graph_id,
            'version': self.version,
            'nodes': self.nodes
        }, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def validate(self) -> List[str]:
        """Validate graph structure. Returns list of errors."""
        errors = []

        # Check for start node
        if 'start' not in self.nodes:
            errors.append("Missing 'start' node")

        # Check all node references are valid
        for node_id, node in self.nodes.items():
            for ref_key in ['next', 'on_true', 'on_false']:
                if ref_key in node:
                    ref_target = node[ref_key]
                    if ref_target not in self.nodes:
                        errors.append(f"Node '{node_id}' references unknown node '{ref_target}'")

        # Check for at least one exit node
        has_exit = any(n.get('type') == 'exit' for n in self.nodes.values())
        if not has_exit:
            errors.append("No exit node defined")

        return errors


@dataclass
class GlyphBinding:
    """
    Binding between a glyph code and an execution graph.
    This is the authority-signed link that gives a glyph its meaning.
    """
    glyph_code: int
    graph_id: str
    authority: int
    valid_from: datetime
    valid_until: datetime
    signature: str = ""

    def is_valid(self) -> bool:
        """Check if binding is currently valid."""
        now = datetime.utcnow()
        return self.valid_from <= now <= self.valid_until


@dataclass
class Registry:
    """
    In-memory UASC registry.

    In production, this would be a distributed, replicated data store
    with cryptographic verification and access control.
    """
    registry_id: str
    domain: int
    authority: int
    graphs: Dict[str, ExecutionGraph] = field(default_factory=dict)
    bindings: Dict[int, GlyphBinding] = field(default_factory=dict)
    revocations: List[int] = field(default_factory=list)

    def register_graph(self, graph: ExecutionGraph) -> str:
        """
        Register an execution graph.

        Returns the graph_id on success.
        """
        # Validate graph
        errors = graph.validate()
        if errors:
            raise ValueError(f"Invalid graph: {errors}")

        self.graphs[graph.graph_id] = graph
        return graph.graph_id

    def bind_glyph(
        self,
        glyph_code: int,
        graph_id: str,
        validity_days: int = 365
    ) -> GlyphBinding:
        """
        Bind a glyph code to an execution graph.

        This creates the official link between a symbolic glyph
        and the execution logic it invokes.
        """
        if graph_id not in self.graphs:
            raise ValueError(f"Graph '{graph_id}' not found in registry")

        # Check glyph is in valid range for this authority
        if not (0x8000 <= glyph_code <= 0xFFFE):
            raise ValueError(f"Glyph code 0x{glyph_code:04X} outside valid range")

        binding = GlyphBinding(
            glyph_code=glyph_code,
            graph_id=graph_id,
            authority=self.authority,
            valid_from=datetime.utcnow(),
            valid_until=datetime.utcnow() + timedelta(days=validity_days),
            signature=self._sign_binding(glyph_code, graph_id)
        )

        self.bindings[glyph_code] = binding
        return binding

    def lookup(self, glyph_code: int) -> Optional[ExecutionGraph]:
        """
        Lookup execution graph for a glyph.

        Returns None if:
        - Glyph is not bound
        - Binding is expired
        - Glyph is revoked
        """
        # Check revocation list
        if glyph_code in self.revocations:
            return None

        # Get binding
        binding = self.bindings.get(glyph_code)
        if not binding:
            return None

        # Check validity
        if not binding.is_valid():
            return None

        # Return graph
        return self.graphs.get(binding.graph_id)

    def get_binding(self, glyph_code: int) -> Optional[GlyphBinding]:
        """Get binding for a glyph code."""
        return self.bindings.get(glyph_code)

    def revoke(self, glyph_code: int, reason: str = ""):
        """
        Revoke a glyph binding.

        Revoked glyphs will no longer execute.
        """
        if glyph_code not in self.bindings:
            raise ValueError(f"No binding for glyph 0x{glyph_code:04X}")

        self.revocations.append(glyph_code)
        # In production, would also log revocation with timestamp and reason

    def is_revoked(self, glyph_code: int) -> bool:
        """Check if a glyph is revoked."""
        return glyph_code in self.revocations

    def _sign_binding(self, glyph_code: int, graph_id: str) -> str:
        """
        Generate signature for binding.

        In production, this would use proper cryptographic signing
        with the authority's private key.
        """
        content = f"{self.registry_id}:{glyph_code}:{graph_id}:{self.authority}"
        return hashlib.sha256(content.encode()).hexdigest()[:32]

    def export_bindings(self) -> Dict[str, Any]:
        """Export all bindings for synchronization."""
        return {
            'registry_id': self.registry_id,
            'domain': self.domain,
            'authority': self.authority,
            'bindings': [
                {
                    'glyph_code': f"0x{b.glyph_code:04X}",
                    'graph_id': b.graph_id,
                    'valid_from': b.valid_from.isoformat(),
                    'valid_until': b.valid_until.isoformat()
                }
                for b in self.bindings.values()
            ],
            'revocations': [f"0x{r:04X}" for r in self.revocations]
        }


def load_graph_from_json(filepath: str) -> ExecutionGraph:
    """Load execution graph from JSON file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    return ExecutionGraph(
        graph_id=data['graph_id'],
        name=data['name'],
        version=data['version'],
        domain=data['domain'],
        inputs=data.get('inputs', []),
        outputs=data.get('outputs', []),
        nodes=data['nodes'],
        error_handling=data.get('error_handling', {}),
        constraints=data.get('constraints', {})
    )


def load_graph_from_dict(data: Dict[str, Any]) -> ExecutionGraph:
    """Load execution graph from dictionary."""
    return ExecutionGraph(
        graph_id=data['graph_id'],
        name=data['name'],
        version=data['version'],
        domain=data['domain'],
        inputs=data.get('inputs', []),
        outputs=data.get('outputs', []),
        nodes=data['nodes'],
        error_handling=data.get('error_handling', {}),
        constraints=data.get('constraints', {})
    )
