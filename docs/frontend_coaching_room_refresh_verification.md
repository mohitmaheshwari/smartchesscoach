# Frontend coaching-room refresh: first visual pass

Branch: `codex/frontend-coaching-room-v3`.
Base: `71b8a016` in `_one_coach_experience`; unrelated main-worktree edits untouched.

## Implemented

- Shared page padding and hero typography reduced so actions appear earlier.
- Forest/cream/lime palette retained; sidebar labels made more readable.
- Game Review columns rebalanced and chapter panel made theme-aware.
- Hover/press feedback and entrance motion retained/refined; shell respects reduced motion.
- Skip-to-content, named icon controls, mobile-menu expanded state, larger mobile controls.
- One main landmark in the curriculum Home path.

## Verification

- Five frontend suites, **20 passing tests**: LayoutNotificationEffects,
  AllGamesCoachSelected, UnifiedProgress.evidence, UnifiedProgress.trainedPattern,
  CurriculumPrimary. Includes a new keyboard/navigation-contract test.
- Production build exit **0**. Existing warnings: stale browserslist data,
  missing chess.ts sourcemap, large main bundle. Not resolved by this pass.
- `git diff --check` clean.
- Actual production bundle rendered in isolated headless Edge, with synthetic
  account/API fixtures and HTTPS requests blocked. This is layout verification,
  not production account or backend E2E evidence.
- Game Review at 1440x1000 and 390x844, in light and dark themes: no horizontal
  overflow; desktop mobile-nav hidden; mobile bottom-nav visible; primary review
  button fully above the fold (desktop bottom 502px, mobile bottom 483px).
- Initial render exposed a pale dark-mode chapter panel and excessive desktop
  panel height; both corrected, rebuilt, and re-rendered.
- Screenshots retained locally in `frontend-visual-artifacts/`.

## Boundaries and next pass

Not a completed all-page redesign. Home/Learn/Progress regression tests ran;
their full state matrix, onboarding, live chessboard flows, and device touch
testing still need visual/interactive coverage. The screenshots use synthetic
content and must not be presented as a real player's personalized findings.

Next: inspect actual resume state, result feedback, next-action selection, and
empty/error paths across Home -> lesson -> review -> play -> Progress. Reuse the
canonical curriculum decision and learning ledger; do not invent diagnoses,
duplicate rankings, or imply practice alone proves transfer.

No backend, detector authorization, rollout flag, production data, or deployment
changed. Claude's ongoing deployment remains separate.

## Guided-flow continuation

Approved in the following user turn (“go”). Existing personalized lesson flow
extended; no new page or coaching decision source.

- Final response verdict, soundness note and explanation remain visible after
  completion. Completion itself no longer asserts “You found the idea.”
- Completion invalidates the old curriculum cache and renders CurriculumPrimary
  from the current server decision. Disabled/missing decisions fall back to the
  plan; failed requests offer retry without resubmitting the lesson answer.
- Failed HTTP and network pause requests keep the student on the board with a
  retry instruction. Successful pause invalidates the plan cache before leaving.
- Changing lesson parameters clears the prior session/feedback during loading.

Verification: seven suites, **29 passing tests** (PersonalizedLessonWorkspace,
CurriculumPrimary, LayoutNotificationEffects, PrescribedTraining route/back/
emptyPool/clockFocus). Five new cases cover stale-plan refresh with exact route,
negative final feedback plus plan retry, HTTP pause failure, network pause failure,
and changing lesson parameters. Existing concept and endgame flows still pass.

Production build exit **0**; same warning categories as above. Synthetic completed
session rendered through the built `/training` route in headless Edge at 1440x1000
and 390x844. No horizontal overflow. Next action bottoms at 464px desktop and
715px mobile. Mobile dark screenshot inspected. This is not live-account E2E;
the final-response transition is verified by component interaction tests.

Voice review: new copy describes practice completion and navigation only; chess
explanations still come from the existing server response and moveVerdict. No new
material claims, notation-led headline, or generated chess teaching path added.

Remaining: production account round-trip after integration/deployment; deeper
resume persistence and coherence across game review/PWC/Progress. No claim that
the whole personalized journey has now been redesigned or validated.

## Review / coach-game / Progress continuity

Further continuation approved with “go ahead”. Repairs to existing surfaces:

- Progress HTTP/network/malformed-response failures now have a distinct retry
  state. They no longer masquerade as an absence of learning evidence.
- If the curriculum request alone fails, available game evidence stays visible
  with a lesson-loading warning. A valid disabled response retains the original
  honest evidence state. Transfer interpretation is unchanged.
- Unified PWC postgame buttons pair the label and destination from the same
  server recommendation. A label without a destination no longer promises
  practice while silently starting a new game; it says “Play another game”.
- Successful review saves, game end, and arriving unified postgame summaries
  invalidate the existing curriculum cache. Failed review saves do not.
- Progress uses the shell's main landmark rather than nesting another main.

Combined verification: **14 suites / 61 tests passing**. Includes HTTP/network/
malformed Progress failures and retry, partial curriculum failure with evidence
preserved, legitimate disabled state, clicked postgame route assertions, late
summary invalidation, successful/failed review completion, and all prior lesson
flow regressions. This includes both interaction tests and existing source-contract
tests; it is not a full API or production E2E run.
Production build exited 0; the same browserslist, chess.ts sourcemap, and bundle
size warnings remain. `git diff --check` passed.

No fresh browser screenshots were taken for this continuation. The new failure
card reuses the already-rendered shared visual primitives; visual verification of
this specific state and the real-account combined journey remains outstanding.
No detector, caption fact, mastery threshold, role gate, or production data changed.
