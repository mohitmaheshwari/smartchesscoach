# Play with Coach — Unified Experience Data Lock

Date: 2026-09-13
Scope: `docs/play_with_coach_unified_experience_scope.md`
Production database: `chess_coach`, read-only

## Measurement boundary

The production corpus contains 484 Play with Coach session documents. Only 74 carry an explicit `game_mode`, so mode-specific decisions use those 74 sessions. They cover 18 users between 2026-07-20 and 2026-09-10, but the sample is concentrated: one user owns 44.6% of the sessions and the top three users own 68.9%. The results are strong evidence of the current system's behavior, not a causal estimate of what all future players prefer.

The baseline intentionally emitted only aggregates. No user ID, session ID, move, position, or message body was exported.

## Baseline

| Measure | Production result |
|---|---:|
| All stored sessions | 484 |
| Sessions with explicit mode | 74 |
| Explicit Coach sessions | 55 |
| Explicit Play sessions | 19 |
| Coach player moves | 221 |
| Coach stored messages | 320 |
| Coach messages per player move | 1.448 |
| Coach question messages | 32 |
| Impulse warnings | 159 |
| Coach sessions ending at two or fewer player moves | 35/55 (63.6%) |
| Coach sessions reaching ten player moves and a terminal status | 6/55 (10.9%) |
| Play sessions with at least one player move | 8/19 (42.1%) |
| Messages leaked into Play mode | 6, including 4 piece-safety nags |
| Coach sessions with canonical `coaching_context` | 5/55 |
| Coach sessions with a supporting focus | 0/55 |
| Coach sessions with a session goal | 55/55 |
| Session goals with a matched mission moment | 0/55 |
| Session color, explicit-mode sample | White 71; Black 3 |
| Time control, all sessions | `15+10` 482; `unlimited` 1; `classical` 1 |
| Time from session creation to first move | p25 2.5s; median 5.7s; p75 9.8s; p90 27.7s |
| Recorded player `time_spent` | p25 0; median 0; p75 0; p90 0 |

The canonical active-focus collection contains 53 active weakness rows for 53 users and no duplicate active weakness document per user. Forty-three rows carry both an instruction ID and instruction text. Forty-nine focuses have three runners-up, but all 151 runner records lack a detector-quality identity; the fail-closed coaching-context bridge therefore authorizes none as a supporting focus today.

## Decision locks

### DECISION LOCKED: default time control

**VALUE:** `15+10`.

**EVIDENCE:**

- 482 of 484 stored sessions use `15+10` (99.6%).
- The alternative values have one session each, which is not enough evidence to replace the established default.

**REJECTED CANDIDATES:**

- `unlimited`: one observed session and no outcome evidence.
- `classical`: one observed session and no outcome evidence.
- A new rapid or blitz default: no production comparison exists, and introducing it would confound the experience redesign.

**MEASUREMENT METHOD:** read-only frequency aggregation over all production `coach_sessions`.

### DECISION LOCKED: initial color recommendation

**VALUE:** White, with Change remaining available.

**EVIDENCE:**

- 71 of 74 explicit-mode sessions use White.
- This is treated as continuity evidence, not proof that players intrinsically prefer White, because the current interface already defaults to White and the cohort is concentrated.

**REJECTED CANDIDATES:**

- Random: no current counterfactual and it would change both onboarding and opening behavior during the same experiment.
- Black: only three observed sessions.

**MEASUREMENT METHOD:** read-only frequency aggregation over production sessions with explicit `game_mode`.

### DECISION LOCKED: unsolicited non-critical coaching cadence

**VALUE:** at most two proactive non-critical teaching messages in a rolling six player turns. Critical verified warnings and explicit “Ask coach” responses are separate. Only one message may own a turn.

**EVIDENCE:**

- The current product emits 1.448 stored messages per player move in explicit Coach sessions, contradicting the approved “most moves are quiet” contract.
- Impulse warnings alone account for 159 of 320 Coach messages (49.7%).
- The repository already carries Mohit's signed-off, empirically tuned `2 per 6` cooldown for adaptive coach-move teaching. Reusing the established density as the unified upper bound avoids inventing another cadence constant.

**REJECTED CANDIDATES:**

- Current uncapped/overlapping behavior: it produces more than one stored message per player move.
- Three per six turns: no measured learning benefit supports increasing the established cap.
- One per eight turns: that number belongs to the separate geometry-prompt distribution and cannot be generalized to all coaching.

**MEASUREMENT METHOD:** production `coach_messages` joined to explicit-mode `coach_sessions`, plus the existing locked cadence in `live_v5_teaching.py` and `memory/project_play_with_coach_phase1_design.md`.

### DECISION LOCKED: critical warning budget

**VALUE:** retain the existing maximum of three warnings per session for V1; do not create a new severity or frequency number.

**EVIDENCE:**

- The existing session schema, Guardian, and player contract already carry a three-intervention budget.
- Production recorded zero successful Guardian interventions and zero overrides in the explicit-mode sample, so the corpus cannot justify a different number.
- This is an inherited constant, not a newly inferred optimum. The rollout must measure warning opportunities, displays, overrides, abandonment, and later transfer before it can change.

**REJECTED CANDIDATES:**

- Unlimited critical warnings: violates the quiet-coach contract and removes an existing restraint.
- A new lower or higher cap: current production evidence cannot discriminate it.

**MEASUREMENT METHOD:** production field aggregation plus the current `PreMoveGuardian` and session defaults.

### DECISION LOCKED: impulse coaching

**VALUE:** no player-facing impulse or time-pressure warning in Unified V1 unless trustworthy move time is present. With today's data, the live output is disabled.

**EVIDENCE:**

- The p90 of stored player `time_spent` is zero seconds, so timing classifications are not supported by the recorded evidence.
- The invalid signal produced 159 impulse warnings, the largest message class in the Coach sample.

**REJECTED CANDIDATES:**

- Tune the “fast move” threshold: there is no valid time distribution from which to find a cliff.
- Keep the warning as-is: it asserts behavior that the system did not measure.

**MEASUREMENT METHOD:** read-only percentiles over player move-history `time_spent`, compared with message-type frequency.

### DECISION LOCKED: session focus selection

**VALUE:** Play with Coach does not rank weaknesses. It reads the primary focus and at most one quality-authorized supporting focus from `focus_bridge.build_coaching_context`.

**EVIDENCE:**

- Production has exactly one active weakness document for each of 53 focused users.
- The canonical bridge already validates one primary and at most one supporting focus.
- All 151 stored runners-up currently lack a detector-quality identity, so no secondary focus may be promoted until its existing authorization contract passes.

**REJECTED CANDIDATES:**

- Re-rank inside Play with Coach: creates a second focus system.
- Display the first runner-up regardless of quality: turns ranking residue into an unauthorized teaching claim.
- Hardcode topic choices: creates an option library that can drift from the improvement plan.

**MEASUREMENT METHOD:** read-only active-focus aggregate plus source inspection of `focus_bridge.py`.

### DECISION LOCKED: mode treatment

**VALUE:** no hidden default session. The player explicitly chooses Play with Coach or Play a Game. Coach is the primary CTA; Play is the quiet alternative.

**EVIDENCE:**

- The explicit-mode corpus contains 55 Coach and 19 Play sessions, but mode choice is too concentrated to infer a universal preference.
- Six messages leaked into Play sessions, proving that mode isolation must be a correctness invariant rather than another scoring threshold.

**REJECTED CANDIDATES:**

- Three visible evidence modes: they expose an internal measurement distinction as product terminology.
- Auto-start Coach mode: prevents informed selection and makes setup conversion impossible to measure honestly.

**MEASUREMENT METHOD:** read-only mode and message aggregation over explicit-mode sessions.

## Locks deliberately not made

- No retention-lift target is invented from 18 concentrated users.
- No learning-effect target is inferred from session completion; the current mission scoreboard recorded zero matched moments.
- No timing threshold is set while the move timer is invalid.
- No supporting focus is shown until the existing detector-quality authorization can identify one.
- No new focus-ranking formula is added to Play with Coach.
