# Complete Coaching System — Phase 8 Release Rescue Addendum

**Status:** APPROVED WITH DATA PREREQUISITE
**Date:** 2026-09-04
**Parent scope:** `docs/complete_coaching_system_scope.md`
**Parent architecture:** `docs/complete_coaching_system_spec.md`
**Audited integration base:** `origin/working-code` at `fbe6514c2e222b84c523d63bbcec330387d63d2b`
**Product direction:** EXTEND the existing Complete Coaching System; do not create a parallel coach

## 0. Existing-surface decision

Phase 8 is a release rescue, not a new product and not a detector-building phase.

| Need | Existing canonical surface or authority | Phase 8 decision |
|---|---|---|
| One personal focus | `/home`, `ActivationHub`, `CurriculumPrimary`, `CanonicalFocusRail`, `focus_bridge` | **EXTEND.** Preserve one coach conversation and one primary action. |
| Board-first assigned practice | `/training`, `PersonalizedLessonWorkspace`, `PICPieceSafetyLesson`, `teaching_engine` | **EXTEND.** Use the shipped interactive grader; do not rebuild the right/wrong feedback already live in `cf7892ab`. |
| Complete game explanation | `/game/:gameId`, `LabV2`, `GameDecryptionV5`, central caption pipeline | **EXTEND.** Surface every currently authorized Caption fact when the stored evidence exists. |
| Honest learning evidence | `learning_evidence_ledger`, `LessonResult v2`, verified puzzle attempts | **EXTEND.** Do not create another attempt or mastery store. |
| Improvement story | `/progress`, `UnifiedProgress`, canonical mastery reducer | **CONSOLIDATE.** Player-facing claims must read canonical evidence or say not measured. |
| Deployment verification | `scripts/deploy.sh`, `backend/scripts/verify_deployment.py` | **EXTEND.** Add a mandatory non-admin full-journey reach check to the one deploy path. |
| Rollout eligibility | Existing master flags, role gates and per-user review feature flag | **CONSOLIDATE.** One complete-coaching cohort decision feeds all surfaces; subsystem truth gates remain independently fail-closed. |

The visible architecture remains:

```text
Home assigns one focus
        ↓
Training teaches it on an interactive board
        ↓
Server grades and records the attempt
        ↓
Review explains authorized moments from real games
        ↓
Later unassisted games provide comparable opportunities
        ↓
Progress reports improved / still recurring / not enough evidence
```

## 1. Outcome

At the end of Phase 8, a real non-admin player with analyzed games can encounter one complete, evidence-backed coaching journey without manual database repair or an administrator role:

1. Home explains one verified focus and why it matters.
2. The Home action opens the assigned interactive lesson.
3. The board accepts the move and immediately says whether it worked.
4. The server records the attempt once with assistance and version provenance.
5. Game Review shows every authorized applicable teaching fact whose stored proof is current.
6. Progress distinguishes practice from unassisted transfer.
7. A later analyzed game updates the same focus using comparable opportunities.
8. The next Home visit continues the same coaching story.

Phase 8 is not complete merely because code, flags, or counters exist. It is complete only after the real-user gate in §7 passes.

Before any non-admin enrollment, Phase 8 must first evaluate the already-shipped Plan-grade detector across the stored observation backlog, create eligible focus bundles through the existing focus authority, and freeze the resulting eligible denominator. This is release reconciliation for an existing detector, not new detector development.

## 2. Literal player experience

### Home

```text
YOUR COACHING PLAN

Keep every piece safe after you move it.

I have seen the same decision in several of your games: you choose a move,
but the piece can be taken on the square where it lands. We will practise
that exact check, then I will watch for it in your next games.

[ Practise this with your coach ]

Also watching
Your game review has two other verified moments. They do not replace
today's focus.
```

No centipawn report, confidence score, detector ID, unsupported psychology, or generic library prose appears in this card.

### Assigned lesson

Before the attempt:

```text
KEEP EVERY PIECE SAFE

What would you play here?
Choose your move on the board.

Position 1 of 5 · from one of your games
```

After a server-verified successful move:

```text
Yes — that works.

Your rook stays protected, and their queen has no free capture.

[ Next position ]
```

After a server-verified unsuccessful move:

```text
Not yet.

After your move, their queen can take your rook on d2. Try again and find
a square where the rook cannot be won immediately.

[ Try again ]  [ Show one hint ]
```

Piece names, squares, replies and consequences are rendered only from the verified result contract. If those facts are absent, the interface says only that the move did not pass and offers a retry; it never invents the reason.

### Completion

```text
Practice complete

You handled these positions with help available. That is useful practice,
but it does not prove the habit is yours yet.

I will check the same kind of decision in your next three analyzed games.

[ Return to your coach ]
```

### Game Review

```text
WHAT THIS GAME CAN TEACH YOU

Move 18 — your current focus
After Rd2, their queen could take the rook. Before settling on a move,
check whether the piece is safe on its new square.

Move 24 — a separate verified fork opportunity
One knight move attacked two valuable pieces. This is worth learning,
but it does not replace your current plan.

[ Replay move 18 ]  [ Try the fork ]
```

Only Plan- or Caption-authorized facts may produce these claims. Shadow and Disabled detector output remains invisible.

### Progress before later-game evidence

```text
Keeping every piece safe

You completed the practice.
Real-game improvement is not measured yet.

I am waiting for comparable decisions in your next analyzed games.
```

### Progress after the review window

```text
Keeping every piece safe

Getting more reliable

In your recent games, you handled this decision more consistently than
before the lesson. I will keep watching it while we begin the next focus.

[ See the game moments ]
```

or:

```text
Still recurring

You can solve this when the lesson points to it, but it is still being
missed inside games. I am changing the kind of practice and keeping the
focus active.
```

or:

```text
Not enough evidence yet

Your recent games did not contain enough comparable decisions. I will not
call this improved or unimproved yet.
```

## 3. The 11 local-only commits

The stale local `working-code` is 11 commits ahead and 97 commits behind `origin/working-code`. Phase 8 starts from the latest integration ref in a clean worktree. The old branch is preserved during implementation, but none of its commits will be cherry-picked wholesale.

| Local-only commit | Evidence on `origin/working-code` | Decision |
|---|---|---|
| `7a749dab` selection lock and corpus snapshots | Patch-equivalent commit already exists upstream | **ABANDON LOCAL DUPLICATE.** |
| `811282d4` ignore local test dependencies/logs | Upstream counterpart `43175905` | **ABANDON LOCAL DUPLICATE.** |
| `f535f249` detector quality gate and gold | Upstream counterpart `b20c825e`, followed by newer promotions | **ABANDON LOCAL DUPLICATE; KEEP NEWER UPSTREAM AUTHORITY.** |
| `1ae49051` guided frontend/canonical surfaces | Upstream counterpart `aec53faf`, followed by later product fixes | **ABANDON LOCAL DUPLICATE; EXTEND CURRENT SURFACES.** |
| `43be3a3f` delete malformed scratchpad paths | Those malformed files are absent from the current integration tree | **ABANDON AS NO-OP ON CURRENT LINEAGE.** |
| `a2469c21` One Surviving Instruction | Integrated and superseded through `b0105f21`, `3e32a4fe`, `f3bea6c9`, and later canonical-focus work | **ABANDON LOCAL DUPLICATE; KEEP CURRENT FOCUS BRIDGE.** |
| `f97594fc` repository operating standards | `AGENTS.md` and `.agents/skills` already exist upstream from `2497e47e` and later edits | **ABANDON OLDER DUPLICATE.** |
| `a35954fa` remove generated path blockers | Upstream counterpart `42e30369`; generated artifacts are absent | **ABANDON LOCAL DUPLICATE.** |
| `85d57984` remaining working-tree sweep | Material landed through `f3bea6c9` and later focused lineages; current versions of `focus_game_service`, product-loop census, canonical context, tests and designs exist upstream | **ABANDON WHOLESALE COMMIT.** Any apparently missing file must be justified and ported independently; the 119-file sweep is never replayed. |
| `50b44cbc` portable test collection | Patch-equivalent commit already exists upstream | **ABANDON LOCAL DUPLICATE.** |
| `4af8313c` export `piece_value_cp` | Patch-equivalent commit already exists upstream | **ABANDON LOCAL DUPLICATE.** |

This is an explicit merge decision, not an implicit orphaning. The stale branch/worktree is not deleted by Phase 8.

## 4. Numeric reach lock

The earlier `10 of 67` lock is superseded before implementation. A production coverage audit on 2026-09-04 established:

```text
non-admin users with an analyzed game                         64
non-admin users with an ACTIVE focus bundle                    0
non-admin users with >=1 firing Plan-grade observation        12
move_observations total                                  446,495
move_observations carrying the detector field              24,817 (5.6%)
```

Ten remains the **provisional candidate**, not the release target. Treating ten as final today would mean requiring ten of twelve currently eligible users to complete a nine-step journey, even though 94.4% of stored observations have not been evaluated by the existing Plan-grade detector. That denominator measures incomplete reconciliation, not genuine user eligibility.

The final completion target is locked only after the prerequisite in §4A completes. The lock report must state:

- total and evaluated stored observations;
- detector fires and exact decisions;
- non-admin analyzed-game users;
- users with qualifying Plan-grade evidence;
- users for whom the canonical focus authority can create a valid active bundle;
- the proposed absolute completion target, current denominator and rationale;
- why the proposal is feasible without silently converting it into a percentage target.

No non-admin enrollment may begin while this target is provisional. The target may be confirmed as ten or explicitly restated from the measured denominator, but it may not be selected to make the phase appear successful after user outcomes are known.

### 4A. Stored-evidence coverage prerequisite

Before baseline capture or cohort enrollment, release tooling must:

1. Dry-run the existing Plan-grade `destination_safety_exact` detector across every stored `move_observation` that does not already carry the current detector/proof version.
2. Report current, stale, missing, ineligible and invalid observations separately, with no production writes, Stockfish runs, model calls or detector changes.
3. On separate explicit approval, apply only the missing current detector decisions, preserving historical evidence and remaining idempotent.
4. Dry-run focus-bundle creation for eligible non-admin analyzed-game users through `user_active_focus`, `focus_bridge` and the existing primary-weakness authority.
5. On separate explicit approval, create only valid missing bundles; never replace a current valid focus merely to increase the denominator.
6. Re-run both jobs to prove zero additional writes, then derive and freeze the eligible denominator and final completion target.

The production counts above are the prerequisite baseline. Their purpose is to prove coverage was repaired, not to predict the eventual fire count.

### Full-journey completion definition

A real user counts once, and only once, when all of these server-verifiable facts exist in order:

1. Pre-enrollment transfer baseline frozen.
2. User was eligible through the canonical Phase 8 cohort decision and was not an admin/super-admin-only test.
3. Home served an authorized personal focus and recorded its stable focus/instruction identity.
4. User opened the assigned lesson from that Home action.
5. User completed the assigned lesson with at least one server-graded first attempt; assistance is recorded, not inferred.
6. A routed Game Review served at least one authorized teaching event or explicitly recorded `no_authorized_event` without failing the page.
7. At least one later unassisted analyzed game produced a comparable opportunity for the same focus.
8. The canonical reducer produced one honest verdict: `improved`, `still_recurring`, or `insufficient_evidence`.
9. A later Home or Progress response served that verdict from the same evidence identity.

Success does not require the player to improve. It requires the system to close the loop honestly. A `still_recurring` or `insufficient_evidence` verdict counts when every prior step is real and correctly represented.

## 5. Baseline-before-enrollment contract

Before any non-admin pilot flag changes, the release tooling writes an immutable internal baseline row per candidate user containing:

- baseline version and creation time;
- user and cohort identity inside production only;
- focus ID, instruction ID, detector-quality ID and proof version;
- the three fully analyzed games immediately preceding enrollment, using the already-locked three-game review window;
- comparable opportunity counts split into handled, missed, unclear and did-not-occur;
- latest canonical learner state and the evidence IDs supporting it;
- analyzed-game and review-record coverage at the cutoff;
- the exact enrollment cutoff timestamp and source commit.

The versioned artifact contains aggregates and salted/non-reversible cohort labels only. It contains no emails, raw user IDs, game IDs, PGNs, credentials or FENs.

If a user has no valid pre-period opportunity, the baseline records `insufficient_pre_period`. The user may receive coaching, but cannot support a before/after improvement claim until the contract has sufficient comparable evidence.

## 6. Reconciliation contract

The dry-run must classify every analyzed game and every relevant move record without changing production:

- `already_current`: required record exists with the current caption/plan/proof versions;
- `partially_reconciled`: some required current records exist and others are absent;
- `never_had_required_records`: no required caption/plan record was ever stored;
- `stale_version`: records exist but are from an incompatible version;
- `no_authorized_evidence`: the game has no currently authorized teaching fact;
- `invalid_or_unowned`: record cannot be safely reconciled and remains unchanged.

The report separately counts games and move records. It must report the known `caption_concept_id` reconciliation rather than recomputing already-current rows. Apply mode is additive/idempotent, requires an explicit cohort or game selector, and may not rewrite engine analysis or upgrade Shadow evidence.

## 7. Two different release gates

### A. Mechanical deploy blocker

`scripts/deploy.sh` must invoke strict deployment verification after backend and frontend health. The new check uses a dedicated non-admin verification account and a seeded, non-production-learning fixture to prove:

- the account is not authorized merely by role;
- canonical cohort access is active;
- Home returns the expected focus identity and action;
- the action target returns an interactive lesson contract;
- a legal test move is graded and yields an explicit verdict;
- the attempt is stored idempotently in the isolated verification namespace;
- Game Review returns authorized teaching events without leaking Shadow facts;
- Progress returns practice-versus-transfer state from canonical evidence;
- the shipped frontend bundle contains the routed components that consume these contracts.

Any skipped step is failure in deploy mode. The verification token/fixture configuration is supplied through server secrets and is never committed. A backend-only deployment may use an API-only variant; a frontend deployment must also prove the bundle marker and route contract.

### B. Real-user Phase 8 completion gate

Phase 8 does not graduate and rollout does not expand to all analyzed users until the final absolute target frozen under §4 is met. Manual verification by the product owner or coaches remains required for the sampled experience; counters alone cannot declare the release live.

The first formal review occurs 42 calendar days after the first non-admin cohort enrollment. If fewer than the frozen target have completed the journey, Phase 8 remains `pilot_incomplete`: rollout does not expand, the target is not lowered, and the review reports each journey step's eligible-user count and drop-off. The product owner then explicitly chooses whether to extend the pilot or repair a demonstrated reach/experience failure. User inactivity is reported separately from product-path failure.

## 8. Canonical rollout authority

Current rollout decisions are split across:

- `PERSONAL_CURRICULUM_ROLES`;
- `PERSONAL_IMPROVEMENT_CYCLE_ROLES`;
- `COACHING_CONTEXT_V1_ROLES`;
- personalized-review master/rollout flags and per-user feature data;
- the default-off `COMPLETE_COACHING_SYSTEM_V1_ENABLED` composition flag.

Phase 8 introduces one general **complete-coaching access decision**, not another concept registry or content source. It is the only place that decides whether a player belongs to the Phase 8 cohort. All five surfaces consume that decision. Existing subsystem flags continue to decide whether their implementation and evidence are safe to use; detector authorization continues to decide what may be said.

Compatibility adapters may read existing per-user review enrollment during migration. They may not maintain independent cohort lists. Role alone never grants real-user pilot access, and removing the per-user pilot flag removes the user from every Phase 8 surface without deleting evidence.

A player who is already mid-journey must not experience a silent disappearance. The canonical surfaces preserve their completed attempts and evidence and show a neutral paused state: “Your lesson and progress are saved. Your coach is preparing the next step.” Existing Game Review and ordinary training remain available; no transfer or improvement claim is fabricated while access is paused.

## 9. In scope

- A clean integration branch/worktree from the latest `origin/working-code`.
- The canonical cohort-access decision and adapters for Home, Training, Review and Progress.
- Pre-enrollment baseline capture and aggregate snapshot generation.
- Stored-observation coverage dry-run/apply for the existing Plan-grade detector and idempotent creation of valid missing focus bundles.
- Idempotent reconciliation dry-run/apply tooling with the §6 classifications.
- Routed use of all six Caption-grade authorizations plus the one Plan-grade authorization, only where their exact stored evidence exists.
- One non-admin API/browser contract journey suitable for local, staging and post-deploy verification.
- Mandatory strict reach verification in `scripts/deploy.sh`.
- Server-side journey evidence and aggregate counters.
- Honest player-facing practice, transfer and insufficient-evidence states.
- A deployment handoff for Claude containing ordering, commands, expected outputs and rollback.

## 10. Out of scope

- Any new detector, detector promotion, 3A.6 packet or Stockfish rerun.
- Rebuilding the already-live right/wrong lesson feedback.
- Enabling Shadow or Disabled detectors on a player surface.
- A new Home, Training, Review, Progress or coaching page.
- A second attempt store, progress reducer, focus store, caption pipeline or curriculum registry.
- Claiming improvement from lesson completion, hints, ratings or wins.
- An Elo guarantee or fixed result date.
- Deleting legacy readers before comparison and rollout evidence pass.
- Automatic 100% enrollment, production writes by Codex, or deployment by Codex.
- Deleting the stale 11-commit branch/worktree during this phase.

## 11. Acceptance criteria

- The pre-enrollment baseline is captured before any pilot access mutation.
- A reconciliation dry-run accounts for all analyzed games as exactly one §6 category and reports games separately from move records.
- Re-running reconciliation after apply produces zero additional writes.
- One non-admin verification journey passes automatically in the deploy path with no skipped checks.
- The seven currently player-authorized detector qualities are reachable only on their earned surfaces; all Shadow/Disabled controls remain absent.
- Home, lesson, review, evidence and progress use the same focus/instruction/concept identities.
- The lesson board is interactive and every submitted move receives a server-owned explicit verdict.
- Retries and duplicate submissions do not duplicate evidence.
- Practice completion never changes the transfer verdict by itself.
- The stored-observation and focus-bundle prerequisites complete idempotently before enrollment, and their rerun produces zero additional writes.
- The final eligible denominator and absolute completion target are frozen from the prerequisite report before any user outcome is observed.
- The frozen number of real non-admin users complete the journey in §4 before Phase 8 is declared complete.
- Mohit and the invited coaches manually verify sampled journeys before broader rollout.
- Rollback disables cohort access without deleting baselines, attempts, reviews or later-game evidence, and a mid-journey player sees the explicit paused state rather than losing the feature silently.

## 12. Delivery and deployment boundary

Codex owns implementation, tests, reconciliation tooling and the deployment handoff. Claude owns push and production deployment. Production mutation is not authorized by this addendum. Every reconciliation apply, target lock, baseline insert and cohort mutation remains a separate explicit production action; each tool defaults to dry-run and requires its own confirmation token.

Deployment order is fixed:

```text
backup + restore proof
→ fast-forward the clean server checkout to the approved commit
→ build the candidate backend/worker/frontend images without restarting production
→ keep COMPLETE_COACHING_SYSTEM_V1_ENABLED=false
→ run stored-observation coverage dry-run
→ inspect and explicitly approve/apply existing-detector decisions
→ run focus-bundle creation dry-run
→ inspect and explicitly approve/apply valid missing bundles
→ verify both jobs are idempotent
→ derive the eligible denominator and freeze the absolute completion target
→ run remaining reconciliation dry-run
→ inspect and explicitly approve/apply remaining reconciliation
→ verify remaining reconciliation is idempotent
→ capture the dedicated non-admin verifier baseline
→ enroll only the dedicated verifier through the existing per-user review flag
→ set COMPLETE_COACHING_SYSTEM_V1_ENABLED=true in server configuration
→ invoke scripts/deploy.sh; it restarts services and must pass the live non-admin journey gate
→ capture immutable baselines for the bounded real-user pilot
→ enroll the bounded real-user pilot
→ verify one real non-admin account manually
→ review at 42 days or earlier if the frozen target completes
→ decide whether rollout may expand
```

The candidate-image build is deliberately not a deployment: the current
production containers and frontend bundle remain untouched while the new
version's prerequisite commands run in one-off containers. This resolves the
bootstrap dependency in §7A—the mandatory live journey gate needs the frozen
target, verifier baseline and verifier enrollment to exist before the new
backend can pass its first restart. Failure of any prerequisite stops before
production services change.
