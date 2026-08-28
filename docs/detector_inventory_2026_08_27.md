# Detector quality-gate inventory — 2026-08-27

Status: PRE-CODE INVENTORY COMPLETE

This inventory names every detector family that can currently influence a
player-facing explanation, concept grade, weakness, active focus, or coaching
prompt. It records the canonical source and the enforcement point. Detector
quality authorization is a new concern; no existing file is its source of
truth.

## Inventory

| Family | Canonical detector IDs | Count | Current player-facing consumers | Quality-gate decision |
|---|---|---:|---|---|
| Cognitive-gap category | The analyzer's `cognitive_gap` values, refined by `services/cognitive_gap_subtypes.py` | 9 category families | `move_observation_deriver.py` -> focus/progress/plan services | Gate the derived observation before it becomes focus evidence. Category and subtype remain separate evidence dimensions. |
| Piece-safety decision (`D_live`) | `move_observation_deriver._derive_d_live_fact` | 1 versioned decision detector | Personal improvement cycle proof and focus projection | Keep as the canonical piece-safety decision fact. Do not recreate its logic in the quality authority. |
| Caption principles | `services/caption_principles.py:PRINCIPLES` | 35 | `caption_facts.py` -> `caption_pipeline.py` / `live_v5_teaching.py` | Authorize by principle ID after facts are computed and before selection/rendering. |
| Caption shape patterns | `services/shape_patterns.py:PATTERNS_BY_ID` + `services/shape_detectors.py` | 26 catalog entries / 26 detector functions | post-game V5 captions, live V5 teaching, realtime feedback | Authorize by shape-pattern ID after engine/dynamic verification. Geometry by itself cannot earn Plan-grade. |
| Mastery-transfer concepts | `services/concept_detectors/registry.py:DETECTORS` | 10 | `_runner.py` -> `coach_memory.record_skill_attempt` -> skill mastery | Gate centrally in `_runner.py`; unapproved detectors may be observed but cannot write mastery grades. |
| Chess Brain | `services/chess_brain/detector_registry.py` + `advanced_detectors.py` | 33 | Chess Brain, intelligent position coach, decryption voice dispatcher | Gate inside `DetectorRegistry.run_all`; default all unmeasured IDs to Shadow. |
| Legacy endgame principles | `services/endgame_detectors/principle_detector_registry.py:DETECTORS` | 3 | deterministic principle caption generator and extraction utilities | Treat as a legacy duplicate family; default Shadow until callers migrate to a canonical concept or caption-principle ID. |
| Standalone gap detectors | `coordination_detector.py`, `prophylaxis_detector.py`, `opening_deviation_detector.py`, `board_concepts.py`, `concept_attribution.py` | multiple | legacy Lab/profile/pattern flows | No new registry is created for their chess logic. Each reachable caller must declare a canonical quality ID before the result may become plan evidence. |

## Canonical ID sets

### Mastery-transfer concepts (10)

`endgame_rule_of_square`, `defend_scholars_mate`, `mate_kq_vs_k`,
`mate_kr_vs_k`, `defend_fried_liver`, `endgame_opposition`,
`endgame_lucena`, `endgame_philidor`, `trap_detection`, `opening_play`.

### Chess Brain (33)

`fork_detector`, `pin_detector`, `hanging_piece_detector`,
`trapped_piece_detector`, `back_rank_detector`, `mate_detector`,
`discovery_detector`, `skewer_detector`, `overload_detector`,
`removal_detector`, `isolated_pawn_detector`, `passed_pawn_detector`,
`knight_outpost_detector`, `rook_activity_detector`,
`king_safety_detector`, `time_trouble_detector`, `impulse_move_detector`,
`tilt_detector`, `doubled_pawns_detector`, `backward_pawn_detector`,
`bad_bishop_detector`, `space_advantage_detector`,
`weak_squares_detector`, `open_file_detector`, `seventh_rank_detector`,
`pawn_majority_detector`, `piece_coordination_detector`,
`opposition_detector`, `zugzwang_detector`,
`outside_passed_pawn_detector`, `king_activity_detector`,
`rook_endgame_detector`, `fortress_detector`.

### Caption principles (35)

`OP_FINISH_DEVELOPMENT`, `OP_LOOSE_KING_PAWNS`, `OP_QUEEN_OUT_EARLY`,
`OP_SAME_PIECE_TWICE`, `OP_PAWN_HEAVY`, `OP_CLAIM_CENTER`,
`OP_KNIGHT_ON_RIM`, `OP_BISHOP_BLOCKED`, `OP_NOT_CASTLED`,
`TAC_CHECKS_CAPTURES_THREATS`, `TAC_BACK_RANK`, `TAC_HANGING_PIECE`,
`TAC_DEFENDER_COUNT`, `TAC_FORK_PATTERN`, `TAC_PIN_PATTERN`,
`TAC_SKEWER_PATTERN`, `TAC_DISCOVERED_PATTERN`, `DEF_MOST_ATTACKED`,
`TAC_CHANGED_AFTER_MOVE`, `MID_KING_SAFETY`, `MID_KEEP_ATTACKERS`,
`MID_ROOK_OPEN_FILE`, `DEF_TRADE_ATTACKERS`, `MID_BAD_BISHOP`,
`MID_PAWN_BREAK`, `DEF_WALK_KING`, `END_PASSED_PAWN`,
`END_KING_ACTIVE`, `END_RULE_OF_SQUARE`, `END_OPPOSITION`,
`END_ROOK_BEHIND_PASSER`, `PAWN_PUSH_TRAPS_OWN_ROOK`,
`OP_BISHOP_TRADE_DOUBLES_PAWN`, `OP_F2_F7_STRIKE`,
`OP_TRAPPED_KNIGHT`.

### Shape patterns (catalog IDs, 26)

`knight_fork`, `bishop_fork`, `rook_fork`, `pawn_fork`, `hidden_attack`,
`pin`, `skewer`, `double_attack_line`, `back_rank_trap`, `h7_attack`,
`queen_knight_mate`, `strong_knight_square`, `weak_squares`, `free_pawn`,
`open_long_line`, `no_safe_square`, `tired_defender`, `free_piece`,
`long_diagonal_bishop`, `remove_the_guard`, `force_the_king`,
`in_between_move`, `knight_mate`, `pawn_hole_fianchetto`,
`king_pawn_lifted`, `clearance_for_attack`.

## Duplicate and drift findings

1. `shape_patterns.py` contains `in_between_move` without a same-ID entry in
   `shape_detectors._DETECTORS`; the detector map contains
   `clearance_then_check` without a same-ID catalog entry. This is reachability
   drift and needs a guard test, not another copied list.
2. Rule of the square still has three callable product surfaces, but no longer
   has three truth implementations. `concept_detectors/rule_of_the_square.py`
   owns the legal push-versus-king race fact;
   `endgame_detectors/rule_of_square_detector.py` and the caption predicate
   behind `END_RULE_OF_SQUARE` are compatibility adapters. All remain Disabled
   because the first 200-game production scan found only five eligible
   positions, all from one game - not enough independent evidence to authorize
   player-facing claims.
3. Fork, pin, skewer, hanging piece, king safety, pawn structure and endgame
   concepts are independently recognized in Chess Brain, shape detectors,
   caption facts and cognitive-gap subtypes. These are true logic duplicates
   when they assert the same board fact; authorization must not be mistaken for
   consolidation. Trapped-piece is now partially consolidated:
   Chess Brain and move attribution read services.board_concepts, while
   OP_TRAPPED_KNIGHT and shape:no_safe_square still answer narrower,
   perspective-specific questions and remain separate audit targets. Chess
   Brain king safety now adapts the pawn-shelter and king-zone facts owned by
   services.board_state_describer; MID_KING_SAFETY and cognitive-gap labeling
   remain separate audit targets because they answer different product
   questions. Chess Brain hanging-piece detection now adapts the
   board-mutating legal exchange truth in services.caption_facts instead of
   maintaining an attacker/defender-count recognizer; the caption principle
   remains the player-facing selector over that same semantic layer.
4. `test_detector_gold_corpus.py` calls data “gold” but filters on detector-like
   labels and uses firing-rate checks in places. It cannot authorize truth.
5. The earlier subtype scope allowed hard labels at 85% verified-true. The
   current king-safety audit found 145 concerning fires in 590 (24.6%), showing
   that the old floor and/or verifier was not safe enough for plan evidence.

## Single-source decision

Create one quality authority whose keys are namespaced references to the
canonical IDs above. It stores only authorization and evidence metadata; it
does not copy detector functions, labels, thresholds, chess rules, or catalog
text. Unknown IDs fail closed to `shadow`. Adding a detector requires one edit
to its canonical registry and zero quality-authority edits until evidence is
ready; promotion is a separate reviewed change.

The authority is consulted at these central chokepoints:

- plan evidence: observation/focus bridge;
- caption claims: principle and shape selection;
- mastery grades: concept-detector runner;
- Chess Brain claims: registry result aggregation.

External Lichess positions remain research evidence and never enter `games`,
`game_analyses`, `move_observations`, coach memory, or player focus history.
