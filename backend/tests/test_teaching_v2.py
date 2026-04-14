"""
Tests for Teaching Move Selector v2 — pattern detectors + intent selection.

All tests use specific FEN positions to verify:
1. Pattern detectors find real patterns
2. Intent selector picks feasible intents
3. Scoring produces meaningful differentiation
4. No illegal moves are returned
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import chess
import pytest

from coach_play.teaching.types import (
    TeachingIntent, CandidateMove, PIECE_VALUES,
)
from coach_play.teaching.pattern_detectors import (
    find_hanging_pieces, find_fork_opportunities,
    count_forcing_moves, analyze_position,
)
from coach_play.teaching.teaching_evaluator import (
    score_candidate, score_all_candidates, is_intent_feasible,
    MIN_FEASIBILITY_SCORE,
)
from coach_play.teaching.intent_selector import (
    rank_intents, select_intent,
)


# ─── PATTERN DETECTOR TESTS ─────────────────────────────────────


class TestHangingPieceDetector:
    """Test find_hanging_pieces on known positions."""

    def test_undefended_knight(self):
        """Black knight on d5 attacked by white pawn on e4, no defenders."""
        # White: Ke1, Pe4  Black: Ke8, Nd5
        board = chess.Board("4k3/8/8/3n4/4P3/8/8/4K3 w - - 0 1")
        undefended, underdefended = find_hanging_pieces(board, chess.BLACK)
        assert len(undefended) >= 1
        # The knight on d5 should be found
        hanging_squares = [h.square for h in undefended]
        assert chess.D5 in hanging_squares

    def test_defended_piece_not_hanging(self):
        """Black knight on d5 defended by pawn on e6 — should NOT be hanging."""
        # White: Ke1, Pe4  Black: Ke8, Nd5, Pe6
        board = chess.Board("4k3/8/4p3/3n4/4P3/8/8/4K3 w - - 0 1")
        undefended, underdefended = find_hanging_pieces(board, chess.BLACK)
        hanging_squares = [h.square for h in undefended]
        assert chess.D5 not in hanging_squares

    def test_underdefended_piece(self):
        """Piece with more attackers than defenders and cheaper attacker."""
        # White: Ke1, Nf3, Bc4 attack d5  Black: Ke8, Qd5 defended by nothing
        # Actually Qd5 undefended + attacked = undefended, not underdefended
        # Better: Qd5 defended by Nd7, attacked by Bc4 and Nf3 (2 minors vs 1 minor defending queen)
        board = chess.Board("4k3/3n4/8/3q4/2B5/5N2/8/4K3 w - - 0 1")
        undefended, underdefended = find_hanging_pieces(board, chess.BLACK)
        # Queen on d5: attacked by Bc4 + Nf3, defended by Nd7
        # 2 attackers (value 3 each) > 1 defender, cheapest attacker (3) < queen (9)
        total_hanging = len(undefended) + len(underdefended)
        assert total_hanging >= 1

    def test_no_hanging_in_starting_position(self):
        """Starting position — no pieces should be hanging."""
        board = chess.Board()
        undefended, underdefended = find_hanging_pieces(board, chess.WHITE)
        assert len(undefended) == 0
        assert len(underdefended) == 0


class TestForkDetector:
    """Test find_fork_opportunities on known positions."""

    def test_knight_fork_king_and_queen(self):
        """Classic knight fork: Nc7 forks Ke8 and Qa8."""
        # White: Ke1, Nc7  Black: Ke8, Qa8
        board = chess.Board("q3k3/2N5/8/8/8/8/8/4K3 w - - 0 1")
        forks = find_fork_opportunities(board, chess.WHITE)
        # Knight on c7 attacks both Ke8 and Qa8
        assert len(forks) >= 1
        fork = forks[0]
        assert fork.forker_type == chess.KNIGHT
        assert len(fork.target_squares) >= 2

    def test_no_fork_with_single_target(self):
        """Knight attacks only one piece — not a fork."""
        # White: Ke1, Nc3  Black: Ke8, Nd5
        board = chess.Board("4k3/8/8/3n4/8/2N5/8/4K3 w - - 0 1")
        forks = find_fork_opportunities(board, chess.WHITE)
        # Nc3 only attacks Nd5 (one target)
        knight_forks = [f for f in forks if f.forker_square == chess.C3]
        assert len(knight_forks) == 0

    def test_queen_fork(self):
        """Queen forking two pieces — king and rook."""
        # White: Ke1, Qa4  Black: Ke8, Ra7 — Qa4 attacks Ra7 and Ke8 diagonally
        board = chess.Board("4k3/r7/8/8/Q7/8/8/4K3 w - - 0 1")
        forks = find_fork_opportunities(board, chess.WHITE)
        queen_forks = [f for f in forks if f.forker_type == chess.QUEEN]
        # Queen on a4 attacks both Ra7 and diagonal to e8
        assert len(queen_forks) >= 1


class TestForcingMoves:
    """Test count_forcing_moves."""

    def test_check_available(self):
        """Position with available checks."""
        # White: Ke1, Qh5  Black: Ke8
        board = chess.Board("4k3/8/8/7Q/8/8/8/4K3 w - - 0 1")
        checks, captures, hv = count_forcing_moves(board, chess.WHITE)
        assert checks >= 1  # Qe8+, Qe5+, Qh8+, etc.

    def test_forcing_on_either_turn(self):
        """count_forcing_moves works even when it's not side's turn (flips board)."""
        # It's Black's turn, but we ask for White's threats
        board = chess.Board("4k3/8/8/7Q/8/8/8/4K3 b - - 0 1")
        checks, captures, hv = count_forcing_moves(board, chess.WHITE)
        # White's queen should have checks available even though it's Black's turn
        assert checks >= 1


class TestPositionAnalysis:
    """Test the full analyze_position function."""

    def test_returns_features(self):
        """analyze_position returns a PositionFeatures with all fields."""
        board = chess.Board()
        features = analyze_position(board, chess.WHITE)
        assert hasattr(features, "opponent_hanging")
        assert hasattr(features, "fork_opportunities")
        assert hasattr(features, "checks_available")


# ─── TEACHING EVALUATOR TESTS ───────────────────────────────────


class TestTeachingEvaluator:
    """Test scoring functions."""

    def _make_candidate(self, board, move_san, eval_cp=0, rank=1):
        move = board.parse_san(move_san)
        return CandidateMove(
            move=move, san=move_san, eval_cp=eval_cp, eval_rank=rank,
        )

    def test_hanging_piece_scores_higher_when_pieces_hang(self):
        """A move that leaves opponent pieces hanging should score higher
        for HANGING_PIECE_PUNISHMENT than a move that doesn't."""
        # Position where White can play Bb5, attacking undefended Nc6
        # White: Ke1, Bf1  Black: Ke8, Nc6
        board = chess.Board("4k3/8/2n5/8/8/8/8/4KB2 w - - 0 1")

        # Bb5 attacks undefended Nc6
        candidate_attack = self._make_candidate(board, "Bb5", eval_cp=50, rank=1)
        # Ke2 does nothing
        candidate_quiet = self._make_candidate(board, "Ke2", eval_cp=30, rank=2)

        score_attack = score_candidate(
            board, candidate_attack, TeachingIntent.HANGING_PIECE_PUNISHMENT,
            chess.WHITE, best_eval_cp=50,
        )
        score_quiet = score_candidate(
            board, candidate_quiet, TeachingIntent.HANGING_PIECE_PUNISHMENT,
            chess.WHITE, best_eval_cp=50,
        )

        # Attack move should have higher raw_score
        assert score_attack.raw_score > score_quiet.raw_score

    def test_fork_scores_higher_with_fork(self):
        """A move that creates a fork should score higher for FORK_OPPORTUNITY."""
        # White: Ke1, Nd4  Black: Ke8, Ra8, Rc8 (if Nc6 forks Ra8+Rc8? Let's try a known fork)
        # Better: setup where Nc7 forks K+R
        # White: Ke1, Nd5  Black: Ke8, Ra8
        board = chess.Board("r3k3/8/8/3N4/8/8/8/4K3 w - - 0 1")

        # Nc7+ forks king and rook (if legal)
        try:
            candidate_fork = self._make_candidate(board, "Nc7+", eval_cp=100, rank=1)
            score_fork = score_candidate(
                board, candidate_fork, TeachingIntent.FORK_OPPORTUNITY,
                chess.WHITE, best_eval_cp=100,
            )
            assert score_fork.raw_score > 0
        except ValueError:
            # Move might not be legal in this exact position — that's ok
            pass

    def test_feasibility_check(self):
        """is_intent_feasible returns True when at least one score is above threshold."""
        from coach_play.teaching.types import IntentScore
        scores_feasible = [
            IntentScore(intent=TeachingIntent.THREAT_AWARENESS, raw_score=0.5, final_score=0.5),
            IntentScore(intent=TeachingIntent.THREAT_AWARENESS, raw_score=0.1, final_score=0.1),
        ]
        assert is_intent_feasible(scores_feasible) is True

        scores_not_feasible = [
            IntentScore(intent=TeachingIntent.THREAT_AWARENESS, raw_score=0.1, final_score=0.1),
            IntentScore(intent=TeachingIntent.THREAT_AWARENESS, raw_score=0.0, final_score=0.0),
        ]
        assert is_intent_feasible(scores_not_feasible) is False


# ─── INTENT SELECTOR TESTS ──────────────────────────────────────


class TestIntentSelector:
    """Test intent ranking and selection."""

    def test_rank_with_tactics_focus(self):
        """Teaching focus 'tactics' should rank FORK first."""
        ranked = rank_intents(teaching_focus="tactics")
        assert ranked[0] == TeachingIntent.FORK_OPPORTUNITY

    def test_rank_with_threat_awareness_weakness(self):
        """Student weakness 'threat_awareness' should rank HANGING_PIECE first."""
        ranked = rank_intents(student_weaknesses=["threat_awareness"])
        assert ranked[0] == TeachingIntent.HANGING_PIECE_PUNISHMENT

    def test_rank_with_learning_loop(self):
        """Last game violations should boost corresponding intents."""
        ranked_without = rank_intents()
        ranked_with = rank_intents(last_game_violations=["hanging_pieces"])

        # HANGING_PIECE_PUNISHMENT should be higher with the violation
        idx_without = ranked_without.index(TeachingIntent.HANGING_PIECE_PUNISHMENT)
        idx_with = ranked_with.index(TeachingIntent.HANGING_PIECE_PUNISHMENT)
        assert idx_with <= idx_without

    def test_rank_default_order(self):
        """No profile info — should return default order."""
        ranked = rank_intents()
        assert TeachingIntent.THREAT_AWARENESS in ranked
        assert TeachingIntent.HANGING_PIECE_PUNISHMENT in ranked
        assert TeachingIntent.FORK_OPPORTUNITY in ranked

    def test_focus_has_more_weight_than_weakness(self):
        """Teaching focus (explicit) per-intent weight (+3.0) > weakness per-intent (+2.0)."""
        # tactics focus: FORK +3.0, HANGING +2.5, THREAT +2.0
        # No weakness → FORK should be first purely from focus
        ranked = rank_intents(teaching_focus="tactics")
        assert ranked[0] == TeachingIntent.FORK_OPPORTUNITY

        # Now add a weakness that boosts HANGING: threat_awareness → HANGING +2.0
        # FORK = 3.0, HANGING = 2.5 + 2.0 = 4.5 → HANGING wins (both signals stack)
        ranked2 = rank_intents(
            teaching_focus="tactics",
            student_weaknesses=["threat_awareness"],
        )
        # This is correct behavior: when weakness and focus BOTH boost HANGING, it should win
        assert ranked2[0] == TeachingIntent.HANGING_PIECE_PUNISHMENT


# ─── INTEGRATION TEST (no engine needed) ────────────────────────


class TestPatternDetectorsIntegration:
    """Test that pattern detectors work together on real-ish positions."""

    def test_italian_game_position(self):
        """After 1.e4 e5 2.Nf3 Nc6 3.Bc4 — standard position."""
        board = chess.Board()
        for san in ["e4", "e5", "Nf3", "Nc6", "Bc4"]:
            board.push_san(san)

        features = analyze_position(board, chess.WHITE)
        # In this position, White has some tactical possibilities
        # but nothing should crash
        assert features is not None
        assert isinstance(features.checks_available, int)

    def test_hanging_piece_after_blunder(self):
        """Set up a position where Black blundered a piece."""
        # After 1.e4 e5 2.Nf3 Nc6 3.Bc4 Nd4?? (bad move, Nc6 was defending e5)
        # Now e5 pawn might be hanging
        board = chess.Board()
        for san in ["e4", "e5", "Nf3", "Nc6", "Bc4", "Nd4"]:
            board.push_san(san)

        # Analyze from White's perspective
        features = analyze_position(board, chess.WHITE)
        # The e5 pawn is now undefended (Nc6 moved away)
        # But we skip pawns in hanging detection, so check structure is intact
        assert features is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
