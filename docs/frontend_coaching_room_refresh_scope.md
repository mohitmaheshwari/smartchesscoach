# Frontend coaching room refresh

## 0. Existing surfaces audit

EXTEND existing. Layout owns desktop and mobile navigation. index.css owns the
cream, emerald and lime experience tokens and cg-page/hero/panel/action primitives.
CurriculumHome, AllGames and UnifiedProgress use these primitives; they currently
stack large introductions and page padding. AllGames and Progress override the
shared title size. The board and lesson state remain page-owned.

## 1. What it is

A calmer, more readable coaching room: compact introductions, a prominent next
action, consistent surfaces, visible navigation and subtle interaction feedback.
Mohit requested implementation on 2026-09-15, with ease and personalization next.

## 2. What the user sees

Home: greeting, a compact coach introduction, then the current lesson or playable
position. The current curriculum still supplies the title and action.

Game Review: “Let's find the moment worth understanding.” followed immediately
by the existing recommendation and game library. Import stays easy to find.

Desktop: readable forest sidebar, selected-page indicator, and named controls.
Mobile: clear menu and bottom navigation, with room for content above device insets.
Buttons lift gently on hover and respond when pressed; reduced motion disables
movement. Board animations and answers retain their existing behavior.

## 3. In scope

- Refine existing shared page spacing, typography, panels and action treatments.
- Improve navigation contrast and keyboard control names.
- Respect reduced-motion preferences in the shared shell.
- Remove oversized page-specific title overrides.
- Verify compilation and existing frontend behavioral tests.
- Inspect a rendered preview when the browser runtime is available.

## 4. Out of scope for the visual pass

New diagnoses, recommendation ranking, content authorization and mastery changes.
The next pass audits the complete student journey using existing server decisions:
resume, clear feedback, appropriate next action and honest progress states.

## 5. Success criteria

The lesson starts closer to the top of the viewport; controls remain readable in
both themes; keyboard users can identify and operate the shell; fixed mobile
navigation does not cover content; existing actions continue to their current routes.
User retention and personalization are not claimed from CSS changes.

## 6. Open questions

Live visual verification depends on a working preview browser. Record any missing
render check explicitly. Personalization changes follow a separate endpoint review.

## 7. Pre-code requirements

Existing surfaces inspected; literal presentation above; user authorization in
this turn; no new chess thresholds; clean branch from the reviewed integration tip.
Proceed with visual implementation, followed by existing behavioral checks.
