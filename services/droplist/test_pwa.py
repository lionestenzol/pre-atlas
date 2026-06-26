"""Task C acceptance: PWA installability.

Proves the three things Chrome needs to fire `beforeinstallprompt`:
  - a manifest is linked from the served HTML and serves with the right MIME
  - a service worker is registered and serves as JavaScript at root scope
  - the declared icons actually resolve
"""
from __future__ import annotations

import json

from fastapi.testclient import TestClient

from droplist.server import app

client = TestClient(app)


def test_head_injects_pwa_tags_and_sw():
    html = client.get("/").text
    assert 'rel="manifest"' in html
    assert 'href="/manifest.webmanifest"' in html
    assert 'name="theme-color"' in html
    assert "serviceWorker" in html and "/sw.js" in html


def test_manifest_serves_with_mime_and_icons():
    r = client.get("/manifest.webmanifest")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/manifest+json")
    m = json.loads(r.text)
    assert m["display"] == "standalone"
    assert m["start_url"] == "/"
    sizes = {i["sizes"] for i in m["icons"]}
    assert {"192x192", "512x512"} <= sizes
    assert any(i.get("purpose") == "maskable" for i in m["icons"])


def test_service_worker_serves_as_javascript():
    r = client.get("/sw.js")
    assert r.status_code == 200
    assert "javascript" in r.headers["content-type"]
    assert r.headers.get("Service-Worker-Allowed") == "/"
    assert "addEventListener('install'" in r.text


def test_declared_icons_resolve():
    for name in ("icon-192.png", "icon-512.png", "icon-maskable-512.png", "apple-touch-icon.png"):
        r = client.get(f"/icons/{name}")
        assert r.status_code == 200, name
        assert r.headers["content-type"] == "image/png"
