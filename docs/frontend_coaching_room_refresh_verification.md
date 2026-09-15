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
