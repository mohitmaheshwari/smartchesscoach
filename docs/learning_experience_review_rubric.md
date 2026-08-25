# Review Rubric: Learning Experience System (fork V1)

**Purpose.** The criteria the implementation will be reviewed against, published
*before* the code is written so it prevents findings instead of catching them.

**Reviews against:** `learning_experience_system_scope.md` v3.1 and
`pattern_learning_system_scope.md` v4.4. If either document changes, this rubric
is stale.

**Method.** Every claim is verified against the running code or the database —
never against the diff narrative or the implementer's summary. "It says it does
X" is not evidence that it does X.

---

## Pre-existing conditions the implementer should know

These are already true of the codebase. They are not caused by this work, but
this work will be judged on whether it repeats them.

| Fact | Verified | Consequence for this build |
|---|---|---|
| `EndgameLesson.jsx` — the phase machine PLS §3.3 generalises from — has **0** `aria-`/`role=` attributes and 2 responsive utilities | grep | Copying its structure inherits a component that fails LES §7.6. The generalised runner must add what the source lacks. |
| **22 of 250** `.jsx` files use any `aria-`/`role=` | grep | Accessibility is absent product-wide. The lesson runner is a board-interaction surface where it matters most; it is the place to start, not another file that skips it. |
| Frontend has **1** test file; CI runs only `src/lib/*.test.js`, no component rendering | `.github/workflows/ci.yml` | A new interactive component gets zero automated coverage unless tests are written deliberately. |
| The caption-source guard runs `|| true` | `ci.yml` | It cannot fail the build. Do not treat a green CI as proof no parallel caption path was added. |
| Four newline-identical `active_recall_*` modules; bare imports resolve the root copies | LES §0 | Consolidation is required by LES §7.3. Do not add a fifth copy or a new bare import. |

---

## Lens 1 — Product

The question: *does this make ChessGuru better, or just bigger?*

| Check | How | Bar |
|---|---|---|
| Scope held to fork-only | Read the diff's file list | No piece-safety, endgame, or opening lesson code. Sample screens in the scope do not authorize files. |
| No new top-level nav | `grep -n "name: '" frontend/src/components/Layout.jsx` | Item count unchanged. |
| Walking skeleton is actually thin | Trace the implemented path | One recommendation → baseline item → guided interaction → different unseen item → exit → resume → delayed recall. Extra stages built before that loop is proven is scope creep. |
| No second lesson dispatcher | `grep -rn "def start\|def process_move\|def exit" backend/services/` | `teaching_engine.py`'s vocabulary is extended, not duplicated. |
| No second mastery label | `grep -rn "unseen\|learning\|studied\|stale" backend/ --include=*.py` | Only `concept_mastery_service` publishes learner-facing status. |
| Existing entry points converge | Follow every link that reaches a fork lesson | Same saved session, same state. Not two versions of the same lesson. |
| Unrelated defects not bundled | Diff review | Plateau Breaker routes, Opening Quiz correctness, and `/challenge`+`/opening-walkthrough` audits are separate work and are **not** cited as evidence this V1 works. |

---

## Lens 2 — The user (a 700–1500 player, on a phone, tired, after a loss)

The question: *can they actually do this, and do they feel taught rather than tested?*

| Check | How | Bar |
|---|---|---|
| Completable from the board alone | Walk the lesson without reading SAN | Every interaction is a tap/drag on a square or arrow. SAN may only appear as a secondary label after an action. |
| Voice | `python backend/scripts/pwc_coaching_lint.py` **plus** reading every string | No jargon (`fianchetto`, `prophylaxis`, `zwischenzug`), no snake_case leaks, no "1 mistakes", no pawn called a piece. The lint catches mechanics; only reading catches condescension. |
| Pattern leads, not the move | Read every caption | Never open with "you played Nxe4". Lead with the geometry or idea; SAN is footnote evidence. |
| Never restates the destination square | Read every caption | "Nf3 puts your knight on f3" is zero information. |
| Wrong answers teach | Trigger each wrong-answer branch | Names the missed geometry/defender/attacker. `Incorrect — Nf6 was best` fails. |
| Recommended moves carry a why | Read every "better was X" string | A move without a purpose raises the student's "why?" and walks away. |
| Two-strike exit works | Answer wrong twice | Teaches the position, marks it `shown`, does not count it. No endless retry. |
| No fabricated praise | Complete a lesson by revealing everything | Result must not read as mastery. |
| No dark patterns | Read all copy | No streak pressure, no loss-aversion urgency, no "don't lose your progress". |
| Honest when evidence is thin | Force the no-personal-content path | Says "rating-appropriate foundation", never invents a personal weakness. |

---

## Lens 3 — Usability and accessibility

| Check | How | Bar |
|---|---|---|
| Board usable at 360px | DevTools mobile viewport | Squares are tappable targets; the position stays visible while answering. |
| No scroll-away | Mobile viewport, mid-question | The learner never scrolls the board off-screen to read the prompt or reach the answer control. |
| Color is not the only signal | Grayscale the page | Correct/incorrect distinguishable without hue — icon, text, or shape. |
| Keyboard reachable | Tab through the lesson | Every interactive control is focusable with a visible focus ring. |
| Screen-reader labels | `grep -cE "aria-\|role=" <new files>` | Board squares and answer controls are labeled. **Zero is a finding**, given this is a new interaction surface. |
| Interruption is safe | Close the tab mid-answer, return | Resumes at the correct unanswered interaction with attempt history intact. |
| Latency is honest | Throttle the network | No silent hang; slow states are shown, not faked. |

---

## Lens 4 — Code and architecture

| Check | How | Bar |
|---|---|---|
| Single source of truth | `/single-source-of-truth` | No new recognizer, detector, content file, or rating-band table that duplicates an existing one. |
| Canonical authorities used | Read the imports | Lifecycle via `teaching_engine.py`'s contract; projection via `concept_mastery_service`. |
| Active-recall consolidated | `find backend -name "*active_recall*"` | Two files, both under `services/`, no bare imports, guard test present. |
| No `_id` leakage | Hit every new endpoint | MongoDB `_id` excluded or stringified. |
| No hardcoded debug | `grep -rn "move_san ==\|== 'Nf3'"` in new code | No case-specific debug in production paths. |
| Flag is real | Set it off, exercise every entry point | Default-off is a genuine no-op, not a hidden partial path. |
| Tests exist and run | `python backend/tests/test_all_flows.py`; new suites | Backend logic covered. Frontend: at least the grading/state reducer is unit-tested, given CI renders no components. |
| CI green means something | Read the workflow diff | If new checks are added `|| true`, they are decoration. |
| Migration safety | Read any backfill/migration | Backup, apply-by-`_id`, zero-change verification, reversible. |

---

## Lens 5 — Measurement and data integrity

This is where a learning product lies to itself. Highest scrutiny.

| Check | How | Bar |
|---|---|---|
| Event chain is queryable | Seed an admin journey, query it end to end | Entry source → lesson/content version → start → answer meaning → help → reveal → retry → failure exit → completion → resume → post-test → delayed recall → application, on stable identifiers, matching the UI exactly. A break here **blocks beta** (kill rule 2). |
| Triplets are difficulty-matched | Read the item-assignment code | Parallel triplets; constrained-random counterbalancing per player; no player sees a position twice; no item permanently the "post" item. |
| Cohorts are separated | Read the cohort logic | Admin verifies plumbing only. Calibration users are **excluded** from confirmatory analysis. Pool and scoring rule frozen before confirmatory starts. |
| Hints/reveals disqualify | Solve with hints, then check the record | A hinted or revealed solve cannot produce independent, retained, or applied evidence. |
| Demotion works | Fail delayed recall | `current_demonstrated_checkpoint` drops; `highest_` does not. `Refresh needed` appears. |
| Decay ≠ mastery | Read the call sites | `pattern_decay_service` may set priority; it must never write mastery. |
| Content versioning bites | Edit a FEN on an answered item | Pending attempts invalidated; history auditable under the old version. |
| History not promoted | Check a user with old puzzle attempts | Starts at Not measured. No silent optimistic migration. |
| `not measured` is real | Force a game with no eligible opportunity | Shows `not measured`, never a fabricated success or failure. |
| Denominators shown | Read any summary output | Exact denominators. No group mean used as a launch decision. |

---

## Lens 6 — Chess correctness

Nothing here is negotiable; a wrong chess claim is worse than no lesson.

| Check | How | Bar |
|---|---|---|
| Every position legal | python-chess over the served set | 100%. Not a sample. |
| Orientation correct | Render each position | Side to move matches the prompt. |
| Answers engine-verified | Query Stockfish per FEN | The taught idea is actually present. Never reason from position-intuition. |
| Valid alternatives accepted | Play a different correct move | Not rejected merely for differing from the stored move. |
| Content classes enforced | Trace where each class can be served | `Gold` only for cohorts; `Provisional` admin-only and unable to advance mastery; `Verified` never shown to a cohort. |
| Provenance exact | Read every personal-game string | Game/date/move/opponent named only when provenance is exact. Ambiguous provenance never leaks. |
| Counterexamples are real | Engine-check the negatives | Positions labeled "no fork" genuinely have none. |

---

## Lens 7 — Operations, rollout, safety

| Check | How | Bar |
|---|---|---|
| Rollout ladder honored | Read the flag/cohort code | default-off → admin → calibration → confirmatory, each with a rollback condition. |
| Kill rules implementable | Map each of the 6 stop conditions to a check | A stop condition nobody can evaluate is not a stop condition. |
| Experiment overlap resolved | Check cohort membership | Non-overlapping with Universal Habit Coach and One Surviving Instruction, per Q3. |
| Trust failure pauses exposure | Simulate an illegal position | Affected content version disabled until corrected and re-verified. |
| Local ≠ live | — | A local container rebuild is not a deploy. Nothing is "live" until it is pulled and rebuilt on the server. |
| Dirty worktree preserved | `git status` before and after | Existing staged and unrelated changes are not absorbed or overwritten. |

---

## How findings are reported

Ranked most-severe first, each with: the file and line, a concrete failure
scenario (inputs → wrong output), and whether it is CONFIRMED (reproduced) or
PLAUSIBLE (reasoned but not reproduced). Anything I could not verify is labeled
unverified rather than asserted.

**Blocking vs non-blocking.** A finding blocks if it violates a trust gate
(LES §5), trips a kill rule, produces a false teaching claim, or fabricates
evidence of learning. Everything else is ranked but non-blocking.
