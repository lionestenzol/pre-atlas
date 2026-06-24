"""Headless, caller-scoped self-description of a surface — the "test form" model.

The idea (Bruke, 2026-06-24): every surface can describe *itself* — its state and
the actions available — without any visual UI, so a blind/deaf human, a CLI, a
screen reader, and an LLM agent all consume the SAME headless descriptor. Crucially
the descriptor is *scoped to who is asking*: like a standardized test where each
test-taker gets a different form, two callers asking the same surface "what can I
do?" receive different forms based on their access.

Two ideas fuse here:
  1. A blind human and an agent are the same consumer — both need the system to
     *narrate* itself, not *show* itself. Build for one, get the other free.
  2. Safety by need-to-know: the MORE critical a capability, the FEWER descriptors
     leak. A capability above your clearance is progressively stripped — full →
     locked (you see it exists) → redacted (you don't even know it's there, only a
     count). Internal hashes proving existence-without-disclosure are a later
     hardening (see TODO at end).

Self-description is declarative, echoing inPACT's "every feature describes itself":
each capability is fully declared once in a per-surface overlay file
(`services/<name>/atlas.surface.json`); this module only *filters* that declaration
per caller. Nothing here invents a description format — the projection logic is the
product; the affordance shape mirrors hypermedia (state + available actions).

This is layer 1 (self-description) of the capability-registry vision. It composes
on the same MapSnapshot the rest of atlas-map-api already loads.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

# Surface names index into the filesystem (services/apps/tools/<name>) — restrict to
# a safe charset so a caller-supplied name can never path-traverse out of its group.
_SAFE_SURFACE = re.compile(r"^[A-Za-z0-9_-]+$")

Direction = Literal["read", "write"]
Exposure = Literal["public", "agent", "internal"]

OVERLAY_FILENAME = "atlas.surface.json"

# A surface can live in any of these group dirs. Overlays are resolved by scanning
# all three so apps (UI affordances) and tools (CLI commands) self-describe too, not
# just HTTP services.
GROUP_DIRS = ("services", "apps", "tools")

# What KIND of surface this is — decides what `invoke` means and how it's verified:
#   http      -> invoke is "METHOD /path"; verify_overlays greps the route in source
#   cli       -> invoke is a shell command (e.g. "atlas where")
#   ui        -> invoke is a screen action/affordance (e.g. "click Add card")
#   websocket -> invoke is an event/channel
#   library   -> invoke is an import/function entry
SurfaceKind = Literal["http", "cli", "ui", "websocket", "library"]
# Lifecycle so the registry can say "don't build on this" instead of staying silent.
Lifecycle = Literal["live", "retired", "stub"]


# ---------------------------------------------------------------------------
# Roles — the "test-takers". Each role is a point in the 3-axis access model:
#   clearance  : how critical a capability it may fully see (0=routine .. 3=danger)
#   exposure   : which exposure classes it may see at all
#   directions : whether it may observe (read), mutate (write), or both
# Agents deliberately get LESS than the hands-on human operator (safety intent).
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Role:
    name: str
    clearance: int
    exposure: frozenset[str]
    directions: frozenset[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.name,
            "clearance": self.clearance,
            "exposure": sorted(self.exposure),
            "directions": sorted(self.directions),
        }


ROLES: dict[str, Role] = {
    "anon": Role("anon", 0, frozenset({"public"}), frozenset({"read"})),
    "agent-ro": Role("agent-ro", 1, frozenset({"public", "agent"}), frozenset({"read"})),
    "agent": Role("agent", 1, frozenset({"public", "agent"}), frozenset({"read", "write"})),
    "operator": Role("operator", 2, frozenset({"public", "agent", "internal"}), frozenset({"read", "write"})),
    "root": Role("root", 3, frozenset({"public", "agent", "internal"}), frozenset({"read", "write"})),
}

DEFAULT_ROLE = "anon"


def resolve_role(name: str | None) -> Role:
    """Map a caller-supplied role name to a Role, falling back to the least-privileged."""
    return ROLES.get((name or "").strip().lower(), ROLES[DEFAULT_ROLE])


def narrow_role(token_role: Role, requested: str | None) -> Role:
    """Return the LESS-privileged of the token's role and any requested role.

    The query param may only narrow, never escalate: a caller can ask to *preview*
    a lower form (e.g. a root operator viewing what an agent would see), but cannot
    ask for more than their token grants. Privilege is ranked by (clearance, breadth
    of exposure, breadth of directions) so no single axis can be used to climb.
    """
    if not requested:
        return token_role
    asked = resolve_role(requested)
    rank = lambda r: (r.clearance, len(r.exposure), len(r.directions))  # noqa: E731
    return asked if rank(asked) <= rank(token_role) else token_role


# Criticality at/above which a *fully redacted* capability emits an existence proof
# — an over-cleared auditor can verify completeness without a need-to-know leak.
PROOF_CRITICALITY = 2


def existence_hash(surface: str, cap_id: str, secret: str) -> str:
    """Stable, non-reversible proof that a capability exists, without disclosing it.

    HMAC keyed by a server secret so a caller cannot forge or precompute the hash
    for a guessed id; truncated for readability. Same (surface, id, secret) always
    yields the same value; the value never equals the id or its invoke string.
    """
    msg = f"{surface}:{cap_id}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()[:12]


# ---------------------------------------------------------------------------
# Capability — one self-declared affordance from a surface overlay file.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Capability:
    id: str
    label: str
    direction: Direction
    exposure: Exposure
    criticality: int  # 0 routine .. 3 dangerous
    invoke: str = ""  # how to call it (e.g. "POST /api/drop") — leaked only when full
    needs: tuple[str, ...] = field(default_factory=tuple)

    @staticmethod
    def from_dict(raw: dict[str, Any]) -> "Capability":
        return Capability(
            id=str(raw.get("id", "")).strip(),
            label=str(raw.get("label", "")).strip(),
            direction="write" if str(raw.get("direction", "read")) == "write" else "read",
            exposure=_coerce_exposure(raw.get("exposure")),
            criticality=max(0, min(3, int(raw.get("criticality", 0) or 0))),
            invoke=str(raw.get("invoke", "") or ""),
            needs=tuple(str(n) for n in (raw.get("needs", []) or [])),
        )


def _coerce_exposure(raw: Any) -> Exposure:
    v = str(raw or "internal").strip().lower()
    return v if v in ("public", "agent", "internal") else "internal"  # type: ignore[return-value]


@dataclass(frozen=True)
class SurfaceOverlay:
    surface: str
    headline: str
    capabilities: tuple[Capability, ...]
    kind: str = "http"
    lifecycle: str = "live"


def overlay_path(repo_root: Path, surface: str) -> Path:
    """Resolve a surface's overlay across services/apps/tools (first hit wins).

    Falls back to the services/ path when none exists yet (so callers have a
    canonical write location for a new service overlay).
    """
    for group in GROUP_DIRS:
        p = repo_root / group / surface / OVERLAY_FILENAME
        if p.is_file():
            return p
    return repo_root / "services" / surface / OVERLAY_FILENAME


def load_overlay(repo_root: Path, surface: str) -> SurfaceOverlay | None:
    """Read a surface's self-description overlay, or None if it hasn't declared one.

    Fail-soft: a malformed overlay yields None rather than crashing the gateway.
    A surface name that isn't a safe identifier (path-traversal attempt) yields None.
    """
    if not _SAFE_SURFACE.match(surface):
        return None
    p = overlay_path(repo_root, surface)
    if not p.is_file():
        return None
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    caps = tuple(
        Capability.from_dict(c)
        for c in (raw.get("capabilities", []) or [])
        if isinstance(c, dict) and str(c.get("id", "")).strip()
    )
    return SurfaceOverlay(
        surface=str(raw.get("surface", surface)),
        headline=str(raw.get("headline", "")),
        capabilities=caps,
        kind=str(raw.get("kind", "http") or "http"),
        lifecycle=str(raw.get("lifecycle", "live") or "live"),
    )


def described_surfaces(repo_root: Path) -> list[str]:
    """Every surface (service, app, or tool) that has declared an overlay."""
    out: list[str] = []
    for group in GROUP_DIRS:
        base = repo_root / group
        if not base.is_dir():
            continue
        out.extend(
            d.name for d in base.iterdir() if d.is_dir() and (d / OVERLAY_FILENAME).is_file()
        )
    return sorted(out)


# ---------------------------------------------------------------------------
# The projection — turn one overlay into ONE caller's form.
#
# Per capability, the redaction ladder (the "fewer descriptors when more critical"
# rule made concrete):
#   wrong exposure class for this role        -> redacted (counted, unnamed)
#   right exposure but wrong direction         -> redacted (counted, unnamed)
#   clearance >= criticality                   -> FULL  (label + invoke + needs)
#   clearance == criticality - 1               -> LOCKED (named, no invoke — one
#                                                  step away; signals an elevation path)
#   clearance <= criticality - 2               -> redacted (counted, unnamed)
# ---------------------------------------------------------------------------
def _full_field(cap: Capability) -> dict[str, Any]:
    out: dict[str, Any] = {
        "id": cap.id,
        "label": cap.label,
        "direction": cap.direction,
        "exposure": cap.exposure,
        "criticality": cap.criticality,
    }
    if cap.invoke:
        out["invoke"] = cap.invoke
    if cap.needs:
        out["needs"] = list(cap.needs)
    return out


def describe_surface(
    overlay: SurfaceOverlay, role: Role, secret: str | None = None
) -> dict[str, Any]:
    """Project a surface overlay into the single form THIS role receives.

    When `secret` is provided, every fully-redacted capability at criticality
    >= PROOF_CRITICALITY contributes an opaque existence hash to `redacted_proofs`
    — proof-of-existence without disclosure (the "internal hashes" hardening).
    """
    fields: list[dict[str, Any]] = []
    locked: list[dict[str, Any]] = []
    redacted_caps: list[Capability] = []

    for cap in overlay.capabilities:
        if cap.exposure not in role.exposure or cap.direction not in role.directions:
            redacted_caps.append(cap)
            continue
        gap = cap.criticality - role.clearance
        if gap <= 0:
            fields.append(_full_field(cap))
        elif gap == 1:
            locked.append({"id": cap.id, "label": cap.label, "reason": "needs higher clearance"})
        else:
            redacted_caps.append(cap)

    fields.sort(key=lambda f: (f["direction"], f["id"]))
    proofs = (
        sorted(
            existence_hash(overlay.surface, c.id, secret)
            for c in redacted_caps
            if c.criticality >= PROOF_CRITICALITY
        )
        if secret
        else []
    )
    return {
        "surface": overlay.surface,
        "form_id": f"{overlay.surface}@{role.name}",
        "headline": overlay.headline,
        "kind": overlay.kind,
        "lifecycle": overlay.lifecycle,
        "caller": role.to_dict(),
        "state": None,  # live-state slot (Wire 2): read the surface's status cap here
        "fields": fields,
        "locked": locked,
        "redacted": len(redacted_caps),
        "redacted_proofs": proofs,
        "totals": {"declared": len(overlay.capabilities), "visible": len(fields)},
    }


def render_text(form: dict[str, Any]) -> str:
    """Narrate a form as plain text — the channel a screen reader / TTS / CLI speaks.

    Same descriptor, non-visual render: this is what makes the surface operable by
    a blind human and an agent through the identical path.
    """
    lines = [f"{form['surface']} — {form['headline']}".rstrip(" —")]
    if form.get("lifecycle") in ("retired", "stub"):
        lines.append(f"⚠ This surface is {form['lifecycle']} — do not build on it.")
    lines.append(f"(your form: {form['form_id']})")
    if form["fields"]:
        lines.append("You can:")
        for f in form["fields"]:
            how = f" [{f['invoke']}]" if f.get("invoke") else ""
            lines.append(f"  - {f['label']}{how}")
    else:
        lines.append("You have no available actions at this access level.")
    if form["locked"]:
        lines.append("Locked (one clearance step away):")
        for item in form["locked"]:
            lines.append(f"  - {item['label']}")
    if form["redacted"]:
        lines.append(
            f"{form['redacted']} further capabilit"
            f"{'y is' if form['redacted'] == 1 else 'ies are'} hidden at your access level."
        )
    return "\n".join(lines)


# TODO (later hardening, per Bruke): for criticality>=2 redactions, emit an opaque
# existence hash — proof that a capability exists without disclosing what it is —
# so an over-cleared caller can verify completeness without a need-to-know leak.
