"""FastAPI sidecar — Phase C surface, revived 2026-06-24.

The verification engine (verify/spatial/consensus/ReferenceLibrary) was complete
and tested all along; this module was the missing HTTP face + the missing caller
that left the service "retired". It is pure glue over `verify.verify()` and
`visual.ReferenceLibrary` — no new logic.

Run as: `python -m triangulation.api`  (needs the [api] extra: fastapi+uvicorn).
Port: 3074 (NOT 3010 — that collides with optogon). Cold-start works with zero
models; the visual (SigLIP-2) signal stays None until the [visual] extra is
installed, and `library_add` fails loudly rather than silently in that state.
"""

from __future__ import annotations

from . import config, visual
from .verify import verify as run_verify  # submodule import: avoids __init__ re-export shadowing


def _load_library() -> visual.ReferenceLibrary:
    """Load the persisted reference library, or an empty one on cold start."""
    p = config.LIBRARY_PERSIST_PATH
    if p.is_file():
        try:
            return visual.ReferenceLibrary.load(p)
        except Exception:
            return visual.ReferenceLibrary()
    return visual.ReferenceLibrary()


def verify_endpoint(elements: list[dict]) -> list[dict]:
    """Run the triangulation pipeline over `elements`, return serialized verdicts.

    Cold-start (no populated library / no [visual] extra) cleanly skips the visual
    signal — the DOM + spatial + consensus path still produces verdicts.
    """
    library = _load_library()
    results = run_verify(elements, embedder=None, library=library)
    return [r.to_dict() for r in results]


def library_stats() -> dict[str, int]:
    """`{label: count}` for the persisted visual reference library (pure; no model)."""
    return _load_library().stats()


def library_add(label: str, screenshot_path: str) -> dict:
    """Add a labeled reference screenshot to the visual library.

    Requires the [visual] extra (SigLIP-2) to embed the image. Without it this
    fails honestly with `ok: False` rather than pretending — no broken furniture.
    """
    try:
        emb = visual.Embedder().embed(screenshot_path)
    except NotImplementedError as e:
        return {"ok": False, "error": "visual extra not installed", "detail": str(e)}
    library = _load_library()
    library.add(label, emb)
    library.persist(config.LIBRARY_PERSIST_PATH)
    return {"ok": True, "label": label, "stats": library.stats()}


# ---- HTTP surface (optional import: core package works without fastapi) --------
try:
    from fastapi import Body, FastAPI, HTTPException

    app = FastAPI(title="triangulation", version=config.VERSION)

    @app.get("/healthz")
    def healthz() -> dict:
        """Liveness + whether the visual signal is available (public read)."""
        return {
            "status": "ok",
            "service": "triangulation",
            "version": config.VERSION,
            "visual_available": False,  # True once the [visual] extra is wired
            "library": library_stats(),
        }

    @app.post("/verify")
    def post_verify(elements: list[dict] = Body(..., embed=True)) -> dict:
        """Verify auto-labeled UI elements via DOM + spatial + (optional) visual."""
        return {"count": len(elements), "results": verify_endpoint(elements)}

    @app.get("/library/stats")
    def get_library_stats() -> dict:
        return {"stats": library_stats()}

    @app.post("/library/add")
    def post_library_add(
        label: str = Body(..., embed=True),
        screenshot_path: str = Body(..., embed=True),
    ) -> dict:
        result = library_add(label, screenshot_path)
        if not result.get("ok"):
            # 503: the endpoint exists and is correct, but the visual extra isn't installed.
            raise HTTPException(503, result.get("error", "library add unavailable"))
        return result

except ImportError:  # pragma: no cover — fastapi is the [api] extra
    app = None  # type: ignore[assignment]


def run() -> None:
    """Console entry point — serve on 127.0.0.1:3074."""
    import uvicorn

    uvicorn.run("triangulation.api:app", host="127.0.0.1", port=config.API_DEFAULT_PORT, reload=False)


if __name__ == "__main__":  # pragma: no cover
    run()
