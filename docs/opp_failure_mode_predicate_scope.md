# Opp-Side Failure-Mode Predicate Framework — Scope Document

**Status:** AWAITING MOHIT SIGNOFF (2026-06-06)
**Skill applied:** `/scope-driven-development` (with Section 0 existing-surfaces audit)
**Triggered by:** `fb_4899b11157fa` engine-verification revealing the predicate-vs-override gap
**Predecessor backlog:** [CAPTION_BACKLOG.md item 7](../CAPTION_BACKLOG.md) — concrete framework sketch
**Next skills:** `/audit-pre-code` before first file

---

## 0. Existing surfaces audit

### What exists today

| Surface | What it does | File |
|---|---|---|
| **User-side failure-mode framework (v100)** | When user plays a mistake, R12_blunder.json's `failure_mode_clauses_user` array picks a concrete failure clause (e.g. `failure_walks_into_check`, `failure_allows_fork`, `failure_allows_recapture`, `failure_allows_capture`) before promoting an alternative. Drives the "{played} {failure_clause}. {best_move} was better — {why_clause}" caption shape. | [`backend/data/captions/R12_blunder.json`](../backend/data/captions/R12_blunder.json) lines 185-202 |
| **User-side failure-mode facts** | Computed in caption_facts.py: `opp_reply_san_is_check`, `opp_reply_creates_fork`, `opp_reply_recaptures_on_played_square`, `opp_reply_captures_piece_type`, `is_exchange_losing`, `opp_reply_attacks_played_piece`, `pieces_now_undefended_present`. | [`backend/services/caption_facts.py`](../backend/services/caption_facts.py) (opponent-reply section ~line 4877) |
| **Opp-side why-clauses** | When OPPONENT plays a mistake, R12's `why_clauses_opp` array picks a clause focused on USER'S RESPONSE (`why_opp_punish_capture`, `why_opp_user_finds_mate`, `why_opp_user_attack_with_tempo`, etc.) | R12_blunder.json lines 208-228 |
| **Opp-side fallback (bare template)** | When no concrete why-clause activates, falls to bare `"Opponent's {played_san} {severity_phrase}."` shape — sometimes followed by a user_best_reply_san if available. | caption_pipeline.py line 3066-3067 |
| **Authoring override layer** | Per-(game_id, move_number, move_san) prose replacement. Tonight's 22-row apply handles specific positions Parth flagged. | `authored_caption_overrides` collection |

### The gap

There's a **user-side failure-mode array** (good — `failure_mode_clauses_user`) but **no opp-side parallel** (`failure_mode_clauses_opp` doesn't exist). Result: when opponent makes a mistake, the system can only tell the user what THEY should do (`why_opp_punish_*`) — never what OPPONENT actually missed.

Concrete failure case from this morning: `fb_4899b11157fa` — Black plays Nbd7 (severity opp_mistake, cp_loss=166). Engine truth: Black's best move was Qxd4 grabbing the free d4 pawn. The current caption renders "Opponent's Nbd7 is a mistake. Play O-O." — accurate on what user should do, silent on what opp missed (the free pawn).

The authoring-override pipeline can patch specific positions but **doesn't generalize**. The next opp_mistake position not in any override falls back to the same bare template.

### Decision

**EXTEND** the existing R12 architecture by mirroring the user-side failure-mode framework on the opp side. Same structural pattern, different facts, parallel array.

NOT PARALLEL — that would create a separate caption surface for opp moves, breaking the "one source of truth" rule.
NOT REPLACE — the existing opp why-clauses (focused on user's response) are still useful and shouldn't be removed.

---

## 1. What it is

When opponent makes a mistake, the caption explains **what opponent missed** in addition to **what the user should do** — pulling teaching value from the position's chess truth rather than relying on per-position authored overrides.

In plain English: if the engine sees that opponent's best move was Qxd4 winning a pawn, and opponent played Nbd7 instead, the caption should name that miss. Today it doesn't. After this ships, it does.

---

## 2. What the user sees

### Before (today, `fb_4899b11157fa`)

```
Opponent's Nbd7 is a mistake. Play O-O.
```

### After this scope ships

```
Opponent's Nbd7 missed the free pawn on d4 — Qxd4 would have grabbed it cleanly. 
Play O-O — secure your king before pressing further.
```

### Pattern in general

```
Opponent's {played_san} {opp_failure_clause}. {user_response_clause}
```

Where `opp_failure_clause` is selected from a new array based on which opp-side facts fire. Initial set of three:

| Variant | Fires when | Renders as |
|---|---|---|
| `opp_failure_missed_capture` | opp's best_move is a capture winning material ≥ pawn | "missed the free {captured_piece} on {target_square} — {best_move_san} would have grabbed it" |
| `opp_failure_missed_mate` | opp's best_move was a forced mate sequence | "missed forced mate in {N} starting with {best_move_san}" |
| `opp_failure_quiet_when_threatened` | opp had a piece/square under attack and played a non-defending quiet move | "ignored the attack on {threatened_piece} at {threatened_square} — {best_move_san} was the defensive line" |

---

## 3. In scope (V1)

- New fact group in `caption_facts.py`: `opp_failure_*` facts (~3-4 fields total)
- New array `failure_mode_clauses_opp` in `R12_blunder.json` mirroring `failure_mode_clauses_user`
- 3 initial variants (the 3 in the table above)
- New wrapper variants `opp_with_failure_and_response` (parallel to `user_with_failure_and_alternative`)
- Threading through `caption_rules.py` _r12 builder
- One unit test per variant verifying the failure clause fires on the right positions

V1 ships behind no flag — it's an additive enrichment of existing opp captions. Risk surface: low (only fires when concrete facts activate; bare-template fallback stays for cases where no opp_failure_* fact fires).

---

## 4. Explicitly out of scope (V1)

- **Positional/strategic opp failure modes** (e.g. "opp's move blocked their own bishop" — the bishop-block claim I made for Nbd7 that turned out to be secondary). These require positional evaluation predicates that don't exist; defer to V2.
- **Opp-side curriculum captions** (e.g. "opp's setup deviated from main-line Caro-Kann"). Out of scope.
- **Severity-band tuning** — if opp_mistake severity is wrong at cp_loss 50-100, that's a separate cliff problem (CAPTION_BACKLOG item 9).
- **The defensive-piece-trade case** (`fb_9c4ad043240b` Nxg3) — engine-truth on whether trading a defensive piece is a mistake needs a different predicate (piece-activity loss); separate V1.1 work.
- **More than 3 initial variants** — additional shapes (sacrifice-missed, exchange-gain-missed, etc.) added as concrete examples accumulate.
- **PWC integration** — same separation as v100: this is the central pipeline; PWC integration is the PWC migration's job ([docs/pwc_central_caption_migration.md](pwc_central_caption_migration.md)).

---

## 5. Success criteria

**Primary:** for the 4 known opp_mistake test cases (`fb_44ab295462d0` cxd5, `fb_771714e55f1f` c3, `fb_9c4ad043240b` Nxg3, `fb_4899b11157fa` Nbd7), running the central pipeline produces a non-empty `opp_failure_*` clause for at least 3 of them.

This is a corpus-level correctness criterion, not a usage metric. The "did it work?" question is "does the predicate fire on the cases that motivated it?"

**Secondary tracked:**
- Of all opp_mistake / opp_blunder fires across the analyzed-games corpus, what % activate an `opp_failure_*` clause (vs falling back to bare template)? Target: ≥40% within 1 week post-deploy.
- Authoring-override pipeline pass rate on opp_mistake submissions — should DROP (since the system now handles more cases automatically; fewer need overrides).
- Flag rate on opp_mistake captions — should hold or improve (no regression from over-firing wrong predicates).

**Explicitly NOT a success metric:**
- "Users say opp captions feel smarter" — subjective.
- "Fewer 'no WHY' feedback flags" — would be confounded by other coverage work.

---

## 6. Open questions

### Q1. Where is `best_move_san` computed for opp moves?

The probe confirmed Stockfish returns `Qxd4` as best for the Nbd7 position. The fact is computed in `analysis_worker.py` at game analysis time. But: is it threaded through to `caption_facts.py` for opp moves the same way it is for user moves?

- **Why unresolved:** I haven't traced the wiring. The `MoveInputs.best_move_san` field exists; whether it's populated for opp moves needs verification.
- **Unblocking step:** grep the analysis pipeline; verify with a probe on stored `decryption_v5_data` for a known opp_mistake game.

### Q2. What's the captured-piece-value floor for `opp_failure_missed_capture`?

If opp could have captured an undefended pawn but played a slightly-better-positional move (cp_loss=20), is that a "missed capture" worth captioning? Probably not — the move was MARGINALLY better, not winning material.

- **Why unresolved:** depends on cp_loss distribution of "missed pawn capture" cases.
- **Unblocking step:** floor at pawn value initially. Refine via `/lock-via-data` probe after deploy.

### Q3. Should `opp_failure_quiet_when_threatened` fire when the user can't actually punish the threat?

If opp ignored an attack on their bishop, but user has no good way to capture it (defended), saying "opp ignored the attack" reads weird.

- **Why unresolved:** edge case; need to define the gate.
- **Unblocking step:** add `AND threat_is_punishable_by_user` to the predicate. Verify via test cases.

---

## 7. Pre-code requirements

- [ ] Q1 traced — confirm `best_move_san` reaches `caption_facts.py` for opp moves
- [ ] Q2 floor decided — likely pawn (cp_loss ≥ 100 for a missed capture)
- [ ] Q3 gate decided — punishable-by-user check
- [ ] Test corpus identified — the 4 known feedback positions used as initial test cases
- [ ] V5_COACHING_VERSION bump plan (107 → 108 after ship)
- [ ] Mohit explicit signoff on this scope document

After all gates pass: `/audit-pre-code` runs as final check, then implementation begins.

---

## Appendix A — what gets built (descriptive, not part of scope contract)

**Backend changes:**

`caption_facts.py`:
- New section ~line 4900 (parallel to existing opp_reply_* extraction): `opp_failure_*` fact computation
- Inputs: `mover_is_user`, `severity`, `best_move_san`, `board_before`, `played_move`
- Outputs: `opp_failure_missed_capture` (bool), `opp_missed_capture_san`, `opp_missed_capture_piece_type`, `opp_missed_capture_square`, `opp_failure_missed_mate` (bool), `opp_missed_mate_moves`, `opp_failure_quiet_when_threatened` (bool)
- ~80 lines of fact extraction

`R12_blunder.json`:
- New array `failure_mode_clauses_opp` after `failure_mode_clauses_user`
- New variants: `opp_failure_missed_capture`, `opp_failure_missed_mate`, `opp_failure_quiet_when_threatened`
- Updated `select_variant` to include `opp_with_failure_and_response` shape

`caption_rules.py`:
- Thread the new facts into `_r12_render` (4 new key/value lines in the facts dict)

**Tests:**
- One unit test per variant using fixed FENs from the 4 known feedback positions
- Verify the failure clause fires on the right positions, doesn't fire on positions where the predicate shouldn't

**Estimated implementation time:** 3-5 hours including testing. NOT half a day.

---

This appendix is descriptive. Sections 0–7 are the contract.
