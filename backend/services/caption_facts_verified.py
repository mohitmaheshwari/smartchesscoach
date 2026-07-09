"""
Caption Facts Verified — Stockfish-backed detection layer.

Wraps caption_facts.extract_facts() with mandatory verification gates.
Every detected fact must be backed by Stockfish evaluation.

GATES:
  Gate 1: cp_loss significance — Is the move actually a mistake by engine standard?
  Gate 2: Fact-eval consistency — Does the detected fact explain the cp_loss?
  Gate 3: Threat severity — Is detected threat significant vs eval?

RESULT: Every fact returns (detected, verified=true/false)
  verified=true  → confidence 8/10, show to user
  verified=false → confidence <3/10, silence or fallback only
"""

from typing import Dict, Any, Optional, List
import chess
from services.caption_facts import extract_facts


def verify_facts(
    facts: Dict[str, Any],
    board_before: chess.Board,
) -> Dict[str, Any]:
    """
    Verify all detected facts against Stockfish evaluation.

    Args:
        facts: Output from extract_facts()
        board_before: Position before the move

    Returns:
        facts dict with added 'verified' and 'verification_details' fields
    """

    cp_loss = facts.get("cp_loss", 0)
    eval_before = facts.get("eval_before_cp", 0)
    eval_after = facts.get("eval_after_cp", 0)

    # GATE 1: Is cp_loss significant enough to caption?
    # Only caption real mistakes (blunders > 300cp, mistakes > 100cp)
    if cp_loss < 100:
        return {
            **facts,
            "verified": False,
            "verification_reason": "cp_loss < 100 (not a real mistake)",
        }

    verification_details = {}

    # GATE 2: Verify each detected fact matches eval

    # Hang verification
    if facts.get("pieces_now_undefended"):
        hang_verified = _verify_hang(facts, cp_loss)
        verification_details["hang"] = hang_verified
        if not hang_verified and not _has_verified_detection(verification_details):
            # Hang was detected but eval doesn't support it as primary reason
            pass

    # Tactic verification
    if facts.get("multi_target_attack_evidence"):
        tactic_verified = _verify_tactic(facts, cp_loss)
        verification_details["tactic"] = tactic_verified

    if facts.get("aligned_pieces_evidence"):
        pin_verified = _verify_pin(facts, cp_loss)
        verification_details["pin"] = pin_verified

    if facts.get("discovered_attack_evidence"):
        discovered_verified = _verify_discovered_attack(facts, cp_loss)
        verification_details["discovered"] = discovered_verified

    # Threat verification
    if facts.get("threats_created"):
        threats_verified = _verify_threats(facts, cp_loss)
        verification_details["threats"] = threats_verified

    # Mate threat verification
    if facts.get("mate_threat_evidence"):
        mate_verified = _verify_mate_threat(facts, cp_loss)
        verification_details["mate"] = mate_verified

    # Missed tactic verification
    if facts.get("missed_tactic_evidence"):
        missed_verified = _verify_missed_tactic(facts, cp_loss)
        verification_details["missed_tactic"] = missed_verified

    # Overall verdict: verified if ANY detected fact is verified
    is_verified = any(v for v in verification_details.values() if v is True)

    return {
        **facts,
        "verified": is_verified,
        "verification_details": verification_details,
    }


def _verify_hang(facts: Dict[str, Any], cp_loss: int) -> bool:
    """
    Verify that a piece is actually hanging (undefended + captured).

    Hang should match material value in cp_loss.
    """
    pieces_undefended = facts.get("pieces_now_undefended", [])
    if not pieces_undefended:
        return False

    # Expected material loss from hanging
    total_value = sum(p.get("piece_value_cp", 0) for p in pieces_undefended)

    # Gate: cp_loss should roughly match piece value (within 50cp for calculation errors)
    if total_value > 0 and abs(cp_loss - total_value) < 50:
        return True

    # Or cp_loss is very large (piece + positional loss)
    if cp_loss >= total_value + 100:
        return True

    return False


def _verify_tactic(facts: Dict[str, Any], cp_loss: int) -> bool:
    """
    Verify that a tactic (fork, skewer) actually explains the cp_loss.

    Tactic should gain material, so eval should shift by tactic value.
    """
    tactic_evidence = facts.get("multi_target_attack_evidence", [])
    if not tactic_evidence:
        return False

    # Each target should be significant (avoid trivial tactics)
    targets = tactic_evidence[0].get("targets", []) if tactic_evidence else []
    target_value = sum(t.get("piece_value_cp", 0) for t in targets)

    # Gate: cp_loss should be explained by winning material
    # If we win material, eval_after should be better, so cp_loss < 0
    # But our convention is cp_loss = eval_before - eval_after
    # So winning material means cp_loss is negative (good for us)

    # Actually: if we play a good tactic, cp_loss should be small or negative
    # If we play a bad move that missed a tactic, cp_loss should be large

    # For this position: we're analyzing OUR move
    # If we played a tactic, we gained material -> cp_loss negative or small
    # If we didn't play the tactic and blundered, cp_loss large

    # So: if tactic detected and target_value > 0, cp_loss should be small
    if target_value > 300 and cp_loss < 200:  # Good tactic, small loss
        return True

    return False


def _verify_pin(facts: Dict[str, Any], cp_loss: int) -> bool:
    """
    Verify that a pin actually exists and is significant.
    """
    pin_evidence = facts.get("aligned_pieces_evidence", [])
    if not pin_evidence:
        return False

    # Pin should be on valuable piece (rear piece)
    for pin in pin_evidence:
        rear_value = pin.get("rear_piece_value_cp", 0)
        if rear_value >= 500:  # Queen or Rook
            # Pin on valuable piece should matter
            if cp_loss > 50:  # Position shifted significantly
                return True

    return False


def _verify_discovered_attack(facts: Dict[str, Any], cp_loss: int) -> bool:
    """
    Verify that a discovered attack is real and significant.
    """
    discovered = facts.get("discovered_attack_evidence", [])
    if not discovered:
        return False

    for attack in discovered:
        target_value = attack.get("target_value_cp", 0)
        if target_value >= 300 and cp_loss > 100:
            return True

    return False


def _verify_threats(facts: Dict[str, Any], cp_loss: int) -> bool:
    """
    Verify that created threats are real and explained by eval shift.
    """
    threats = facts.get("threats_created", [])
    if not threats:
        return False

    # Any significant threat (SEE >= 200) is worth verifying
    for threat in threats:
        threat_see = threat.get("see_cp", 0)
        if threat_see >= 200:
            # Threat creates pressure, eval should shift
            if cp_loss < 50:  # Threat doesn't lose material
                return True

    return False


def _verify_mate_threat(facts: Dict[str, Any], cp_loss: int) -> bool:
    """
    Verify that a mate threat is real.
    Mate threats should show large eval swings.
    """
    if not facts.get("mate_threat_evidence"):
        return False

    # Mate threats are absolute — any mate threat with large eval is verified
    eval_swing = abs(facts.get("eval_before_cp", 0) - facts.get("eval_after_cp", 0))

    if eval_swing > 500:  # Large swing (mate is near)
        return True

    return False


def _verify_missed_tactic(facts: Dict[str, Any], cp_loss: int) -> bool:
    """
    Verify that we actually missed a significant tactic.
    """
    missed = facts.get("missed_tactic_evidence")
    if not missed:
        return False

    # If we missed a tactic, eval should have shifted significantly
    # cp_loss should be large
    if cp_loss >= 150:
        return True

    return False


def _has_verified_detection(details: Dict[str, bool]) -> bool:
    """Check if any detection is verified."""
    return any(v for v in details.values() if v is True)


def extract_facts_verified(
    fen_before: str,
    played_san: str,
    best_move_san: Optional[str],
    eval_before_cp: int,
    eval_after_cp: int,
    pv_after_played: Optional[List[str]] = None,
    pv_after_best: Optional[List[str]] = None,
    move_history_san: Optional[List[str]] = None,
    full_move_number: int = 1,
) -> Dict[str, Any]:
    """
    Extract facts with Stockfish verification (synchronous).

    Every fact is checked: is the detection backed by engine eval?
    """

    # Get raw facts
    cp_loss = (eval_before_cp or 0) - (eval_after_cp or 0)

    facts = extract_facts(
        fen_before=fen_before,
        played_san=played_san,
        best_move_san=best_move_san,
        eval_before_cp=eval_before_cp,
        eval_after_cp=eval_after_cp,
        cp_loss=cp_loss,
        pv_after_played=pv_after_played or [],
        pv_after_best=pv_after_best or [],
        move_history_san=move_history_san or [],
        full_move_number=full_move_number,
    )

    # Verify against Stockfish
    try:
        board = chess.Board(fen_before)
    except:
        facts["verified"] = False
        return facts

    verified_facts = verify_facts(facts, board)

    return verified_facts
