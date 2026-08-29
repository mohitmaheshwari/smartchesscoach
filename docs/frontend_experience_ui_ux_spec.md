# Frontend Experience UI/UX — Spec

**Status:** SIGNED OFF v1 — approved by Mohit on 2026-08-27.
**Version:** v1 (2026-08-27).
**Scope:** largest of the player-facing frontend surfaces; multi-day to ship in gated phases.
**Source of truth:** [frontend_experience_ui_ux_scope.md](frontend_experience_ui_ux_scope.md), signed by Mohit on 2026-08-27.

---

## 1. The problem

ChessGuru already has differentiated coaching: it detects a player's recurring issue, remembers it, assigns practice, observes a Focus Game, and can show evidence of recovery. The frontend does not yet express that loop as one obvious journey.

Static audit evidence:

- `App.js` declares 57 routes. Several specialist and legacy routes coexist without a single page-family contract.
- Core screens mix wine, amber, teal, emerald, violet and slate as competing primaries. The app can feel like separate products rather than one premium coach.
- Board experiences use both Chessground and `react-chessboard`, with different framing, controls, annotations and supporting layouts.
- Home, Lab, Game Review, Training and Play with Coach contain the right actions, but the next step is not consistently the most visually obvious action.
- Player-facing sharing is effectively absent, so earned progress has no privacy-safe, attractive object users can share.
- Home, Play with Coach and Prescribed Training contain active Personal Improvement Cycle work. A visual rewrite must preserve that behavior and its canonical `/api/coach/active-focus` contract.
- The live browser audit is currently blocked by Windows sandbox error 206. Static audit is complete; signed visual QA remains mandatory before rollout.

The result must feel premium, calm and personal while making this loop unmistakable: **what ChessGuru noticed → why it matters → the right activity → start/resume → proof of improvement**.

## 2. The shape — 6 outcomes

| Outcome | Before | V1 shape |
|---|---|---|
| One brand | Screen-specific color systems | “Warm Intelligence”: ink/warm surfaces, amber brand/action, teal progress, emerald success, soft rose mistakes |
| One shell | Destinations vary by viewport and page | Stable desktop rail, compact mobile bar, persistent contextual Start/Resume action |
| One coaching hierarchy | Many cards compete | Coach statement → personal evidence → one primary action → optional detail |
| One Board Stage | Two engines look unrelated | Shared frame, sizing, coordinates, controls, states and annotations; engine adapters remain intact |
| One guided loop | Recommendations can dead-end or drift | Canonical focus resolves to the correct opening, endgame, pattern, review or coached-play activity |
| Earned sharing | No player share object | Privacy-safe cards for Chess DNA, recurring insight, focus graduation and weekly recap |

Representative Home hierarchy:

```text
Coach Maya                                      7-day rhythm
“Your pieces are becoming safer.”
I found the same decision in 3 recent games.

[ Continue your piece-safety plan ]             6–8 min
Next: one guided lesson → three positions → Focus Game

Latest evidence              Your current focus              Recent activity
```

The headline names the human learning pattern, never a SAN move or detector key. Chess notation belongs on the Board Stage and in evidence details.

## 3. Schema / files touched

No database schema, coaching classifier, detector, plan store or board engine is added.

Canonical sources to extend:

- `frontend/src/index.css`: semantic color, elevation, focus, typography and Board Stage CSS variables.
- `frontend/tailwind.config.js`: expose existing semantic variables; remove page-level primary-color invention over time.
- `frontend/src/lib/motion.js`: retain locked timings and reduced-motion behavior.
- `frontend/src/context/ThemeContext.jsx`: retain light/dark ownership.
- `frontend/src/App.js` and `frontend/src/components/Layout.jsx`: route-family metadata, shell and responsive navigation.
- `frontend/src/components/LichessBoard.jsx` plus `react-chessboard` consumers: visual adapters to one Board Stage contract; chess behavior remains local to each engine.
- Shared UI under `frontend/src/components/ui/` and a small `frontend/src/components/experience/` layer for `PageHeader`, `CoachLead`, `PrimaryJourneyCard`, `ActivityCTA`, `BoardStage`, state panels and share previews.
- Page families: public/activation; Home; Lab/history; canonical Game Review; Training/openings/endgames; Play with Coach; Progress; Settings/legal; admin inheritance.

Protected dirty-worktree behavior:

- `HomePageNew.jsx`: Personal Improvement Cycle projection and Focus Game controls.
- `CoachPlay.jsx`: canonical active-focus pre-game instruction.
- `PrescribedTraining.jsx` and `PICPieceSafetyLesson.jsx`: PIC lesson routing.
- `MotifDrill.jsx`: server-side gating and verified wording.
- `PostGameReflection.jsx`: preserve current user changes after overlap review.

Route usage analytics are unavailable. `/coach`, `/focus`, `/games`, `/review`, `/lab/game/:gameId`, `/game-old/:gameId`, `/weaknesses`, `/opening-walkthrough`, `/openings-overview`, `/recover/:gameId` and `/plateau-breaker/*` remain functional until measured evidence supports redirects or retirement.

## 4. New facts / data the system needs

V1 foundation uses existing facts and APIs. It adds presentation telemetry, not coaching truth:

- `experience_variant`, route family and viewport family.
- Primary action impression, click, successful activity start and resume.
- Focus-to-activity resolution kind and whether the destination loaded successfully.
- Board Stage interaction failures and layout overflow signals.
- Share preview, export, native-share/copy outcome and selected privacy mode.
- Completion and return-to-next-step events across the guided loop.

Baselines must be captured before any numeric success threshold or route-retirement decision is locked. Local Mongo is unavailable and no production analytics source was provided, so current conversion, route usage and share rates are **UNKNOWN**.

## 5. Gating — preventing the “beautiful but less usable” trap

1. **Canonical-action gate:** every primary CTA is derived from the existing focus/activity resolver or existing page contract; visual code does not invent coaching destinations.
2. **One-primary-action gate:** a screen region may visually nominate only one next action. Secondary controls remain available but subordinate.
3. **Coaching-truth gate:** UI may simplify language, not strengthen confidence or invent improvement claims.
4. **Board-parity gate:** shared styling cannot change legal moves, orientation, FEN, arrows, highlights, promotion or callbacks in either engine.
5. **State-completeness gate:** loading, empty, error, stale, locked, complete and resume states ship with each redesigned family.
6. **Accessibility gate:** keyboard access, visible focus, contrast, touch targets, text scaling and reduced motion are required—not polish backlog.
7. **Performance gate:** no decorative asset or animation may delay board readiness or the primary action.
8. **Route-safety gate:** no alias or specialist route is removed without observed usage plus an explicit redirect decision.
9. **SSoT gate:** pages consume semantic tokens and shared primitives; no second theme, motion table, board model or improvement-plan store.

## 6. Test strategy

**Phase 1 — stateless probes**

- Token lint/audit: hard-coded competing brand colors, focus styles and semantic misuse.
- Route inventory: every `App.js` route assigned a family, shell mode and legacy disposition.
- Focus-action contract fixtures: each existing focus kind resolves to its correct destination.

**Phase 2 — boundary suite**

- Component tests for CTA hierarchy, loading/empty/error/locked/complete/resume and share privacy defaults.
- Board adapter tests for FEN, orientation, move callbacks, arrows/highlights, promotion and read-only states.
- Navigation tests for signed-out, new, active, returning and admin users at existing Tailwind breakpoints.

**Phase 3 — snapshots and journeys**

- Visual snapshots for light/dark, desktop/mobile and content extremes across each page family.
- End-to-end journeys: landing → activation; Home → correct activity; Lab → Review → Training; PWC setup → game → reflection; Progress → share preview.
- Frontend production build, console-error audit and existing relevant test suites.

**Phase 4 — Mohit/Parth eyeball**

- Live browser audit of every canonical route using realistic data.
- Chessboard interaction review on desktop and touch layouts.
- Copy and hierarchy review for the 600–1500 audience.
- Side-by-side old/new review before any rollout increase.

## 7. Risk + rollback

Main risks are visual regressions across 57 routes, breaking board interaction, hiding specialist workflows, overwriting in-progress PIC work, and making uncertain coaching claims look certain.

Flag: `REACT_APP_FRONTEND_EXPERIENCE_V1_ENABLED`, default `false`. Internal review builds may enable it explicitly. Percentage rollout requires deployment/cohort routing; the CRA build-time flag alone cannot assign users dynamically.

Rollback:

1. Set `REACT_APP_FRONTEND_EXPERIENCE_V1_ENABLED=false` in the frontend deployment environment.
2. Rebuild/redeploy the frontend; existing render paths remain until the clean-at-100% deletion phase.
3. Revert only the affected implementation commit if a shared primitive fails while retaining this spec and telemetry evidence.

No migration mutates user data, chess data or active-focus state.

## 8. What this spec does NOT cover

- Detector, classifier, Stockfish, caption-pipeline or confidence-threshold changes.
- A new recommendation engine, lesson catalog, activity type or improvement-plan store.
- Replacing Chessground or `react-chessboard`.
- Native mobile apps, a social feed, public profiles, leaderboards or casino-style gamification.
- New lesson content or deeper opening trees.
- Route deletion without analytics.
- Fixing unrelated product bugs except when they block a signed canonical journey; those receive separate scoped fixes.
- A production analytics vendor decision; this spec defines events, not the transport.

## 9. Implementation order

1. **Contract and baseline** — protect dirty overlaps, inventory route families, add telemetry names, obtain live-browser access. Expected commit: `docs(spec): frontend experience ui ux v1 — guided premium system`.
2. **Foundation, default-off** — extend semantic tokens, shared primitives, shell and Board Stage adapters behind the false flag. Expected commit: `feat(ui): add gated premium experience foundation`.
3. **Core guided loop** — Home, Lab/history, canonical Review, activity start/resume, Training and Progress. Expected commit: `feat(ui): unify the guided improvement loop`.
4. **Board and specialist families** — Play with Coach, openings/endgames, activation/import, public pages, settings/legal and admin inheritance. Expected commit: `feat(ui): apply board stage and page-family system`.
5. **Share moments** — privacy-safe preview/export/share using existing earned facts. Expected commit: `feat(ui): add earned progress share cards`.
6. **Ship default-off (flag false)** — run full test matrix and browser audit; Mohit signs visual acceptance.
7. **Mohit + Parth A/B for one week with flag on** — compare behavior and qualitative feedback; do not advance on unresolved board/action defects.
8. **10% rollout, monitor for one week** — only after analytics access and baseline-derived guardrails are locked.
9. **100% rollout** — only after the signed gate report shows no critical regression.
10. **Delete legacy code after two weeks clean at 100%** — consolidate render paths and remove the flag; route deletion remains a separate evidence-backed decision.

Phases 2–10 are blocked until Mohit answers §10 and signs this spec. No implementation commit is bundled with the spec.

## 10. Decisions approved by Mohit

Mohit approved the recommended decisions on 2026-08-27:

1. **Visual direction:** “Warm Intelligence” is the one product direction: ink/warm surfaces, amber action, teal progress, emerald success, rose mistakes; violet is no longer a competing primary.
2. **First implementation slice:** foundation + shell + Home + Lab + canonical Review comes first, followed by all remaining page families.
3. **Share launch:** Focus Graduation is first; usernames, opponent names, exact game links and rating are hidden unless the user opts in.
4. **Route policy:** no route is retired until production usage is available.
5. **Rollout evidence:** percentage rollout waits for an identified analytics/deployment owner and baseline-derived guardrails.
6. **Browser blocker:** implementation may proceed from the signed static audit and literal mockups; rollout remains blocked until supported live-browser visual QA is available.
7. **Dirty overlaps:** the PIC changes listed in §3 are authoritative behavior and must be preserved.
8. **Spec sign-off:** approved; application implementation may begin behind the default-off flag.
