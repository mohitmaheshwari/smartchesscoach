"""The own-game piece-safety drill names the game move before the solve.

2026-11-16, Mohit, on his move 22 (Be7, taken by the queen on c7): "it should
tell what move is the problem, from this position how do you know piece
safety". services/coaching_puzzle_service.py _get_coaching_context.
"""
from services import coaching_puzzle_service as cps
from services.verified_puzzle_admission import ADMISSION_VERSION

FEN = "5r1k/2q3pp/pb4b1/1pn1pp2/7B/1BP2P2/PP2Q1PP/3R1R1K w - - 0 22"


def _puzzle(reply="c7e7", played="h4e7"):
    return {
        "fen": FEN, "source": "your_game", "move_number": 22, "pattern_type": "piece_safety",
        "verified_admission": {
            "admission_version": ADMISSION_VERSION,
            "concept_id": "piece_safety.destination_safety_exact",
            "played_move_uci": played,
            "detector_facts": [{"piece": "bishop", "square": "e7", "winning_reply_uci": reply}],
        },
    }


def _context(puzzle):
    svc = cps.CoachingPuzzleService.__new__(cps.CoachingPuzzleService)
    return svc._get_coaching_context(puzzle, "piece_safety")


def test_the_drill_names_the_game_move_and_who_takes_it():
    c = _context(_puzzle())
    assert c["personal_note"] == "This is move 22 from your game."
    assert c["why_this_matters"] == (
        "You played Be7 here, and the queen on c7 could take your bishop on e7. Find a better move."
    )
    assert c["problem_move_uci"] == "h4e7" and c["problem_reply_uci"] == "c7e7"
    # The answer (Bc2) is never named before the solve.
    assert "Bc2" not in c["personal_note"] + c["why_this_matters"]


def test_a_reply_that_does_not_replay_drops_only_the_taker():
    c = _context(_puzzle(reply="a1a2"))
    assert c["why_this_matters"].startswith("You played Be7 here, and your bishop could be won on e7.")
    assert c["problem_reply_uci"] is None


def test_a_move_that_does_not_replay_keeps_the_old_text():
    c = _context(_puzzle(played="a1a8"))
    assert "problem_move_uci" not in c
    assert c["personal_note"].startswith("This is move 22 from your game. Solve it again")
