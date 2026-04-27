# Anatomy Extension

Live-draw labels on any web app. Alt+click an element, type a label, it sticks. Persists per origin+path.

## Install (unpacked)

1. Open `chrome://extensions`
2. Toggle **Developer mode** (top right)
3. Click **Load unpacked**
4. Select this folder: `C:\Users\bruke\Pre Atlas\tools\anatomy-extension`
5. Pin the icon in the toolbar (puzzle piece → pin)

## Use

| Action | What it does |
|---|---|
| Click ⓘ button (bottom-right) | Toggle Anatomy on/off |
| Alt + hover | Outline the element you'd label |
| Alt + click | Open label prompt for that element |
| Hover label in side panel | Highlight + scroll to the region |
| Click ✕ on a label | Delete it |
| Export button | Download labels for this page as JSON |
| Import button | Load labels from a JSON file |

## Storage

Labels live in `chrome.storage.local` keyed by `hostname + pathname`. Same page next visit → labels rehydrate.

## Export format

```json
{
  "scope": "localhost/index.html",
  "exported_at": "2026-04-22T22:00:00.000Z",
  "labels": [
    { "label": "Atlas card", "selector": "main > div > div:nth-of-type(5)", "ts": 1745366400000 }
  ]
}
```

## Caveats

- Selectors use tag + `:nth-of-type` chains, not React keys. Heavy DOM rewrites can break them.
- Doesn't reach into iframes (cross-origin).
- No file:line links yet (host page doesn't know its source). Could add via a manifest config that maps selectors → repo paths.
