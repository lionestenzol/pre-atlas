"""Code module memory store — port of conversation #557 "Phase 3 AI
System" (2025-02-02), Pre Atlas harvest pipeline.

The source thread built a multi-agent PHP pipeline (planner, code
generator, refinement, memory, testing agents) that, by the thread's
own end, was verified working end-to-end ("Every single agent is now
Working!"). The agents' own source was never fully captured in the
harvest (only bash invocations and interactive dotenv/Composer fixes),
but one concrete data structure recurs dozens of times throughout the
conversation and is fully specified: a `memory.json` file storing named
code modules as `{"modules": {name: {"code": <base64>}}}`, read by the
refinement agent and written to after each refinement pass. This ports
that store as a small, real module, since it's the one piece of the
pipeline actually nailed down rather than described in prose.
"""
import base64
import json
import os


def load_store(path):
    if not os.path.exists(path):
        return {"modules": {}}
    with open(path, "r") as f:
        return json.load(f)


def save_store(path, store):
    with open(path, "w") as f:
        json.dump(store, f, indent=2)


def save_module(path, name, source_code):
    store = load_store(path)
    store["modules"][name] = {"code": base64.b64encode(source_code.encode()).decode()}
    save_store(path, store)


def load_module(path, name):
    store = load_store(path)
    module = store["modules"].get(name)
    if module is None:
        raise KeyError(f"module {name!r} not found in {path}")
    return base64.b64decode(module["code"]).decode()


def list_modules(path):
    return list(load_store(path)["modules"].keys())
