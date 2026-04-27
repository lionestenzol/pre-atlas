"""
shapes.py — catalog of fuzz HTML shapes.

Each shape is a pure function (rng, anchor_id) -> Fragment. Shapes are
built against the anatomy extension v0.3.5 cascade
(tools/anatomy-extension/content.js) so every "should_fire" shape targets
a specific named rule and every "should_filter" shape hits a specific filter.

Adding a shape: define the function, add it to SHAPE_REGISTRY under its
intent name. The intent name becomes the key in expected.json, so keep
it stable.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class Fragment:
    """One shape's contribution to a fuzz file."""
    html: str
    intent: str
    should_fire: bool
    anchor_id: str
    labels_produced: int = 1
    slop: int = 0


ShapeFn = Callable[[random.Random, str], Fragment]


# ------------------------------ helpers ------------------------------

_BUTTON_PHRASES = [
    "Submit order", "Save changes", "Send message", "Confirm",
    "Continue", "Finish setup", "Create account", "Add to cart",
]
_LINK_PHRASES = [
    "Read more", "View details", "Go to dashboard", "See pricing",
    "Open docs", "Contact sales", "Learn how it works",
]
_HEADINGS = [
    "Welcome back", "Today's summary", "Recent activity",
    "Pricing that scales", "How it works", "Featured products",
]
_CARD_BODIES = [
    "All your projects in one place — fast, searchable, and ready to ship.",
    "Track usage, billing, and team activity without switching tabs.",
    "Rebuild your stack with composable primitives.",
]


def _pick(rng: random.Random, pool: list[str]) -> str:
    return rng.choice(pool)


# ------------------------------ cascade-rule hits (should_fire=True) ------------------------------

def native_button(rng: random.Random, aid: str) -> Fragment:
    return Fragment(
        html=f'<button id="{aid}" type="button" style="padding:10px 18px">{_pick(rng, _BUTTON_PHRASES)}</button>',
        intent="native_button", should_fire=True, anchor_id=aid,
    )


def native_anchor_text(rng: random.Random, aid: str) -> Fragment:
    return Fragment(
        html=f'<a id="{aid}" href="#faux" style="padding:6px 10px;display:inline-block">{_pick(rng, _LINK_PHRASES)}</a>',
        intent="native_anchor_text", should_fire=True, anchor_id=aid,
    )


def native_input_text(rng: random.Random, aid: str) -> Fragment:
    return Fragment(
        html=f'<input id="{aid}" type="text" placeholder="Your email" style="padding:8px 12px;width:240px"/>',
        intent="native_input_text", should_fire=True, anchor_id=aid,
    )


def role_button_div(rng: random.Random, aid: str) -> Fragment:
    return Fragment(
        html=f'<div id="{aid}" role="button" tabindex="0" style="padding:12px 20px;display:inline-block">{_pick(rng, _BUTTON_PHRASES)}</div>',
        intent="role_button_div", should_fire=True, anchor_id=aid,
    )


def role_checkbox_div(rng: random.Random, aid: str) -> Fragment:
    return Fragment(
        html=(
            f'<div id="{aid}" role="checkbox" aria-checked="false" tabindex="0" '
            f'style="padding:8px 14px;display:inline-block">Remember me</div>'
        ),
        intent="role_checkbox_div", should_fire=True, anchor_id=aid,
    )


def onclick_div(rng: random.Random, aid: str) -> Fragment:
    return Fragment(
        html=f'<div id="{aid}" onclick="void 0" style="padding:10px 16px;display:inline-block">{_pick(rng, _BUTTON_PHRASES)}</div>',
        intent="onclick_div", should_fire=True, anchor_id=aid,
    )


def tabindex_div(rng: random.Random, aid: str) -> Fragment:
    return Fragment(
        html=f'<div id="{aid}" tabindex="0" style="padding:10px 16px;display:inline-block">Jump to section</div>',
        intent="tabindex_div", should_fire=True, anchor_id=aid,
    )


def cursor_pointer_div(rng: random.Random, aid: str) -> Fragment:
    return Fragment(
        html=f'<div id="{aid}" style="cursor:pointer;padding:10px 16px;display:inline-block">Expand panel</div>',
        intent="cursor_pointer_div", should_fire=True, anchor_id=aid,
    )


def label_wraps_input(rng: random.Random, aid: str) -> Fragment:
    return Fragment(
        html=(
            f'<label id="{aid}" style="display:inline-block;padding:6px">'
            f'Newsletter <input type="checkbox"/></label>'
        ),
        intent="label_wraps_input", should_fire=True, anchor_id=aid,
    )


def span_wraps_input(rng: random.Random, aid: str) -> Fragment:
    return Fragment(
        html=(
            f'<span id="{aid}" style="display:inline-block;padding:6px">'
            f'<input type="text" placeholder="Quantity" style="width:120px"/></span>'
        ),
        intent="span_wraps_input", should_fire=True, anchor_id=aid,
    )


def search_id_div(rng: random.Random, aid: str) -> Fragment:
    return Fragment(
        html=f'<div id="{aid}" data-testid="search-bar" style="padding:12px;width:280px;border:1px solid #ddd">Search products</div>',
        intent="search_id_div", should_fire=True, anchor_id=aid,
    )


def custom_element(rng: random.Random, aid: str) -> Fragment:
    return Fragment(
        html=f'<my-widget id="{aid}" style="display:inline-block;padding:14px;border:1px solid #888">Custom widget body</my-widget>',
        intent="custom_element", should_fire=True, anchor_id=aid,
    )


def card_styled(rng: random.Random, aid: str) -> Fragment:
    body = _pick(rng, _CARD_BODIES)
    return Fragment(
        html=(
            f'<div id="{aid}" style="border:1px solid #ccc;border-radius:8px;'
            f'box-shadow:0 2px 6px rgba(0,0,0,0.08);background:#fff;'
            f'padding:16px;width:320px;margin:10px 0">'
            f'<h3 style="margin:0 0 8px 0">{_pick(rng, _HEADINGS)}</h3>'
            f'<p style="margin:0">{body}</p></div>'
        ),
        intent="card_styled", should_fire=True, anchor_id=aid,
        slop=1,
    )


def heading_h1(rng: random.Random, aid: str) -> Fragment:
    return Fragment(
        html=f'<h1 id="{aid}" style="margin:12px 0">{_pick(rng, _HEADINGS)}</h1>',
        intent="heading_h1", should_fire=True, anchor_id=aid,
    )


def landmark_header(rng: random.Random, aid: str) -> Fragment:
    return Fragment(
        html=(
            f'<header id="{aid}" style="padding:12px 20px;border-bottom:1px solid #eee">'
            f'<strong>Brand</strong> · <span>navigation sits here</span></header>'
        ),
        intent="landmark_header", should_fire=True, anchor_id=aid,
    )


def dialog_open(rng: random.Random, aid: str) -> Fragment:
    return Fragment(
        html=(
            f'<dialog id="{aid}" open style="border:1px solid #888;padding:20px;'
            f'width:320px;margin:20px auto">'
            f'<h3 style="margin:0 0 8px 0">Confirm action</h3>'
            f'<p style="margin:0">Are you sure you want to continue?</p></dialog>'
        ),
        intent="dialog_open", should_fire=True, anchor_id=aid,
        slop=1,
    )


def iframe_large(rng: random.Random, aid: str) -> Fragment:
    return Fragment(
        html=f'<iframe id="{aid}" srcdoc="&lt;p&gt;sandbox content&lt;/p&gt;" width="240" height="180" style="border:1px solid #aaa"></iframe>',
        intent="iframe_large", should_fire=True, anchor_id=aid,
    )


def icon_button_30px(rng: random.Random, aid: str) -> Fragment:
    return Fragment(
        html=(
            f'<span id="{aid}" role="button" tabindex="0" aria-label="Close" '
            f'style="display:inline-block;width:30px;height:30px;line-height:30px;'
            f'text-align:center;border:1px solid #ccc;border-radius:4px;cursor:pointer">×</span>'
        ),
        intent="icon_button_30px", should_fire=True, anchor_id=aid,
    )


def list_repeat_10(rng: random.Random, aid: str) -> Fragment:
    items = "".join(
        f'<li style="padding:8px 12px;border-bottom:1px solid #eee">Item {i + 1} · {_pick(rng, _LINK_PHRASES)}</li>'
        for i in range(10)
    )
    return Fragment(
        html=f'<ul id="{aid}" style="list-style:none;margin:12px 0;padding:0;width:320px;border:1px solid #ddd">{items}</ul>',
        intent="list_repeat_10", should_fire=True, anchor_id=aid,
        labels_produced=2,
        slop=1,
    )


# ------------------------------ filter drops (should_fire=False) ------------------------------

def bare_button_label(rng: random.Random, aid: str) -> Fragment:
    return Fragment(
        html=f'<button id="{aid}" type="button" style="padding:8px 12px">button</button>',
        intent="bare_button_label", should_fire=False, anchor_id=aid,
    )


def cursor_pointer_no_events(rng: random.Random, aid: str) -> Fragment:
    return Fragment(
        html=(
            f'<div id="{aid}" style="cursor:pointer;pointer-events:none;'
            f'padding:10px 16px;display:inline-block">Hover-only decoration</div>'
        ),
        intent="cursor_pointer_no_events", should_fire=False, anchor_id=aid,
    )


def tiny_element_10x10(rng: random.Random, aid: str) -> Fragment:
    return Fragment(
        html=f'<button id="{aid}" type="button" style="width:10px;height:10px;padding:0;font-size:6px">Go</button>',
        intent="tiny_element_10x10", should_fire=False, anchor_id=aid,
    )


def hidden_display_none(rng: random.Random, aid: str) -> Fragment:
    return Fragment(
        html=f'<button id="{aid}" type="button" style="display:none">Hidden via display</button>',
        intent="hidden_display_none", should_fire=False, anchor_id=aid,
    )


def opacity_zero(rng: random.Random, aid: str) -> Fragment:
    return Fragment(
        html=f'<button id="{aid}" type="button" style="opacity:0;padding:10px 16px">Ghost button</button>',
        intent="opacity_zero", should_fire=False, anchor_id=aid,
    )


def iframe_tiny_50x50(rng: random.Random, aid: str) -> Fragment:
    # 50×50 = 2500px², but rule r2 requires w>100 AND h>100 → skipped entirely.
    return Fragment(
        html=f'<iframe id="{aid}" srcdoc="x" width="50" height="50" style="border:1px solid #aaa"></iframe>',
        intent="iframe_tiny_50x50", should_fire=False, anchor_id=aid,
    )


# ------------------------------ registry ------------------------------

SHAPE_REGISTRY: dict[str, ShapeFn] = {
    "native_button": native_button,
    "native_anchor_text": native_anchor_text,
    "native_input_text": native_input_text,
    "role_button_div": role_button_div,
    "role_checkbox_div": role_checkbox_div,
    "onclick_div": onclick_div,
    "tabindex_div": tabindex_div,
    "cursor_pointer_div": cursor_pointer_div,
    "label_wraps_input": label_wraps_input,
    "span_wraps_input": span_wraps_input,
    "search_id_div": search_id_div,
    "custom_element": custom_element,
    "card_styled": card_styled,
    "heading_h1": heading_h1,
    "landmark_header": landmark_header,
    "dialog_open": dialog_open,
    "iframe_large": iframe_large,
    "icon_button_30px": icon_button_30px,
    "list_repeat_10": list_repeat_10,
    "bare_button_label": bare_button_label,
    "cursor_pointer_no_events": cursor_pointer_no_events,
    "tiny_element_10x10": tiny_element_10x10,
    "hidden_display_none": hidden_display_none,
    "opacity_zero": opacity_zero,
    "iframe_tiny_50x50": iframe_tiny_50x50,
}


def shape_is_firing(name: str) -> bool:
    """Convenience — does a shape of this name expect to produce a label?"""
    # Invoke with a throwaway rng; shapes are pure.
    frag = SHAPE_REGISTRY[name](random.Random(0), "__probe__")
    return frag.should_fire


FIRING_SHAPE_NAMES: list[str] = [
    name for name, fn in SHAPE_REGISTRY.items()
    if fn(random.Random(0), "__probe__").should_fire
]
FILTER_SHAPE_NAMES: list[str] = [
    name for name, fn in SHAPE_REGISTRY.items()
    if not fn(random.Random(0), "__probe__").should_fire
]
