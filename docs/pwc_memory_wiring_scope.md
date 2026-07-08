# PWC Memory Wiring — Audit + Connector Scope

**Date:** 2026-07-08
**Status:** DRAFT for sign-off. No new build begins until Mohit approves the connector items in §5. The flag flips in §3 already shipped today (`404e119c`) — they need only the deploy to reach users.
**Author:** Claude, after Mohit's 2026-07-08 push: *"PWC is currently feeling like a bot with just explaining moves, no teaching, no memories, no categories capture that we are tracking like forks and pins."*
**Constraint (Mohit):** *"See what is already there, don't just start from scratch."*

---

## 1. What Mohit asked for

> "Coach memory something teachable — coach memory says I am good with finding forks and I miss it, that's memory. Or if I am not good, coach guides me there. Similarly Italian opening, I don't know — the teaching part."

Two forms:

- **Strengths-as-trust:** "You're good at forks — you'll spot this one."
- **Weaknesses-as-guidance:** "You keep missing pins — slow down, look."
- **Opening memory:** "You've been in this Italian shape before — last time X happened."

Never a stat recital. Always a teaching action grounded in what the coach knows about *this* student.

---

## 2. What already EXISTS (audit before scoping)

Two full days of code exists on disk implementing versions of this. Almost none of it reached prod because the flags were never flipped.

### 2a. The player-model conductor — BUILT (`backend/services/coach_conductor.py`, 344 lines)

Per `docs/pwc_coach_conductor_scope.md`, this IS the memory layer for live coaching. It:

1. Reads `player_profiles.motif_profile` + `.motif_recognition` + `.motif_anticipation` at session start via `player_motif_threads()`. Digests to:
   - `defense`: motifs the player walks INTO (weakness)
   - `offense`: motifs the player misses / is slipping on (needs guidance)
2. Per-move `compute_motif_thread()` returns a THREAD when the current position matches the player's story:
   - **WIN callback** — you executed a motif you're normally weak at: *"Nxc7 — you found the fork. That's the pattern you've been missing — good."*
   - **MISS** — engine's best move was a motif you keep missing: *"There was a skewer here — Rd8. You keep missing these."*
   - **WALK-INTO** — you blundered into a motif that keeps catching you: *"The pin again — Nf3 lets Bg4 in. You keep walking into these."*
3. Follows the STATE-not-ASK law (no quizzes), engine-true or silent, restraint (once per motif per game), catches wins.

**Openings memory:** shipped as an addendum 2026-06-27. Recurring engine-confirmed opening mistakes fire as: *"You've been here before in the Italian."*

**Endgame recognition:** shipped. Lucena, Philidor, opposition, rule-of-square — all narrated as statements: *"That's the Lucena — your rook builds the bridge."*

Flag: `PWC_COACH_CONDUCTOR`. Was on locally, was OFF in prod until `404e119c`.

### 2b. The skill gate — SHIPPED (`backend/services/pwc_skill_gate.py`)

Per `docs/pwc_skills_aware_coaching.md`. Consults engine2 skill mastery (`coach_memory.learning.skills`). For every coaching nudge:
- **DOWNGRADE** if mastered: prepends *"You've handled this before — quick reminder."*
- **ESCALATE** if struggling: prepends *"You've missed this pattern 3 times before — let's lock it in."*
- **DEFAULT** otherwise.

Flag: `PWC_SKILL_GATE_ENABLED`. **STILL OFF in prod AND locally.** This is the biggest miss in the audit.

### 2c. The session goal + spine arc — SHIPPED

Per `docs/coaching_presence_scope.md` (§Part 1) and `docs/coaching_spine_scope.md`:

- `services/focus_bridge.py` — single reader; the "your focus this week" contract.
- `services/session_goal_service.py` — coach opens with the session's one thing.
- `MissionScoreboard` on `CoachGameSession` — tracks focus-relevant moves handled correctly.
- `services/session_greeting_service.py` — warm greeting: *"You're on day 6 of your king-safety focus. Last game you slipped on move 14 with Bxh6 — same square is under fire today."*

All wired via `focus_bridge`. No flag — always on.

### 2d. Every-move-teaches — BUILT

Per `docs/pwc_every_move_teaches_scope.md`. Un-gates the your-move caption so every move gets a teaching line, not just a good/bad chip. Flag: `PWC_EVERY_MOVE_TEACHES`. Was on locally, was OFF in prod until `404e119c`.

### 2e. The identity engine — BUILT + PRODUCES SENTENCES

Per `docs/coaching_presence_scope.md` §"Reality check." `player_identity_engine.py` + `journey_intelligence_service.py` produce narrative like:

> *"You are a cautious player whose level swings significantly between games. Most losses come from failing to convert in the endgame."*

**BUT:** siloed on the Journey page. Not consumed by PWC. This is one of the real gaps.

---

## 3. What flipped today (`404e119c`)

Docker-compose parity fix. Prod's `app` service was missing:

```
PWC_COACH_BLUNDER_GUARD=true     ← floor: no more coach queen-hangs
PWC_TEACHING_OPPONENT=true        ← mirror: coach punishes user's hangs
PWC_COACH_CONDUCTOR=true          ← the whole memory-thread layer
PWC_USE_CENTRAL_CAPTION_PIPELINE=true
PWC_CENTRAL_CAPTION_TELEMETRY=true
PWC_EVERY_MOVE_TEACHES=true       ← un-gate captions so every move teaches
MOTIF_RECOGNITION_CARD=true
```

After deploy: every user turn will fire the conductor's memory threads on motif / opening / endgame recurrences.

**Not flipped yet** (needs discussion, §5 item G below): `PWC_SKILL_GATE_ENABLED`.

---

## 4. What's genuinely MISSING — the four real gaps

After audit, only four connectors are actually absent. The rest is flag flips + one connector.

### Gap A — Concept mastery is invisible to PWC

`user_concept_understanding` tracks 17 real masteries + 5 slipping concepts for Mohit (per today's earlier audit — 60%+ clean rate filter). Named things like *"Loose king pawns — slow down"* and *"Don't move the same piece twice."* The conductor **doesn't read this collection.** It only reads the engine2 skill counters (`coach_memory.learning.skills`, 8 hand-mapped skills).

**Impact:** the coach can't say *"you keep loosening king pawns — this is that shape"* even though the mastery gate agrees Mohit slips on it.

### Gap B — Identity narrative is invisible to PWC

`player_identity_engine` outputs sentences like *"cautious player, level swings, endgame conversion losses."* Never reaches the caption door. The conductor knows motifs and openings but not the higher-level shape of who this player is.

**Impact:** the coach can't ground rare interventions in the player's identity. *"You're an attacker who rushes"* would let the coach say *"careful — this is the shape you rush in."*

### Gap C — Skill gate is off

Built, tested, sitting behind a flag no one turned on. Would immediately give every PWC nudge a "you've handled this before" or "you've missed this before" framing on the 8 hand-mapped skills.

### Gap D — 5-motif conductor coverage not verified for `discovered` + `loose`

The conductor's `compute_motif_thread` iterates `MOTIFS` which as of yesterday's commit `28ec4db9` includes `discovered` and `loose`. It should Just Work — but no test proves it fires cleanly on those two on Mohit's data. Small verify, not a build.

**Verified 2026-07-08 (probe on Mohit's account):** `player_motif_threads` picks up `loose` (offense, tier=Mastered but trending down → slipping-strength thread) and `skewer` (offense, tier=Developing → weakness thread). Fork/pin/skewer defense all populated. `discovered` doesn't yet appear because Mohit's `motif_recognition` for discovered isn't backfilled on prod yet — will appear after `backfill_motif_recognition.py --apply` runs on the server post-deploy. **Code path is correct; only the data is pending backfill.**

### Gap H — Session Teaching Queue (proactive picker, added 2026-07-08 per Mohit)

Mohit 2026-07-08: *"From the mastery skills, lab, coach can also pick up something if that's possible to show in the game to teach."*

**How this differs from A/B/C/E:** those items are REACTIVE — they fire when the user makes a mistake, walks into a motif, or plays a recurring opening pattern. Gap H is PROACTIVE: at session start, coach picks 2-3 topics from the mastery ledger + Lab and WATCHES the live game for chances to teach them — even when the user hasn't made a mistake.

**What already exists** (audit, so we don't duplicate):

- **`PedagogicalOpportunityService`** (`backend/services/pedagogical_opportunity_service.py`, 793 lines) — ALREADY BUILT. Reads user's weakness profile, at 20-30% probability per middlegame/endgame move plays a "good but not best" candidate that creates an opportunity matching one of the user's weakness types (fork/pin/skewer/hanging_piece/back_rank/king_safety/piece_activity/pawn_structure/endgame_technique). Behind `PWC_TEACHING_OPPONENT` flag (flipped on today, `404e119c`).
  - **Bug found + fixed 2026-07-08 (`get_weakness_profile` was querying `db.games` for `habits_report`, which lives on `db.game_analyses`).** Since 2026-06 the service returned `games_analyzed=0` for every user, defaulted all weakness scores to 50, and effectively fired at ~random rather than at the user's actual weaknesses. Post-fix, Mohit's profile now has 20 analyzed games backing it and `primary_weaknesses=['fork','pin','tactics']`.

- **`PositionTeachingService`** — recognizes what opening/position pattern is on the board; can offer to teach it. Not aggressively wired into PWC voice today. Reusable for the queue's position→topic matcher.

- **`focus_bridge.py`** — the one reader for "your focus this week." Already tells us the user's active weakness topic + subtype.

- **`user_concept_understanding`** — 33 mastered concepts + slipping/violating concepts, named via `PRINCIPLES` catalog. This is Mohit's exact "mastery skills" reference.

- **Lab's Coach's Pick** — best unreviewed game with headline pattern. Reusable as a "reference callback" — coach can say "remember your Tuesday game — same shape."

**What's genuinely NEW (the queue itself)** — a session-scoped picker + live matcher, ~2 days:

1. `services/session_teaching_queue.py` — pure module.
   - `pick_queue(user_id, session, active_focus) -> List[TeachingItem]`
     - Reads `user_concept_understanding` for slipping concepts (< 60% clean, ≥ 20 opportunities) + focus_bridge topic + Lab's Coach's Pick teaching moment.
     - Rating-appropriate filter (uses `RATING_BANDS`).
     - Returns 2-3 items ordered by learning priority.
   - `try_match_queue(queue, board, played_move, caption_facts) -> Optional[TeachingItem]`
     - Per move, check whether the position matches any queue item's trigger pattern.
     - Reuses existing `concept_detectors/registry.py` for the pattern match.
     - Returns the matched item or None.

2. `caption_pipeline` extension — new priority slot for Session Teaching Queue thread. Fires as a **statement + directive** (never a quiz):
   - *"Here's a chance to work on loose king pawns. Notice how h3 opens your king. Slow down here."*
   - *"Remember your Tuesday game — same Italian shape. Play it right this time."*

3. Restraint — max 2 injections per session. Reuses the conductor's `conductor_threads_pulled` state pattern (already in `CrossMoveState`).

**Why not fold into Item B (concept-mastery connector):** Item B fires when the user MAKES a concept-related mistake. Item H picks topics AT SESSION START and watches for teaching WINDOWS — no mistake required. Different triggers, complementary. Item H can reuse whatever concept-lookup Item B builds.

**Lab callback specifically:** on session start, read `/api/lab-coach-pick` for the user's Coach's Pick game. Extract its headline pattern (e.g., "you hung the queen on move 24"). Add to the queue. If a similar pattern arises in the live game, the coach references the earlier game. Feel: the coach remembers what it prescribed.

**Acceptance for H:**
- 2-3 items in the queue for any user with ≥ 15 analyzed games.
- ≤ 2 injections per game.
- Every fire is engine-verified against the position.
- No quiz language (STATE law).
- On Mohit's active session: coach picks `OP_LOOSE_KING_PAWNS` (25% clean, real weakness) into the queue; fires when the live position matches.

---

## 5. The connector work (small, well-defined)

Every item below is a wiring change or a small script. Zero new detection.

### A. `pwc_skill_gate` — flip the flag ON

**Change:** add `PWC_SKILL_GATE_ENABLED=true` to `docker-compose.yml` (local) and `docker-compose.prod.yml` (prod).
**Effort:** 5 minutes.
**Risk:** blast radius is per-move on every user's session. Rollback is the flag off. The v2 DOWNGRADE (2026-06-03) is asymmetric-cost safe — no full suppression, only prepended context.
**Blocked-on-Mohit:** yes — should confirm the map covers the openings you'd expect for your rating band before we flip.

### B. Concept-mastery connector for the conductor (`user_concept_understanding` → conductor)

**Change:** add `player_concept_threads(db, user_id)` to `services/coach_conductor.py`. Returns:
```
{
  strengths: [{concept_id, name, clean_rate_pct, opps}],   # ≥ 60% + ≥ 20 opps
  weaknesses: [{concept_id, name, clean_rate_pct, opps}],   # < 40% + ≥ 20 opps + slipping in last 10 games
}
```
Load at session start (same lifecycle as `player_motif_threads`).

**In-game usage:** extend `compute_motif_thread` (or add a sibling `compute_concept_thread`) that fires when the position matches a concept the user is weak on. Firing condition: `caption_facts.principle_id_used` or `caption_facts_principles_violated` matches a weakness concept AND the current move severity is `mistake/blunder/serious`. Statement, not question.

**Example thread:**
- Weakness (OP_LOOSE_KING_PAWNS at 25% clean): *"Careful — h3 loosens your king pawns. This is the pattern you keep missing."*
- Strength (TAC_PIN_PATTERN at 100%): silent (never nag a strength — matches the conductor's existing rule).

**Effort:** ~1 day.
**Dependency:** the concept catalog (`services.caption_principles.PRINCIPLES`) already provides human names — re-use, don't rebuild ([[feedback_single_source_of_truth]]).

### C. Identity narrative into the session

**Change:** at `CoachGameSession.start()`, load the identity engine narrative (`compute_player_identity(user_id)`). Stash as `session.player_identity_summary`. Pass into every `MoveInputs` as an optional field.

**In-game usage:** the conductor's opening/endgame/motif thread text can conditionally prepend an identity-cued lead-in. E.g., if identity says *"cautious player who rushes when winning"* AND you're in a winning position AND you played a rushed move: *"Careful — you rush in these spots. Slow down."*

**Effort:** ~1 day.
**Constraint:** identity narrative is confidence-scaled; only fire the lead-in when `confidence ∈ {high, definitive}` per the coaching_presence_scope rule *"never make a personal claim without evidence."*

### D. Verify motif conductor for `discovered` + `loose`

**Change:** add 4 scenario tests to `backend/tests/` — one MISS and one WIN for each of `discovered` and `loose`. Real FENs from Mohit's game history where the motif fired.

**Effort:** ~1 hour.

### E. Wire the openings thread beyond digest match

The openings thread today fires when the user is in a recurring engine-confirmed opening mistake pattern from their profile. Excellent for Mohit's `exf5` in Italian.

**Missing:** the STRENGTH side — when the user is in a familiar opening playing a MOVE they've handled cleanly before, catch the win. *"Bc4 — you win with the f7 strike from this shape. You've done it 8 times this month."*

**Change:** add `player_opening_wins(user_id, opening_family)` — read `motif_recognition.by_game` filtered by opening_family, report clean rates.

**Effort:** ~1 day. Small.

### F. Post-game story that reads the session's threads

`coaching_presence_scope.md` §Part 1 promises a post-game story that references the session goal. Currently: the post-game summary exists but doesn't cite which of the conductor's threads fired. Fix: at game end, read `session.conductor_threads_pulled` and thread them into the summary: *"You worked on king safety today. The coach flagged the loose-king-pawns pattern on move 12 — you caught it after that."*

**Effort:** ~1 day.
**Depends on:** the session-thread persistence (already in `caption_pipeline.CrossMoveState.conductor_threads_pulled` — verified).

### G. Skill gate flag flip decision

Same as A. Listed separately because it needs a product call: which nudges' downgrade/escalate framing do we trust today? Currently the map covers 8 skills (`defend_fried_liver`, `endgame_rule_of_square`, etc.). Any skill not mapped → default behavior (unchanged). Low-risk.

---

## 6. What NOT to build

- **Not** a new memory layer. Everything above extends existing services (conductor, focus_bridge, session_greeting_service, caption_pipeline).
- **Not** a new detection layer. All signals already computed.
- **Not** an LLM narrator. Coach voice stays deterministic + verified, same as today.
- **Not** a rewrite of `realtime_coaching_feedback.py` or `caption_pipeline.py`. New connectors plug in; no rewrite.
- **Not** the roadmap items from `coaching_presence_scope.md` §Part 2 (prediction, journal, interventions) — those are their own scope.

---

## 7. Order + effort

Ordered by feel-per-effort ratio:

1. **Ship the deploy** (`404e119c` + prior). All the flag flips reach users. **Effort: server-side, ~15 min.** Effect: coach conductor active, PWC every-move-teaches active, coach doesn't hang queens, punishes user's hangs.
2. **A. Skill gate flag flip.** Effort: 5 min diff. Effect: 8 skills' nudges get memory framing.
3. **D. Verify discovered + loose motif threads.** Effort: 1 hour. Effect: yesterday's motif work reaches the coach voice.
4. **B. Concept-mastery connector.** Effort: 1 day. Effect: coach references the 17 real masteries + 5 slipping concepts.
5. **F. Post-game story reads threads.** Effort: 1 day. Effect: session ends with a memory of what got taught.
6. **E. Opening wins side.** Effort: 1 day. Effect: coach catches the wins in Mohit's Italian history.
7. **C. Identity narrative injection.** Effort: 1 day. Effect: rare high-value identity-cued nudges.

Total: ~5 dev-days to close the gap Mohit named. Not weeks. The heavy lifting already happened; we're wiring, not building.

---

## 8. Acceptance

- **After deploy alone** (steps 1+2 above): Mohit's active session runs through the conductor. First game, at least one motif thread should fire (his defense is weak on pin/skewer per the recognition rates). Verified by tail on `[conductor]` log lines.
- **After Item B ships:** in a game where Mohit plays a move matching `OP_LOOSE_KING_PAWNS` (25% clean rate), coach fires the concept thread. Silent on strengths (TAC_PIN_PATTERN 100%).
- **After Item C ships:** in a rushed-attacking position when the identity engine has definitive confidence, the identity lead-in fires — max once per session.
- **After Item F ships:** post-game summary cites which threads got pulled and outcome.

Every acceptance line is verifiable on Mohit's own account without new data.

---

## 9. What Mohit needs to sign off

- §5 items A–G — ship this order?
- §5 G specifically — flip `PWC_SKILL_GATE_ENABLED=true` in prod on this pass, or hold for a live-check first?
- §5 C identity injection — is `confidence ∈ {high, definitive}` the right gate, or should it fire on `medium` too?
- Any of §6 that should actually be in scope?

---

_Companion memory files: [[project_coaching_presence_direction]], [[project_pwc_runs_second_engine]], [[feedback_single_source_of_truth]], [[feedback_users_remember_patterns_not_moves]]._
