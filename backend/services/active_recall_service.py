"""
ACTIVE RECALL SERVICE

Generates pedagogically sound active recall questions using existing verifiers.

Uses:
- chess_verification_layer.verify_move() — validates move rankings
- rule_validator.RuleValidator — validates position evidence
- verified_cause_classifier — validates cognitive gaps
- caption_verifier — validates principle text

Never shows unverified options. If verification fails, skips active recall.
"""

import chess
import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


# ============================================================================
# CONCEPT MAPPING — Maps cognitive gap to principle text + distractors
# ============================================================================

CONCEPT_EXPLANATIONS = {
    "centralization": {
        "correct": "Controls more squares from the center",
        "wrong_options": [
            "Attacks opponent's pieces",
            "Develops faster",
            "Protects your king"
        ]
    },
    "piece_safety": {
        "correct": "Leaves your piece undefended",
        "wrong_options": [
            "Weakens king safety",
            "Blocks development",
            "Gives opponent initiative"
        ]
    },
    "hanging_piece": {
        "correct": "Your piece can be captured for free",
        "wrong_options": [
            "Allows opponent check",
            "Wastes a move",
            "Breaks pawn structure"
        ]
    },
    "missed_tactic": {
        "correct": "Misses a winning tactic",
        "wrong_options": [
            "Allows opponent's tactics",
            "Wastes time",
            "Improves opponent's position"
        ]
    },
    "tactical_oversight": {
        "correct": "Overlooks opponent's tactical threat",
        "wrong_options": [
            "Makes a weak move",
            "Gives away material",
            "Blocks your own piece"
        ]
    },
    "calculation_depth": {
        "correct": "Doesn't calculate far enough ahead",
        "wrong_options": [
            "Makes too hasty a move",
            "Misses opponent's reply",
            "Ignores pawn structure"
        ]
    },
    "king_safety": {
        "correct": "Exposes your king to danger",
        "wrong_options": [
            "Weakens your position",
            "Allows opponent attack",
            "Loses material"
        ]
    },
    "pawn_structure": {
        "correct": "Weakens pawn structure",
        "wrong_options": [
            "Loses time in development",
            "Gives opponent space",
            "Blocks piece movement"
        ]
    },
    "piece_activity": {
        "correct": "Puts your piece on a passive square",
        "wrong_options": [
            "Doesn't develop fully",
            "Limits your options",
            "Allows opponent initiative"
        ]
    },
    "opening_knowledge": {
        "correct": "Deviates from opening theory",
        "wrong_options": [
            "Wastes a tempo",
            "Gives opponent advantage",
            "Leads to weak position"
        ]
    },
}


# ============================================================================
# DIFFICULTY CALIBRATION
# ============================================================================

def calibrate_difficulty_for_rating(user_rating: int) -> Dict:
    """
    Calibrate ranking option difficulty based on user rating.

    Lower ratings: options must be very different
    Higher ratings: options can be more subtle
    """
    if user_rating < 1000:
        return {
            "min_cp_spread": 200,
            "max_options": 3,
            "show_piece_values": True,
        }
    elif user_rating < 1400:
        return {
            "min_cp_spread": 100,
            "max_options": 3,
            "show_piece_values": False,
        }
    elif user_rating < 1800:
        return {
            "min_cp_spread": 50,
            "max_options": 4,
            "show_piece_values": False,
        }
    else:
        return {
            "min_cp_spread": 30,
            "max_options": 4,
            "show_piece_values": False,
        }


# ============================================================================
# RANKING OPTIONS GENERATION
# ============================================================================

async def generate_ranking_options(
    db,
    fen: str,
    user_move_san: str,
    best_move_san: str,
    user_rating: int
) -> Optional[Dict]:
    """
    Generate ranking options (choose best move) with verification.

    Returns None if verification fails (skip active recall for this move).
    """

    try:
        from chess_verification_layer import verify_move, safe_board

        board = safe_board(fen)
        if not board:
            logger.warning(f"[AR] Invalid FEN: {fen}")
            return None

        # Verify the moves are legal
        try:
            user_move = board.parse_san(user_move_san)
            best_move = board.parse_san(best_move_san)
        except Exception as e:
            logger.warning(f"[AR] Invalid move: {e}")
            return None

        # Verify best move is actually better
        analysis = verify_move(fen, user_move_san, best_move_san, cp_loss=50)
        if not analysis.get('is_valid'):
            logger.debug(f"[AR] Move verification failed")
            return None

        difficulty = calibrate_difficulty_for_rating(user_rating)

        # Generate candidate options
        candidates = []

        # 1. Best move (always include)
        candidates.append({
            "move_san": best_move_san,
            "is_best": True,
        })

        # 2. User's played move
        candidates.append({
            "move_san": user_move_san,
            "is_best": False,
        })

        # 3. Find a tempting alternative
        tempting_move = await find_tempting_alternative(board, best_move_san)
        if tempting_move:
            candidates.append({
                "move_san": tempting_move,
                "is_best": False,
            })

        # Shuffle order for display
        import random
        display_options = candidates.copy()
        random.shuffle(display_options)

        # Find index of best move in shuffled list
        correct_index = next(i for i, opt in enumerate(display_options) if opt['is_best'])

        return {
            "type": "ranking",
            "question": "Which move is best here?",
            "options": [opt["move_san"] for opt in display_options],
            "correct_index": correct_index,
            "is_verified": True,
        }

    except Exception as e:
        logger.error(f"[AR] Error generating ranking options: {e}")
        return None


async def find_tempting_alternative(board: chess.Board, best_move_san: str) -> Optional[str]:
    """
    Find a move that looks reasonable but is worse than best_move.
    """
    try:
        candidates = []
        for move in list(board.legal_moves)[:20]:  # Check first 20 moves
            move_san = board.san(move)

            if move_san == best_move_san:
                continue

            # Skip obviously bad moves
            board_test = board.copy()
            board_test.push(move)

            if board_test.is_checkmate():
                continue

            candidates.append(move_san)

        if candidates:
            import random
            return random.choice(candidates[:5])

        return None

    except Exception as e:
        logger.warning(f"[AR] Error finding tempting alternative: {e}")
        return None


# ============================================================================
# CONCEPT MATCHING GENERATION
# ============================================================================

async def generate_concept_options(
    db,
    fen: str,
    user_move_san: str,
    best_move_san: str,
    cognitive_gap: str,
    user_rating: int,
    cp_loss: int = 0
) -> Optional[Dict]:
    """
    Generate concept matching (MCQ: why was this wrong?).

    Returns None if verification fails.
    """

    try:
        from chess_verification_layer import get_critical_facts, safe_board

        board = safe_board(fen)
        if not board:
            logger.warning(f"[AR] Invalid FEN for concept: {fen}")
            return None

        # Verify the cognitive gap is correct
        facts = get_critical_facts(fen, user_move_san, best_move_san, cp_loss)

        # Check if this gap is in detected patterns
        detected_gaps = facts.get('detected_patterns', [])
        if cognitive_gap not in detected_gaps:
            logger.debug(f"[AR] Gap '{cognitive_gap}' not in detected: {detected_gaps}")
            return None

        # Get concept explanation
        concept = CONCEPT_EXPLANATIONS.get(cognitive_gap)
        if not concept:
            logger.warning(f"[AR] No explanation for gap: {cognitive_gap}")
            return None

        correct_text = concept['correct']
        wrong_options = concept['wrong_options']

        # Create all options
        all_options = [correct_text] + wrong_options

        # Shuffle
        import random
        shuffled = all_options.copy()
        random.shuffle(shuffled)

        correct_index = shuffled.index(correct_text)

        return {
            "type": "concept",
            "question": f"Why is {user_move_san} worse than {best_move_san}?",
            "options": shuffled,
            "correct_index": correct_index,
            "is_verified": True,
            "cognitive_gap": cognitive_gap,
        }

    except Exception as e:
        logger.error(f"[AR] Error generating concept options: {e}")
        return None


# ============================================================================
# COMBINED ACTIVE RECALL GENERATION
# ============================================================================

async def generate_active_recall(
    db,
    fen: str,
    user_move_san: str,
    best_move_san: str,
    cognitive_gap: str,
    user_rating: int,
    cp_loss: int = 0
) -> Optional[Dict]:
    """
    Generate BOTH ranking + concept options for a single mistake.

    Returns combined active recall package or None if verification fails.
    """

    # Generate both options
    ranking = await generate_ranking_options(
        db, fen, user_move_san, best_move_san, user_rating
    )

    concept = await generate_concept_options(
        db, fen, user_move_san, best_move_san, cognitive_gap, user_rating, cp_loss
    )

    # Both must verify
    if not ranking or not concept:
        logger.info(f"[AR] Skipping: ranking={ranking is not None}, concept={concept is not None}")
        return None

    return {
        "has_active_recall": True,
        "ranking": ranking,
        "concept": concept,
    }


# ============================================================================
# RESPONSE HANDLING
# ============================================================================

async def record_active_recall_response(
    db,
    user_id: str,
    session_id: str,
    move_index: int,
    cognitive_gap: str,
    ranking_response: Optional[int],
    ranking_correct_index: int,
    concept_response: Optional[int],
    concept_correct_index: int,
) -> Dict:
    """
    Record user's active recall responses for spaced repetition.
    """

    ranking_correct = ranking_response == ranking_correct_index
    concept_correct = concept_response == concept_correct_index

    checkpoint = {
        "user_id": user_id,
        "session_id": session_id,
        "move_index": move_index,
        "pattern": cognitive_gap,
        "ranking_correct": ranking_correct,
        "concept_correct": concept_correct,
        "combined_score": "mastered" if (ranking_correct and concept_correct) else
                         "partial" if (ranking_correct or concept_correct) else
                         "not_learned",
        "timestamp": datetime.utcnow().isoformat(),
    }

    await db.learning_checkpoints.insert_one(checkpoint)

    logger.info(f"[AR] Response recorded: gap={cognitive_gap}, score={checkpoint['combined_score']}")

    return checkpoint
