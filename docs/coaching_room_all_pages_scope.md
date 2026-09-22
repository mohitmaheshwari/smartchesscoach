# ChessGuru coaching room — all-page UX scope

**Status:** Visual direction and all-page coverage explicitly approved on 2026-09-22: “okay, go ahead, and make this UX for all our pages please.” This document records the detailed implementation boundary for final scope sign-off; application implementation has not started.

**Relationship to existing work:** EXTEND the signed frontend experience and current inner-product design. This amendment supersedes their conflicting palette, headline-size and animation treatments, not their working features or data contracts.

## 0. Existing surfaces audit

The [existing-surfaces audit](coaching_ux_polish_existing_surfaces_audit_2026_09_22.md) inventories all 66 routes at `3df9ab99`, their 57 directly routed component owners, and shared/redirect states. That inventory is the coverage checklist for this scope, not a claim that those pages have been redesigned or tested.

The shared `Layout.jsx`, `index.css`, `lib/motion.js` and `lib/experience.js` already own navigation, presentation and motion. `CurriculumPrimary`, `PersonalizedLessonWorkspace`, the existing board renderers and Game Review controls provide the appropriate extension points. No second app shell, lesson controller, recommendation service or progress database is needed.

The main problems are oversized introductions, small teaching text, text-only lesson cards, competing colour systems, weak error states and inconsistent feedback timing. Source inspection also found unregistered action destinations, opening-performance labels phrased as knowledge, and some empty results framed as improvement. These are explicit issues, not reasons to bypass evidence gates.

**Decision: EXTEND existing.** All current routes remain accounted for. Canonical customer pages receive full composition work; internal tools receive efficient forms/table/board polish; aliases retain their destination; legacy routes receive compatibility and accessibility treatment without becoming a second redesigned product. No route retirement is authorised here.

## 1. What it is

A coherent ChessGuru coaching room across the whole application: warm ivory, forest green, restrained sage and lime, elegant editorial headings, readable interface text and a strong chessboard. Each page makes its purpose and next action clear. The coach offers guidance without taking away the player's choice. Motion explains a move or acknowledges an action; it never delays feedback, hides an error or rushes the student past an explanation.

## 2. What the user sees

### Approved visual reference

The approved interactive study is [`design/chessguru-atelier.html`](design/chessguru-atelier.html), landed in the branch on 2026-09-22 with [`design/README.md`](design/README.md) recording its palette, typefaces and reference-only status. Its appearance and interaction quality are the reference; its illustrative chess position, simplified move script, unsaved completion and placeholder account states are **not production functionality**.

Done — it no longer depends on a temporary conversation context. It sits in `docs/`, outside CRA's build and outside `frontend/public`, so it is not routed, served or bundled. The reference itself loads Google Fonts and a **mutable** `lichess-org/lila@master` piece-image URL; neither may ship. Use licensed, self-hosted fonts and the existing bundled piece assets in the app.

### Shared frame

- Warm-white working surface, forest navigation, calm neutral borders; no blanket green glow or gradient behind every page.
- Editorial serif for selected coaching headlines, Manrope for readable controls/body text. Tables, errors and move notation remain straightforward, not decorative. Preserve current user theme choice and provide a tested dark companion.
- Keep the existing primary labels Home, Learn, Game Review, Progress and Play with Coach. The mockup's “Today” is not a route or navigation rename.
- Compact mobile navigation keeps the board and main action accessible. No desktop sidebar squeezed onto a phone.
- Existing admin/view-as warnings remain unmistakable; notifications, account tools and menus keep their working actions.

### Home and Learn

```text
HOME                              LEARN
Welcome back, Mohit.               Your learning space
[Current activity title]          [Current lesson title]
[Relevant position, when safe]    [Relevant position, when safe]
[Why this was selected]           [What we are practising]
[Continue / Start]                [Continue with your coach]
                                  Explore openings · Endgames · Other lessons
Bring your games · Play with Coach
```

The bracketed text is supplied by the existing authorised recommendation, not a new client-side opinion. In a verified rook example the pattern-led heading can be “They don't have to face the queen alone.” That sentence must not be reused on unrelated positions.

When no suitable, authorised board preview is available, show the real lesson title/reason and working action in a compact text composition. Never substitute the mockup's rook position. A preview cannot expose a diagnostic answer, detector label or pre-answer hint.

### Training, diagnosis and lesson workspaces

```text
Piece safety                          Your coach
[Live board, same orientation]       [Position-specific question from the lesson]
                                      [Hint, when supported]

After the verified response:
[Board stays in place]                ✓ [Verified result]
                                      [Short reason tied to this board]
                                      [Show me why, only with a supported line]
                                      [Continue]
```

The student moves on deliberately after the verdict. An automatic opponent reply inside a sequence is not the same as automatically discarding feedback. Preserve accepted alternatives, promotion selection, retry, assistance tagging and attempt submission. A request error says “I couldn't check that move. Try again.” It never marks the move wrong or advances the lesson.

Replay provides previous, play/pause, next and restart where a legal verified continuation already exists. Actual play and alternative lines stay labelled. Reduced motion changes presentation only. Completion says what was done, offers a next step, and never calls assisted practice mastery.

### Game selection, review and libraries

```text
GAME REVIEW
[Reason this game is worth studying]
[Real position]  [Study this moment]
Your games: searchable/browsable existing archive

OPENINGS / ENDGAMES
[Current supported recommendation]
[Relevant board] [Short title] [Open lesson]
Explore the existing library
```

Show why a recommendation was selected when the API supplies it. Otherwise say that the recommendation is unavailable and preserve the archive; do not fabricate a selection rationale. Long opening names remain available in details. “Worth revisiting” describes performance more honestly than “You don't know this.” No invented game totals, durations, ratings, streaks or success percentages.

### Play with Coach

```text
[Start / Resume existing game]
[Board]                               [Current coach message]
                                      [Existing action for this message]
                                      Earlier messages

[Connection status when relevant]     [Existing postgame review action]
```

Keep the active message and relevant intervention visible; preserve the earlier conversation in an accessible history. Never hide a safety intervention in pursuit of minimalism. Reconnect, waiting for opponent, game over and teaching mode each have a recognisable state. No controller or engine change.

### Progress, arrival and utilities

```text
PROGRESS                            IMPORT
What you've worked on               Bring your chess with you.
[Recorded practice, if available]    [Chess.com / Lichess username]
[Later-game evidence, if available]  [Connect]
[Comparison or exact unavailable     Connected → Importing → Analysing
 reason; useful next action]         [Existing supported lesson while waiting]
```

Unavailable comparison is not no progress. Available activity may be shown only from existing records, without weakening baseline or evidence rules. Onboarding retains its supported puzzle/game/import policy. Public landing, login, invite and pricing use the same brand with their own acquisition/form layouts. Legal pages prioritise reading; settings prioritises reliable editing. Internal reviewers get readable tables and evidence, not consumer-sized slogans.

### Motion and state quality

- Real pieces move through the existing renderer; board orientation and scroll position do not jump when feedback arrives.
- A small confirmation acknowledges verified success; no compulsory confetti, audio or repeated reward animation.
- Opening a coach explanation is a brief transition, not letter-by-letter simulated typing or an artificial wait.
- Loading, empty, error, partial and success states are distinct. Retry preserves entered data where safe. Existing data is not erased by a refresh spinner.
- Reduced motion, keyboard, touch, visible focus, zoom, light/dark and narrow layouts are part of the design, not a later patch.

## 3. In scope (V1)

- Apply the approved visual language through the existing shared styles, navigation and motion owners; consolidate conflicting overrides in touched areas.
- Cover every row of the 66-route audit. Track each as not started, implemented, tested or blocked; a shared CSS change does not mark a route complete.
- First deliver the real Learn → lesson → result → completion → return slice, then extend to Home/arrival/import, libraries/review, PWC/progress/settings, public/support and internal/compatibility surfaces.
- Improve layout, text hierarchy, action labels, responsive controls, error recovery and presentation transitions without changing chess judgments or curriculum priorities.
- Reconcile feedback timers with the existing lesson protocol and durable completion/attempt records. No invented persistence.
- Fix scoped navigation defects only after identifying the intended destination and required state; keep email and deep-link promises.
- Add focused component/interaction tests and a route/state coverage record; render actual app pages rather than count this prototype as app QA.
- Prepare an account-isolated visual pilot and Claude deployment handoff, with actual commit IDs, checks, known gaps, exposure and rollback instructions.

## 4. Explicitly out of scope (V1)

- New detectors, teaching facts, engine/model calls, counterfactual proofs, grading tolerances, opening taxonomy or recommendation ranking.
- Backend changes of any kind, with one explicitly approved exception: the presentation-gate boolean and its allowlist on the existing `/auth/me` response (implementation spec §5). It carries no chess, evidence or curriculum data.
- Production imports, migrations, baseline capture, enrollment, enabling Shadow content or switching PWC controllers.
- New subscriptions, price/entitlement changes, altered legal terms, email campaigns or invitations.
- New community game matching, multiplayer, coaching memory systems or progress claims; existing capabilities stay intact.
- Copying the prototype's fixed chess positions, manual answer script or local completion state into real product paths.
- Deleting old routes, merging unrelated worktrees, replacing either board engine or building a second design system.
- Claiming that visual polish guarantees payment, retention or learning improvement.

## 5. Success criteria

- In observed representative journeys, a player can identify the next task, start it, understand the result, finish deliberately and return to the correct place without facilitator guidance. Compare task completion and avoidable backtracking with the current experience; do not invent a conversion target before a baseline exists.
- The full Learn slice works with real supported payloads and at least one non-admin account in a safe test environment. Mock API tests are labelled as such and do not substitute for it.
- Every route and important query mode is accounted for; changed controls preserve their original action, authority and saved state. All evidence-backed content remains gated as before.
- No known new frontend regression, solution leak, duplicate attempt, false success state, lost active game, unreadable control or keyboard trap remains at release.
- Desktop/mobile and light/dark rendered checks, measured contrast and reduced-motion checks pass. Latency claims require measured request and rendering timings, not animation impressions.
- The product owner approves rendered app screenshots and the live local/staging journey against the approved design. App-wide completion is not declared while route families or critical states remain untested.

## 6. Open questions

- **Question:** Does this all-page implementation boundary match the approved visual direction? **Why unresolved:** the visual approval preceded this detailed scope. **Unblocking step:** Mohit's explicit sign-off on this scope and companion implementation spec.
- **ANSWERED 2026-09-22, from source:** the curriculum payload exposes **no** preview position. `CurriculumCandidate.public_dict()` in `backend/services/personal_curriculum.py` returns exactly `outcome`, `state`, `title`, `reason`, `evidence` and `destination` (`href`, `medium`, `capability`, `lesson_kind`, `lesson_id`). No FEN, no position, anywhere in the contract. The only FEN-bearing path on these surfaces is `HomeReplayDiagnostic`, which is a separate diagnostic with its own answer-hiding rules. **Consequence:** the Learn slice ships the compact text composition, as this scope requires. A board preview on Learn would need a new backend contract and therefore separate approval; it was not added.
- **Question:** What observed change would count as better usability? **Why unresolved:** no baseline task study has been conducted. **Unblocking step:** record representative baseline journeys and compare task completion/backtracking; release correctness gates remain mandatory regardless of those results.

## 7. Pre-code requirements

- Complete: route inventory and EXTEND decision; approved literal interactive visual reference; source owners identified.
- Required: explicit sign-off on this document and `coaching_room_all_pages_spec.md`; no implementation until that gate passes.
- Before each slice: recheck upstream and overlapping edits without overwriting other work; preserve a reproducible baseline and component test results.
- Identify the exact existing payload, renderer, mutation and assistance-state owner for every new presentation element. No decorative substitute for missing facts or states.
- Use existing motion settings initially; no new chess thresholds or quality scores are introduced, so a detector-threshold data lock is not applicable.
- Rollout isolation is decided, not deferred: a runtime per-account gate carried as one boolean on the existing `/auth/me` response, default false for every account until a `user_id` is explicitly allowlisted. See the implementation spec §5. A build-time `REACT_APP_*` flag was considered and rejected — it produces one bundle and cannot isolate accounts. The existing experience flag defaults on and is not isolation for this pass.
- Approved reference landed at `docs/design/chessguru-atelier.html` (complete). Baseline journeys at `3df9ab99` must still be recorded before the first implementation slice — that comparison is unrecoverable once slice 1 lands.
- Run the six-point pre-code audit. Separate approved visual intent from implementation verification and production availability.
