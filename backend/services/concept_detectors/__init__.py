"""
In-game concept application detectors.

Each detector answers ONE question: "did the user just demonstrate
understanding of concept X in real game play?" — using only the
position before the move and the move itself, no external context.

Detectors return:
    "applied"  — the position was a clean test of the concept and the
                 user made the move the concept recommends.
    "missed"   — clean test, user violated the concept.
    None       — position wasn't a clean test (don't grade it).

Why this exists: the Engine 2 graduation rule for knowledge skills is
"one correct attempt in a guided lesson". That's weak. These detectors
let us upgrade specific skills from "studied" to genuinely "learned"
by counting unprompted in-game applications.

Integration point (NOT wired yet — design only):
    Inside coach_play move handler, after the user's move is accepted:

        from services.concept_detectors.rule_of_the_square import (
            detect_rule_of_the_square_application,
        )
        result = detect_rule_of_the_square_application(
            board_before, move, user_color
        )
        if result in ("applied", "missed"):
            outcome = "correct" if result == "applied" else "wrong"
            record_skill_attempt(
                memory, "endgame_rule_of_square", "endgame", outcome
            )

    Once we wire >=2 detectors, lift the graduation threshold for the
    affected skills from "1 correct (lesson)" to "1 correct (lesson) +
    1 applied (in-game)" — that's the honest "learned" bar.

Status (Mohit 2026-05-29):
  Wiring shipped — see registry.py + _runner.py + record_concept_
  applications_from_game in coach_memory.py. Graduation lift is live
  via SkillProgress.is_learned() (detector_engaged check).

  Detectors shipped:
    - endgame_rule_of_square      (pure K+P vs K)
    - defend_scholars_mate        (4-move attack with Bc4 + queen on f7)
    - mate_kq_vs_k                (K+Q vs lone K — mate or mate-in-1)
    - mate_kr_vs_k                (K+R vs lone K — mate or mate-in-1)
    - defend_fried_liver          (5.exd5 Nxd5?? trap defence)
    - endgame_opposition          (K+P opposition geometry)
    - endgame_lucena              (winning R+P bridge technique)
    - endgame_philidor            (drawing R+P rear-guard drop)

  Filed for product discussion (not yet shipped):
    - concept_iqp                 — middlegame IQP play. Needs an
                                    engine-light way to score "healthy
                                    IQP moves." False positives risky.
    - concept_minority_attack     — specific QGD-Exchange b4-b5 pawn
                                    break. Pattern-based detector
                                    possible; deferred until we have
                                    clearer "good vs bad" criteria.
    - concept_prophylaxis         — abstract: detect moves that
                                    prevent a future opponent tempo
                                    gain. Requires engine reasoning
                                    on "what would the opponent's
                                    best move have been." Hard to
                                    detect cleanly without false
                                    positives.
    - trap_set_italian /
      trap_set_caro_kann /
      trap_set_london             — existing PWC trap-teaching path
                                    already credits these. In-game
                                    auto-detection would credit users
                                    who "happened to avoid" traps
                                    they didn't know existed —
                                    product call needed.
    - coached_development         — needs a "focus skill" flow in PWC
                                    (start a coached game with focus=
                                    coached_development). Product
                                    decision.
"""
