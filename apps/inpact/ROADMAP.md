# inPACT Phase 2+ Roadmap

Phase 1 is extraction wiring and is already underway. Phase 2+ work should move the app from local, single-device behavior toward authenticated, durable, and monetized use without changing the current product model unnecessarily.

## 1. Auth

Add email magic link authentication as the primary sign-in path.

Candidate stacks:

- Supabase Auth: Email magic links, session handling, user IDs, and direct alignment with the planned Supabase backend.
- Clerk: Polished hosted auth UI, strong account management, and fast setup, with another service boundary to manage.
- SuperTokens: Flexible self-hosted auth with good control, but more operational responsibility than this phase needs.

Recommendation: Supabase Auth.

Supabase keeps auth and data ownership in the same system, simplifies row-level security, and avoids a second identity integration before the product needs it.

## 2. Backend

Replace direct `localStorage` persistence with the Supabase client SDK.

Use row-level security so each authenticated user can only read and write their own app state. Every persisted row should include a user identifier tied to Supabase Auth.

The state table schema should mirror the current `state.js` shape as closely as practical. Preserve the existing concepts and naming first, then normalize later only when there is a clear product or reporting need.

State areas to account for:

- `AZTask`
- `DayPlans`
- `Routine`
- `Journal`
- `Reflections`
- Goals
- Check-ins
- User preferences
- Onboarding completion state
- Paywall entitlement state
- Public integrity visibility settings

## 3. Storage Abstraction

Build this before the backend work.

Create a storage interface in `state.js` so persistence can be swapped mechanically. The current local implementation should become one implementation of that interface, and Supabase should become a second implementation.

The interface should cover the operations the app already performs:

- Load full state
- Save full state
- Update a state section
- Reset or clear state
- Handle missing or corrupt stored data

Keep the app's state consumers unaware of whether data comes from `localStorage` or Supabase. This keeps the backend migration small, testable, and reversible while Phase 2 is still being built.

## 4. Onboarding Flow

Add a first-run walkthrough that runs once per user.

The flow should have five screens and should tie directly to the curriculum:

- Welcome and purpose
- Lesson 5: Dispositions
- Lesson 6: 1st Install
- Lesson 7: SMART Goals
- Lesson 8: 8 Steps

The walkthrough should set up the user's initial path through the app without duplicating full lesson content. It should help the user choose or confirm their starting disposition, first install, SMART goal, and next action sequence.

Persist completion state so returning users do not see the flow again unless they explicitly restart it.

## 5. Stripe Paywall

Add Stripe Checkout for paid tier access.

Free tier limits:

- A-Z expansion is limited to 5 letters.
- Reflections are limited to weekly use.
- Routines are limited to 1 active routine.

Paid access should unlock:

- A-Z expansion beyond 5 letters.
- More frequent reflections.
- Multiple routines.

The app should check entitlement state before showing gated expansion paths. Stripe should own payment collection and subscription status. The app should store only the entitlement state needed to render access correctly.

## 6. Public Integrity Toggle

Add a per-A-Z-task visibility flag.

When visibility is enabled, generate a public share link that renders the selected task without exposing private user state. The public renderer should show only the approved task data and any public progress fields needed for integrity tracking.

Optional witness or follower identity can be added after the basic share link is stable. Witness identity should not be required for the first version of public sharing.

## 7. Marketing Site Handoff

Marketing lesson calls to action should link to:

`https://app.inpact.com/signup`

Include a lesson reference query parameter so the app can highlight the right tier preview during signup.

Example:

`https://app.inpact.com/signup?lesson=5`

The app should read the lesson reference and use it to determine which preview or upgrade prompt to highlight. This keeps curriculum context intact when a user moves from the marketing site into the app.

## 8. Spec PDF Review

Review the original inPACT spec manually before finalizing Phase 2+ design decisions.

The source file is:

`apps/inpact/docs/inpact-spec.pdf`

The PDF is 11.7 MB and image-based, so it cannot be read programmatically with normal text extraction. Open it manually and validate the roadmap against the original intent before locking backend schema, onboarding sequence, public sharing behavior, and paywall boundaries.
