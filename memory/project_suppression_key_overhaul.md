---
name: suppression-key-overhaul
description: Phase 0.5 — replace the current Set[principle_id] / once_per_game suppression with state-based keys. Same principle fires again when the board state meaningfully changes. Mohit signoff 2026-05-18 — this lands BEFORE Play-with-Coach Phase 1.1 because live teaching must not ship on the blunt suppression that the V5 review surface already complains about.
metadata:
  type: project
---

## Why this exists

The current V5 wiring layer suppression (game_decryption_v5_service.py:3186-3218) does two things:
1. `once_per_move` (default) — no game-state filter
2. `once_per_state_entry` AND `once_per_game` — collapsed identically into "fire exactly once per game-record, ever"

That collapse was an honest punt acknowledged in the code comment:
> "Audit #2 reveal: once_per_state_entry's 'fire when not in last-move set' semantics leak on alternating sides — END_KING_ACTIVE checks the MOVER's king, so the OTHER side's move 'breaks' the last-move-set membership, and the next own move re-fires. For sub-1500 teaching, the cue is needed once per game anyway. Collapse state_entry → game-level suppression."

For review-time captions, this collapse mostly worked. For live Play with Coach it breaks two ways:
- Cross-game spam: the audit run showed `10c19d0c` with 4 raw OPPOSITION fires across moves 31, 37, 39, 41 — same Kf2 best move, same king pair. User would see 4 identical "Take the opposition" messages if naively surfaced.
- Cross-game silence: in a long game where the SAME principle applies twice with materially different king geometries, the second fire is silenced even though it's a different lesson.

Mohit's spec (2026-05-18): suppression must be STATE-based, not principle-only. The same principle CAN fire again if the board state meaningfully changed.

## Design

### Suppression key (per detector fire)

A composite key built from the principle hit:

```
state_key = (
    principle_id,          # "END_OPPOSITION"
    phase,                 # "opening" / "middlegame" / "endgame"
    intent_type,           # "defensive_geometry" / "tactical_attack" /
                           # "material_safety" / "positional_squeeze" /
                           # "development" / "king_safety"
    focal_squares,         # tuple of squares the principle is centered on
    involved_piece,        # piece type (or "king" / "pawn" specifically)
    best_move_family,      # "K_move" / "pawn_break" / "developing_minor" /
                           # "trade" / "rook_lift" / "blockade" / ...
)
```

Each detector knows its own state. Detectors emit `state_key` as part of their evidence return. V5 wiring uses (principle_id, state_key) tuples for suppression checks instead of bare `principle_id`.

### Suppression policy declarations (per principle in caption_principles.py)

Three policies replace the current two:

| Policy | Behaviour | Use when |
|---|---|---|
| `once_per_move` | No game-state filter; default | Stateless principles (single-move tactical claims) |
| `once_per_state_key` | Fires until state_key changes | State-driven principles where same lesson recurs in same shape (RULE_OF_SQUARE, OPPOSITION, HANGING_PIECE, PIN, FORK, etc.) |
| `once_per_game` | Fires exactly once across the whole game-record | One-time concepts (Castle by move 12, "Develop fully before attacking" — once is enough) |

### Re-arm conditions (implicit)

A principle "re-arms" automatically when ANY component of its state_key changes. Mohit's enumerated triggers map cleanly:

| Trigger | Maps to |
|---|---|
| best move family changes | `best_move_family` component flips |
| target square changes | `focal_squares` differs |
| pawn race begins | new principle (different `principle_id` family) |
| new passed pawn appears | `focal_squares` changes (new pawn square) |
| opposition geometry changes | `focal_squares` differs (new king pair) |
| phase transition | `phase` flips (e.g., middlegame → endgame) |

Eval-swing-based re-arm is NOT part of the key (deliberately) — eval is a presentation-layer concern, not a state definition. A principle on the same geometry is the same principle whether you're at +50cp or -50cp.

### Hashability

`state_key` is a tuple of hashable atomics. `focal_squares` is itself a tuple (sorted for stability). Whole key is hashable → goes into a Python `set`.

## Detector return shape change

Today's detector return:

```python
return {
    "principle_id": "END_OPPOSITION",
    "evidence": {...},
    "engine_endorsement": "best",
    "aligned_moves_offered": [...],
}
```

After Phase 0.5:

```python
return {
    "principle_id": "END_OPPOSITION",
    "evidence": {...},
    "engine_endorsement": "best",
    "aligned_moves_offered": [...],
    "state_key": (
        "END_OPPOSITION",
        "endgame",
        "positional_squeeze",
        ("e4", "f2"),       # your_king_should_move_to + their_king_square
        "king",
        "K_move",
    ),
}
```

Detectors emit `state_key` based on their own evidence fields. Each principle's state-key composition is documented per-detector.

## V5 wiring change

`game_decryption_v5_service.py` lines 3186-3218 logic becomes:

```python
state_keys_fired_this_game: Set[Tuple] = set()
principles_fired_this_game: Set[str] = set()
...
for _ev in raw_principles:
    _pid = _ev.get("principle_id")
    _entry = _CAPTION_PRINCIPLES_BY_ID.get(_pid, {})
    _suppress = _entry.get("suppress", "once_per_move")

    if _suppress == "once_per_game":
        if _pid in principles_fired_this_game:
            continue
    elif _suppress == "once_per_state_key":
        _state_key = _ev.get("state_key")
        if _state_key is None:
            # detector hasn't emitted state_key — fall back to once_per_game
            if _pid in principles_fired_this_game:
                continue
        else:
            if _state_key in state_keys_fired_this_game:
                continue
            state_keys_fired_this_game.add(_state_key)
    # once_per_move (default) → no filter

    caption_principles_violated.append(_ev)
    principles_fired_this_game.add(_pid)
```

Backward-compat: detectors without `state_key` degrade gracefully to once_per_game semantics.

## Per-principle migration plan

For Phase 0.5 we MIGRATE the principles that benefit most. The rest stay on `once_per_move` (default) or `once_per_game` (final) as appropriate.

| Principle | Current `suppress` | New `suppress` | state_key composition |
|---|---|---|---|
| END_RULE_OF_SQUARE | once_per_state_entry | once_per_state_key | (pawn_square, promotion_square, king_should_move_to, "K_move") |
| END_OPPOSITION | once_per_state_entry | once_per_state_key | (your_king_should_move_to, their_king_square, opposition_kind, "K_move") |
| END_KING_ACTIVE | once_per_state_entry | once_per_game | one-time lesson per game (Mohit's collapse comment was right for this one) |
| END_ROOK_BEHIND_PASSER (Phase 4) | (n/a yet) | once_per_state_key | (rook_square, passer_square, "rook_move") |
| END_PASSED_PAWN | (n/a registered) | once_per_state_key | (pawn_square, "push_or_support") |
| TAC_HANGING_PIECE | once_per_move | once_per_move | unchanged — every move that hangs a piece is its own lesson |
| TAC_PIN_PATTERN | once_per_move | once_per_move | unchanged — every alignment is its own lesson |
| TAC_FORK_PATTERN | once_per_move | once_per_move | unchanged |
| TAC_SKEWER_PATTERN | once_per_move | once_per_move | unchanged |
| TAC_BACK_RANK | once_per_move | once_per_move | unchanged — fires once per real back-rank threat |
| TAC_DISCOVERED_PATTERN | once_per_move | once_per_move | unchanged |
| OP_QUEEN_OUT_EARLY | once_per_state_entry | once_per_game | one-time lesson per game |
| OP_NOT_CASTLED | once_per_state_entry | once_per_game | one-time |
| OP_KNIGHT_ON_RIM | once_per_state_entry | once_per_game | one-time |
| OP_BISHOP_BLOCKED | once_per_state_entry | once_per_state_key | (bishop_square, blocking_pawn_to) — different bishop / different blocker = different lesson |
| OP_LOOSE_KING_PAWNS | once_per_state_entry | once_per_game | one-time |
| OP_ROOK_OPEN_FILE | once_per_state_entry | once_per_state_key | (rook_square, target_file) |
| OP_FINISH_DEVELOPMENT | once_per_state_entry | once_per_game | one-time |
| OP_NEW_PIECE_EACH_TURN | once_per_state_entry | once_per_game | one-time |
| OP_CENTRE | once_per_state_entry | once_per_game | one-time |
| OP_TRADE_ATTACKERS | once_per_state_entry | once_per_state_key | (attacker_square, defender_square) — different attacker pair = different lesson |
| DEF_WALK_KING | once_per_state_entry | once_per_state_key | (king_square, target_square) |
| MID_BAD_BISHOP | once_per_state_entry | once_per_state_key | (bishop_square,) — different bishop = different lesson |
| TAC_DEFENDER_COUNT | once_per_move | once_per_move | unchanged |
| TAC_CHECKS_CAPTURES_THREATS | once_per_move | once_per_move | unchanged |
| MID_KING_SAFETY | once_per_state_entry | once_per_state_key | (king_square, weakness_type) |
| MID_KEEP_ATTACKERS | once_per_move | once_per_move | unchanged |
| DEF_TRADE_ATTACKERS | once_per_state_entry | once_per_state_key | (target_square, attacker_square) |

Shape patterns (24, TIER 3) — separate migration in a follow-up commit. They use a different suppression layer (line 2773+ in V5 service). Same principle applies.

## What ships in Phase 0.5

1. State_key infrastructure: `_freeze_state_key` helper, V5 wiring update, backward-compat fallback.
2. Migration of the four endgame principles (RULE_OF_SQUARE, OPPOSITION, KING_ACTIVE, PASSED_PAWN) since those are the ones I just shipped and they're the ones with multi-fire-per-game patterns I've actually verified.
3. Migration of OP_NOT_CASTLED, OP_QUEEN_OUT_EARLY, OP_FINISH_DEVELOPMENT, OP_CENTRE to `once_per_game` (the obvious "fire-once" cases).
4. The rest of the principles stay on current behavior in Phase 0.5; their migration is its own follow-up commit per principle family.
5. Audit: re-run `audit_rule_of_square.py` and `audit_opposition.py` to confirm raw fire counts unchanged. Then regen a multi-fire game (10c19d0c) and inspect `principle_id_used` to confirm state-keyed dedup correctly produces fewer visible fires.

## What does NOT ship in Phase 0.5

- Shape pattern (TIER 3) migration to state_key. Separate commit.
- Per-session soft-decay weighting (live-path concern, lands in Phase 1.x).
- Re-arm based on eval swing (deliberately excluded; not part of the key).
- New "intent_type" / "best_move_family" taxonomy — Phase 0.5 ships with these as lightweight string tags chosen per-detector at write time. A future cleanup could centralize the taxonomy into a small enum.

## Edge cases enumerated

1. **Detector doesn't emit state_key.** Fall back to once_per_game on the wiring side (no NULL-pointer crash).
2. **State_key collision across DIFFERENT principles.** Impossible since `principle_id` is part of the key.
3. **State_key components contain unhashable values.** Use `_freeze_state_key` helper to convert lists/dicts to tuples; raise loudly if it can't.
4. **Phase transition mid-move.** Phase is determined by board state, not by us; the detector reads `facts.get("phase")`. If a single move pushes from middlegame to endgame, the state_key's phase reflects the AFTER-move phase per `extract_facts` convention.
5. **Color swap inside one fire.** Some principles fire on opp moves (mover_is_user=False); the state_key still includes the principle perspective. Different perspective → different intent_type → different state.
6. **Same state_key fires legitimately twice in different game phases.** Phase is part of the key, so this is correctly NOT suppressed.
7. **Detector mis-emits state_key (bug).** Audit script verifies state_keys per fire by re-deriving them from evidence; mismatch is a detector bug.

## Verification scope (per [[audit-coverage-tracks-surface]])

Covered:
- Detector-level state_key emission for the four migrated endgame principles.
- V5-wiring-level (principle_id, state_key) dedup.
- Audit script's per-fire geometric check is unchanged (state_key is structural, not geometric).

NOT covered:
- Whether the state_key taxonomy is RIGHT — e.g., are "intent_type" labels well-chosen? That's a tuning concern after we see live behavior.
- Shape patterns (TIER 3) — separate commit.
- Live-path per-session decay — Phase 1.x.
- Real-corpus per-fire audit of the new state-keyed behavior against a regressed baseline. Audit scripts re-run after migration; if fire counts change, that's the validation signal.

## Related memories

- `[[play-with-coach-teaching-integration]]` — parent plan; Phase 1 depends on this.
- `[[play-with-coach-phase1-design]]` — Phase 1 spec; needs UPDATE to reference once_per_state_key.
- `[[endgame-principles-backlog]]` — Phase 4+ principles benefit from state_key infrastructure being ready.
- `[[design-clean-code-leaky]]` — edge cases enumerated upfront (§above); audit coverage flagged.
- `[[no-yes-man]]` — after migration, the audit re-run is the verification, not my word.
