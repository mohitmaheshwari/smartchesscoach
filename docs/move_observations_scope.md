# Move Observations Layer — Scope

**Status:** Drafted 2026-06-29, awaiting Mohit's signoff before backfill runs.
**Author:** session with Claude.
**Related:** [docs/email_page_contract.md](email_page_contract.md), [CLAUDE.md "Email → Page Contract" section](../CLAUDE.md).

---

## TL;DR

We're sitting on rich per-move data that the analyzer already produces (cognitive_gap, CCT discipline, concept_applied, shape_pattern_id, is_critical, is_brilliant, etc.) — but the coaching layer only consumes a tiny slice of it. **Today: ~32% of user moves get one tag (cognitive_gap). The rest is thrown away.**

This scope introduces a `move_observations` collection that derives 10-15 behavioral tags per user move using ONLY fields that already exist in `stockfish_analysis.move_evaluations` and `decryption_v5_data`. **No new analyzer work. No new data collection.**

After this ships, every user move has a structured behavioral record. Every "what does this user understand?" question becomes a query, not an inference.

---

## Why it exists

### The current state (after today's cognitive_gap fixes)

| Surface | What it uses | What's missing |
|---|---|---|
| `player_profiles.top_weaknesses` | cognitive_gap counts per category (9 cats) | Doesn't separate fork-blindness from pin-blindness from skewer-blindness — all lumped into `missed_tactic`. Only fires on bad moves. Zero info on what the user DOES well. |
| `player_identities.style_profile` | brilliant+sacrifice rates | Single number per user; no per-move detail |
| Decryption v5 captions | Per-move LLM commentary | One-off per game; not aggregated into a behavioral record |
| Email "you missed forks 29 times" | profile.top_weaknesses | Wrong granularity (forks ≠ pins ≠ skewers ≠ discovered attacks — all collapsed) |

### What Mohit asked for (the reframe)

> "each move should have tags, and that user based contextual tags, good moves also tell you about user's understanding of game, finding opportunity, and what not, you already can understand from this, also opponent moves are very important for understanding user games."

The current model treats `cognitive_gap` as a **weakness flag** — only fires when something went wrong. The new model treats observation as **continuous** — every move tells us something, and the opponent's previous move is part of the context for what the user faced.

### Why not just keep extending cognitive_gap?

Because:
1. `cognitive_gap` is a name with a fixed semantic ("gap" = failure). Adding "you played a good fork" to a field called `cognitive_gap` is semantically broken.
2. Schema drift risk — if every reader of game_analyses has to re-derive observations from raw fields each time, we'll keep getting the bugs we audited today.
3. A derived collection means we can index it and query coaching questions in milliseconds, instead of scanning move_evaluations.

---

## What it produces (the data model)

One document per user move (opponent moves do NOT get their own observation — they're baked into the next user move as `opponent_previous`).

```json
{
  "_id": ObjectId,
  "user_id": "user_xxx",
  "game_id": "game_yyy",
  "move_number": 14,
  "ply": 27,
  "color": "white",
  "derived_at": ISODate,
  "schema_version": 1,

  // ---- The position they faced ----
  "fen_before": "...",
  "phase": "middlegame",                    // opening | middlegame | endgame
  "was_critical_moment": true,              // from is_critical

  // ---- What the opponent did right before (context) ----
  "opponent_previous": {
    "move_san": "Ng4",
    "created_threat": true,                 // cct_creates_threat on prev move
    "was_capture": false,
    "was_check": false,
    "blundered": false,                     // prev move evaluation == "blunder"
    "cp_loss": 30                           // prev move's cp_loss (theirs, not user's)
  },

  // ---- What the user played ----
  "move_san": "Nxe4",
  "move_uci": "g6e4",
  "execution_quality": "blunder",           // best/excellent/brilliant/good/inaccuracy/mistake/blunder
  "cp_loss": 250,
  "eval_before": 100,                       // pawns × 100; positive = user winning
  "eval_after": -150,
  "was_forcing": true,
  "was_check": false,
  "was_capture": true,
  "was_castle": false,

  // ---- What the user did RIGHT (positive observations) ----
  "concept_used": null,                     // bishop_development | center_control | knight_development | ...
  "tactical_pattern_executed": null,        // free_piece | fork | pin | skewer | ...
  "responded_to_threat": false,             // opponent_previous.created_threat AND user move addressed it
  "punished_opponent_blunder": false,       // opponent_previous.blundered AND user move was best/excellent
  "found_best_in_critical": false,          // was_critical_moment AND execution_quality == best

  // ---- What the user MISSED (gap observations) ----
  "missed_pattern": "missed_tactic",        // from cognitive_gap; null if move was fine
  "missed_free_piece": false,               // shape_pattern_id == "free_piece" AND user didn't play it
  "ignored_opponent_threat": true,          // opponent_previous.created_threat AND NOT responded_to_threat
  "missed_opponent_blunder": false,         // opponent_previous.blundered AND user move wasn't best/excellent

  // ---- Decision style ----
  "decision_register": "wrong_register",    // forcing_when_best_was_forcing | quiet_when_best_was_quiet | wrong_register

  // ---- One-line coaching takeaway (generated from above) ----
  "coaching_takeaway": "Ignored opponent's knight fork setup and walked into the trap"
}
```

### What this enables that we can't do today

| Question coach wants to ask | Today | After this ships |
|---|---|---|
| "Does Shobhit respond to threats?" | Unknown | `db.move_observations.aggregate([{$match:{user_id, opponent_previous.created_threat:true}}, {$group:{_id:null, responded:{$sum:{$cond:['$responded_to_threat',1,0]}}, total:{$sum:1}}}])` |
| "Does Mohit punish opponent blunders?" | Unknown | Same shape, filter on `punished_opponent_blunder` |
| "Does Shobhit specifically miss FORKS vs PINS?" | No — collapsed into `missed_tactic` | Yes, via `tactical_pattern_executed` + `missed_pattern` granularity |
| "Which user moves are exemplary teaching positions?" | Unknown | Filter `concept_used != null AND execution_quality == best` |
| "What does Shobhit do RIGHT?" (positive coaching) | Nothing — only weakness signal | `concept_used`, `punished_opponent_blunder`, `responded_to_threat`, `found_best_in_critical` counts |
| "Which moments belong on the 3-Moments page for this user?" | Custom filter per topic | Indexed query against `move_observations` with filter |

---

## What's out of scope for v1

To ship fast, the v1 explicitly does NOT do:

1. **Finer tactical sub-types from the raw board.** If `cognitive_gap == "missed_tactic"`, we tag `missed_pattern: "missed_tactic"` — we don't (yet) inspect the FEN to determine if it was specifically a fork vs pin vs skewer. That's a v2 enrichment via python-chess board analysis. For now, the granularity matches what the analyzer already gives us.
2. **Opponent intent / strategic plan.** We tag what opponent's move DID (created threat, captured, blundered), not what they were planning. Inferring intent is hard and unreliable.
3. **Time-pressure context.** We won't use `move_time_stats` in v1. That's a separate enrichment (good v2 candidate).
4. **Opponent rating / time control context.** Same — separate enrichment.
5. **A new analyzer phase.** This is purely derivation from already-stored fields. No analyzer change. No re-Stockfish.

---

## Derivation rules (the contract)

For each analyzed game's `stockfish_analysis.move_evaluations`:

```python
for i, mv in enumerate(move_evaluations):
    if mv.get("is_opponent_move"):
        continue  # opponent moves don't get their own observation

    # Look back at opponent's previous move (if exists)
    prev = move_evaluations[i-1] if i > 0 else None
    opponent_previous = build_opponent_previous(prev)  # {created_threat, blundered, ...}

    # Look forward NOT NEEDED for v1 — observation is point-in-time

    obs = {
        # straightforward field copies / lookups
        "phase": classify_phase(mv["move_number"]),
        "execution_quality": mv.get("evaluation"),
        "cp_loss": mv.get("cp_loss"),
        ...

        # cross-move derivations
        "responded_to_threat": (
            opponent_previous and opponent_previous["created_threat"]
            and mv.get("evaluation") in ("best", "excellent", "good")
            and mv.get("cp_loss", 0) < 50
        ),
        "ignored_opponent_threat": (
            opponent_previous and opponent_previous["created_threat"]
            and (not _met_responded_threshold(mv))
        ),
        "punished_opponent_blunder": (
            opponent_previous and opponent_previous["blundered"]
            and mv.get("evaluation") in ("best", "excellent", "brilliant")
        ),
        ...

        # decision register from cct fields
        "decision_register": _classify_register(mv),
    }

    yield obs
```

Full table of derivations: every field above maps to one of (a) direct field copy, (b) cross-move computation using the move at `i-1` and `i`, or (c) classification from cct fields. **No FEN inspection needed in v1.**

---

## Collection design

```
Collection: move_observations
Indexes:
  - (user_id, derived_at)              ← per-user recent queries
  - (game_id, move_number)             ← per-game lookup
  - (user_id, missed_pattern)          ← weakness aggregation
  - (user_id, concept_used)            ← strength aggregation
  - (user_id, was_critical_moment)     ← critical-moment retrieval (used by /coach/moments)
  - (user_id, opponent_previous.created_threat, responded_to_threat)  ← "do you see threats?"

Document size: ~500 bytes per move
Per game: ~25 user moves = ~12 KB
9,572 analyses × ~12 KB ≈ 115 MB total

Replacement policy: drop + re-derive whenever the deriver logic changes
(schema_version bump). Read-only consumers; never user-mutated.
```

---

## Success criteria

A v1 ship is successful if:

1. ✅ The derivation runs against all 9,572 game_analyses without error.
2. ✅ For 100 randomly-sampled moves, the derived `coaching_takeaway` is human-coherent (sanity check).
3. ✅ For Mohit + Shobhit, the new collection's per-user aggregates match the existing `top_weaknesses` numbers within ±10% (sanity check — we're using the same source data, just structured differently).
4. ✅ `/coach/moments/<topic>` endpoint can be rewritten to query `move_observations` directly instead of scanning `stockfish_analysis.move_evaluations` — and returns the same moments.

---

## What it unlocks downstream

After ship:

| Downstream | Becomes possible |
|---|---|
| Email content | "I noticed you respond to opponent's threats 89% of the time, but you miss free pieces 1 in 4 times" — direct query, no guessing |
| `/coach/moments` filters | Indexed queries; ~50ms instead of scanning hundreds of analyses |
| Weakness picker (Theme 3) | Has 30+ tag dimensions to prioritize on, not 9 |
| "What you did well this week" cards | Possible for the first time (positive signals exist) |
| Spaced repetition queue (Theme 3) | Can target specific observation patterns ("user missed free_piece 4 times — queue 3 free-piece puzzles") |
| Peer comparison (Theme 4) | "Players who improved their `ignored_opponent_threat` rate by 50% saw N rating points" |

---

## Implementation plan (phases)

### Phase 0 — Scope signoff (this doc)
Mohit reads, asks questions, signs off or pushes back. **No code committed yet.**

### Phase 1 — Derivation module (1 day)
Pure Python, no DB writes:
- `backend/services/move_observation_deriver.py`
- `derive_observations_for_game(stockfish_analysis_doc) -> list[dict]`
- Unit-testable in isolation (passes a game dict, gets observations).

### Phase 2 — Sample run + visual review (1 hour, requires SSH tunnel)
Run deriver on Mohit's most recent analyzed game. Print all observations. Read them — do they make coaching sense? Iterate the deriver if not.

### Phase 3 — Backfill script (half day)
- `backend/scripts/backfill_move_observations.py`
- Dry-run default, --apply writes
- Idempotent (re-running overwrites by (game_id, move_number))
- Progress bar (9,572 games)
- Estimated runtime: ~10-15 min on a single thread

### Phase 4 — Wire to analyzer for new games (half day)
- Inside `analysis_worker.process_job()`, after the Stockfish phase, call `derive_observations_for_game()` and upsert results.
- Marks the doc with schema_version so future re-derivations can skip up-to-date games.

### Phase 5 — First downstream consumer (1-2 days)
Rewrite `moments_topic_registry._filter_piece_safety_in_winning_position()` to query `move_observations` directly. Verify same results. Then we know the layer is real.

### Phase 6+ — All other consumers migrate gradually
Profile aggregator, weakness picker, email generator. **Not blocking; each can adopt at its own pace** since old code still works on raw `move_evaluations`.

---

## Risks & open questions

| Risk | Mitigation |
|---|---|
| `cognitive_gap` is only populated for ~32% of user moves (today). The observations layer will inherit that sparsity — `missed_pattern` will be null on the rest. | Acceptable for v1. The OTHER tags (`responded_to_threat`, `punished_opponent_blunder`, `decision_register`, `concept_used`) fire independently and cover the rest. |
| `decryption_v5_data` is not on every analysis. Some old games have only `stockfish_analysis`, no v5 decryption. | v1 deriver works from `stockfish_analysis.move_evaluations` only. If v5 fields are present, we use them as bonus. |
| Schema drift: the deriver depends on field names in stockfish_analysis. If the analyzer ever renames a field (like `is_user_move` → `is_opponent_move` did), the deriver silently produces null tags. | Add a CI/smoke test that runs the deriver on a known game and asserts specific tag values. Will catch field renames immediately. |
| 115 MB extra storage | Acceptable. MongoDB can handle it. |
| **What if the deriver disagrees with `top_weaknesses` by more than 10%?** | Strong signal of a bug. Halt before backfill. Diagnose. |

### Open questions for Mohit

1. **Do we keep `top_weaknesses` after this ships?** I'd recommend deprecating it after Phase 5 — `move_observations` aggregates can replace it. But if any frontend code reads `top_weaknesses` directly, we need to coordinate.
2. **Should opponent moves get their own observation documents, or stay baked into the next user move?** v1 design is "baked in" (more compact, easier to query "user response to opponent X"). v2 could split if there's demand.
3. **schema_version bump policy.** If we change a derivation rule, do we re-derive ALL or just new games? v1: re-derive all (simple, takes 15 min).

---

## What you're signing off on

1. **The data model above** (~25 fields per observation).
2. **The derivation rules** (point-in-time, no FEN inspection in v1).
3. **The collection design** (one doc per user move, indexed for the common queries).
4. **Phase 1 + Phase 2 + Phase 3 + Phase 4 ship in this sprint** (~3 days total).
5. **Phase 5 is the proof-of-value** — rewrite `/coach/moments` to use the new layer.
