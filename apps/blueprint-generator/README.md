# Blueprint Generator

Deterministic constraint-based execution blueprint generator.
Takes one structured idea sentence and outputs a scoped, opinionated 8-section build plan.

## What It Does

1. Parses: "I am building a `<product>` that helps `<user>` do `<action>`"
2. Rejects vague language (platform, solution, optimize, AI-powered, etc.)
3. Generates 8 deterministic sections: Objective, Target User, Core Function, Constraints, MVP Features, Build Steps, Dependencies, Definition of Done
4. Locks scope to max 5 MVP features
5. Routes expansion ideas (Slack, analytics, mobile app, etc.) to a V2 Parking Lot

## What It Does NOT Do

- No AI generation
- No backend, no database
- No encouragement or motivation
- No feature additions beyond 5 MVP items

## Run Locally

```
npm install
npm run dev
```

Open http://localhost:3000

## Build

```
npm run build
```

Static output in `out/` directory. Deploy to any static host.

## Deploy

```bash
# Vercel (zero config)
npx vercel --prod

# Netlify
npx netlify deploy --prod --dir=out

# GitHub Pages — push out/ to gh-pages branch
```

## Architecture

```
app/page.tsx             Single page, two states (input/output)
app/layout.tsx           Root layout with metadata
app/globals.css          Dark theme, minimal responsive CSS
lib/types.ts             TypeScript interfaces
lib/parseIdea.ts         Input validation and extraction
lib/generateBlueprint.ts Deterministic section generation
lib/scopeLock.ts         Feature classification and 5-item cap
lib/formatBlueprint.ts   Markdown export for copy
lib/storage.ts           localStorage persistence
```

## Acceptance Tests

- [ ] Valid input produces 8-section blueprint
- [ ] Missing "building" / "that helps" / "do" shows specific error
- [ ] Segment under 2 words shows word count error
- [ ] "platform", "AI-powered" etc. rejected as vague
- [ ] Empty input shows error
- [ ] MVP features count is exactly 5
- [ ] Feature with "Slack" goes to V2 Parking Lot
- [ ] Feature with "analytics" goes to V2 Parking Lot
- [ ] 6th MVP feature requires replacement selection
- [ ] Copy button puts Markdown in clipboard
- [ ] Page refresh restores blueprint from localStorage
- [ ] Start Over clears state and returns to input
- [ ] `npm run build` produces static output with zero errors

## Part of Pre Atlas

Lives at `apps/blueprint-generator/` in the Pre Atlas monorepo. Zero coupling to other services.
