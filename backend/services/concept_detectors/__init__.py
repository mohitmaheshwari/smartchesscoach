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
"""
