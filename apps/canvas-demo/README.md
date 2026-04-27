# canvas-demo

Remotion project. Scaffolded via `~/.claude/skills/remotion/scaffold.mjs`.

## Scripts

- `npm run dev` — open Remotion Studio at http://localhost:3000
- `npm run render` — render `Main` to `out/video.mp4`
- `npm run render -- --props='{"title":"Hi"}'` — with custom props
- `npm run render -- --scale=0.5` — half-res draft
- `npm run upgrade` — upgrade all Remotion packages in lockstep

## Layout

- `src/Root.tsx` — registers compositions
- `src/Main.tsx` — the video component
- `public/` — static assets, accessed via `staticFile('name')`
- `out/` — render outputs (gitignored)
