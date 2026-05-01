"""Two-agent demo: a researcher writes facts, a verifier checks them.

Coordination happens through Refs into a shared shardstate, not through prose.
The LLM is mocked deterministically so the demo runs without network.

Run: python -m shardstate.examples.llm_agent_demo
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from shardstate import Ref, Store


class MockLLM:
    """Deterministic stand-in for a local edge LLM.

    Replace `decide` with a real call to ollama or llama.cpp; see README.
    """

    def decide(self, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        role = context.get("role", "")
        if role == "researcher":
            claim = context.get("claim", "")
            return {
                "claim": claim,
                "confidence": 0.5 + (len(claim) % 7) / 20.0,
                "source": context.get("source", "synthetic"),
            }
        if role == "verifier":
            fact = context.get("fact", {})
            prior = context.get("prior_facts", [])
            claim = fact.get("claim", "")
            contradicted = any(
                p.get("claim", "").lower() == f"not {claim.lower()}" for p in prior
            )
            verified = (not contradicted) and fact.get("confidence", 0) >= 0.5
            reason = (
                "contradicts prior fact" if contradicted
                else ("low confidence" if not verified else "consistent with prior state")
            )
            return {"verified": verified, "reason": reason}
        return {"decision": "noop"}


@dataclass
class ResearcherAgent:
    store: Store
    llm: MockLLM

    def observe(self, claim: str, source: str = "synthetic") -> Ref:
        decision = self.llm.decide(
            prompt="Produce a fact entity from this claim.",
            context={"role": "researcher", "claim": claim, "source": source},
        )
        node = self.store.put({
            "type": "fact",
            "claim": decision["claim"],
            "confidence": decision["confidence"],
            "source": decision["source"],
            "verified": None,
            "reason": None,
        })
        head = self.store.head()
        assert head is not None
        return Ref(state=head.hash, node=node.id, op="verify")


@dataclass
class VerifierAgent:
    store: Store
    llm: MockLLM

    def verify(self, ref: Ref) -> Ref:
        fact = self.store.resolve(ref)
        prior = self._prior_facts(exclude_id=ref.node)
        decision = self.llm.decide(
            prompt="Is this fact consistent with prior state?",
            context={"role": "verifier", "fact": fact, "prior_facts": prior},
        )
        new_state = self.store.patch(ref.node, {
            "verified": decision["verified"],
            "reason": decision["reason"],
        })
        return Ref(state=new_state.hash, node=ref.node, op="verified")

    def _prior_facts(self, exclude_id: str) -> List[Dict[str, Any]]:
        rows = self.store._conn.execute(
            "SELECT stable_id FROM entities WHERE stable_id != ?", (exclude_id,)
        ).fetchall()
        out: List[Dict[str, Any]] = []
        for (sid,) in rows:
            v = self.store.get(sid)
            if isinstance(v, dict) and v.get("type") == "fact":
                out.append(v)
        return out


def _print_handoff(label: str, ref: Ref) -> None:
    print(f"[{label}] ref bytes-on-the-wire: {json.dumps(ref.to_dict())}")


def main(db_dir: Optional[str] = None) -> Dict[str, Any]:
    cleanup = False
    if db_dir is None:
        db_dir = tempfile.mkdtemp(prefix="shardstate_demo_")
        cleanup = True
    db_path = os.path.join(db_dir, "demo.db")

    store = Store(db_path, agent_id="agent_demo")
    llm = MockLLM()
    researcher = ResearcherAgent(store=store, llm=llm)
    verifier = VerifierAgent(store=store, llm=llm)

    claims = [
        "the agreement uses Net 30 terms",
        "the client signed on 2026-04-15",
        "the payment is overdue",
    ]
    final_refs: List[Ref] = []
    for claim in claims:
        ref_in = researcher.observe(claim)
        _print_handoff("researcher -> verifier", ref_in)
        ref_out = verifier.verify(ref_in)
        _print_handoff("verifier -> reader", ref_out)
        final_refs.append(ref_out)

    head = store.head()
    assert head is not None
    print(f"\nfinal state hash: {head.hash}")
    print("entity values:")
    final_values: Dict[str, Any] = {}
    for ref in final_refs:
        v = store.get(ref.node)
        final_values[ref.node] = v
        print(f"  {ref.node}: {json.dumps(v)}")

    result = {
        "state_hash": head.hash,
        "seq": head.seq,
        "entities": final_values,
        "db_path": db_path,
    }
    store.close()
    if cleanup:
        try:
            os.remove(db_path)
            os.rmdir(db_dir)
        except OSError:
            pass
    return result


if __name__ == "__main__":
    main()
