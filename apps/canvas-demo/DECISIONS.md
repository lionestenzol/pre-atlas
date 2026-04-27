# canvas-demo · locked decisions

Answers to the two kickoff blockers from `memory/project_canvas_demo_video.md`.

## 1. Screen capture tool → Playwright built-in

Use Playwright's built-in recorder:

```ts
const context = await browser.newContext({
  recordVideo: { dir: 'clips/', size: { width: 1920, height: 1080 } },
});
```

Rejected alternatives:

| tool | why not |
|---|---|
| Cap (cap.so) | extra install, GUI-driven, flakier in CI |
| OBS Studio | manual start/stop, not scriptable |
| rrweb | DOM replay, not pixel-perfect video |
| CDP Recorder | devtools-only, not headless |

Playwright already drives the scenario — emitting WebM from the same driver is one config flag. No second dependency.

## 2. Demo length → 30s (first cut)

- 900 frames @ 30fps
- Composition: `width 1920 × height 1080`
- Beats: title 3s · pull 7s · open 5s · edit 10s · outro 5s

Iterate longer (90s narrative, 2-3min PH walkthrough) only after the 30s version ships.

## Output format

- Codec: h264, crf 18
- Draft renders: `--scale=0.5`
- Final: full-res `out/canvas-demo.mp4`
