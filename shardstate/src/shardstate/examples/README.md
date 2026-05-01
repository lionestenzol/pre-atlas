# shardstate examples

Two runnable demos showing how agents coordinate through a shared shardstate.

## `llm_agent_demo.py` — two agents through a shared graph

Two agents (`ResearcherAgent` and `VerifierAgent`) coordinate by passing `Ref` values, not prose. The LLM call is mocked deterministically.

Run from the package root:

```bash
python -m shardstate.examples.llm_agent_demo
```

No extra dependencies. Output shows each handoff (the bytes actually transmitted are a JSON-encoded `Ref`), the final state hash, and the resolved entity values.

### What it does

1. The researcher takes a synthetic claim, calls `MockLLM.decide` to shape it into a fact entity, writes it via `store.put`, and emits a `Ref(state, node, op="verify")`.
2. The verifier resolves that `Ref`, calls `MockLLM.decide` against the resolved fact (with prior facts as context), and patches the entity with `verified` and `reason` fields.
3. The verifier emits a new `Ref` pointing at the post-patch state.

The full message between agents at each step is the `Ref` — roughly 80 bytes regardless of the underlying entity size.

## `mcp_client_demo.py` — talking to the MCP server

A minimal client showing how to call `put`, `get`, `patch`, `resolve` on the shardstate MCP server over stdio.

```bash
pip install 'shardstate[mcp]'
python -m shardstate.examples.mcp_client_demo
```

If `mcp` is not installed, the script prints an install hint and exits 0 (no crash). The MCP server is launched as a subprocess via `stdio_client`, with a fresh SQLite file in a temp directory.

## Swap the mock for a real local LLM

`MockLLM.decide` is a placeholder. The two-agent pattern works the same with any local model — only the body of `decide` changes.

### ollama

Make sure ollama is running (`ollama serve`) and you have a model pulled (`ollama pull llama3.1`).

```python
import json, urllib.request

class MockLLM:
    def decide(self, prompt, context):
        body = json.dumps({
            "model": "llama3.1",
            "prompt": f"{prompt}\nContext: {json.dumps(context)}\nRespond as JSON.",
            "stream": False,
        }).encode()
        req = urllib.request.Request(
            "http://localhost:11434/api/generate",
            data=body, headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req) as r:
            return json.loads(json.loads(r.read())["response"])
```

The five lines of the original `MockLLM.decide` body are replaced with the HTTP call.

### llama.cpp via llama-cpp-python

```python
from llama_cpp import Llama

class MockLLM:
    def __init__(self, model_path):
        self.llm = Llama(model_path=model_path)
    def decide(self, prompt, context):
        full = f"{prompt}\nContext: {json.dumps(context)}\nRespond as JSON."
        out = self.llm.create_completion(full, max_tokens=256)
        return json.loads(out["choices"][0]["text"])
```

Same shape: in, out is parsed JSON.

In both cases, the agents (`ResearcherAgent`, `VerifierAgent`) and the shardstate plumbing don't change. The graph and the `Ref` wire format are independent of the model.

## What this demo proves and doesn't

It proves the plumbing connects: two distinct agent objects coordinate through a shared store, the LLM-shaped boundary is mockable, the wire format between them is a tiny coordinate (`Ref`), and the final state is reproducible by hash.

It does **not** prove that real edge LLMs use `Ref` values intelligently — i.e. that they reliably emit valid refs, resolve them when needed, and avoid restating context they could reference. That's a downstream evaluation: run a real local model on real handoffs and measure (a) token counts before/after refs, (b) drift on shared entities, (c) whether the verifier catches contradictions when the researcher writes them.
