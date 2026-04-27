# inPACT

inPACT is a standalone productized version of CycleBoard: a self-sustaining bullet journal for daily execution. It is the execution surface for users of Bruke's 20-lesson curriculum, where they live inside the methodology after learning it.

## What It Is

inPACT turns the CycleBoard operating method into a decoupled product experience. It gives users a structured place to plan the day, manage tasks, track routines, journal, define focus areas, work through the Eight Steps, and reflect on progress.

## How To Run

Run the app with `http-server` on port `3006` via the `inpact-app` launch config in `.claude/launch.json`.

The app is static and does not require a build step.

## Architecture

inPACT is built with vanilla HTML, CSS, and JavaScript. It has no build step. Styling uses the Tailwind CDN and icons use the Font Awesome CDN. Persistence is handled in `localStorage`.

## Module Map

The app is organized into 7 JavaScript modules, about 6700 LOC total.

- `state.js`: Defines the application state shape, default values, persistence behavior, and shared state access.
- `validator.js`: Validates state and user-entered records before they are persisted or rendered.
- `ui.js`: Owns shared rendering helpers, DOM updates, modals, notifications, and common interaction behavior.
- `helpers.js`: Provides reusable utility functions for dates, IDs, formatting, filtering, and small data transformations.
- `screens.js`: Defines the major app screens and their render flows.
- `functions.js`: Contains the core action handlers that mutate state and coordinate user workflows.
- `app.js`: Boots the application, wires events, loads persisted state, and starts the initial render.

## Data Model

Core data is stored under `state` and persisted as one localStorage payload.

- `state.AZTask`: Task records for the A to Z execution system.
- `DayPlans`: Daily plans and day-level execution structure.
- `Routine`: Routine definitions, cadence, and completion tracking.
- `Journal`: Journal entries and daily notes.
- `FocusArea`: Focus areas used to organize priorities and attention.
- `EightSteps`: Progress and inputs for the Eight Steps methodology.
- `Reflections`: Reflection records for reviewing outcomes and learning.

## State Key

inPACT stores its persisted state in `localStorage` under the key `inpact-state`.

## Relationship To Marketing Site

The marketing site lives at `C:/Users/bruke/OneDrive/Desktop/inPACT-site` in a separate repo. That site presents the product and links to this app via CTA.

## Relationship To cognitive-sensor/cycleboard

`cognitive-sensor/cycleboard` is Bruke's personal Atlas actuator with heavy Atlas brain coupling. inPACT is the decoupled product derivative: the same execution methodology shaped into a standalone app.

## Known Gaps

Known gaps include auth, backend persistence, Stripe integration, Public Integrity Toggle, and the onboarding flow. See `ROADMAP.md`.
