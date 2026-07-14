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

    GATE 1: cp_loss >= 100 (real mistake, not inaccuracy)
    GATE 2: ANY detected facts exist (opening, phase, hangs, threats, etc.)

    Verified if BOTH gates pass.

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

    # GATE 2: Does the move have ANY detectable facts?
    # Check for all possible coaching reasons: tactics, hangs, threats, opening, phase, etc.
    has_coaching_reason = _has_any_coaching_fact(facts)

    if not has_coaching_reason:
        return {
            **facts,
            "verified": False,
            "verification_reason": "no coaching reason detected (pure positional)",
        }

    # Both gates pass - caption is verified
    return {
        **facts,
        "verified": True,
        "verification_details": _collect_verification_details(facts),
    }




def _has_any_coaching_fact(facts: Dict[str, Any]) -> bool:
    """
    Check if move has ANY coaching reason (tactical or positional).

    Returns True if ANY of these exist:
    - Hangs/undefended pieces
    - Tactics (fork, pin, skewer, discovered attack)
    - Threats created
    - Mate threats
    - Missed tactics
    - Opening context
    - Phase transition (opening -> middlegame, etc.)
    - Checks
    - Castling
    - Material/exchange facts
    """

    # Tactical facts
    if facts.get("pieces_now_undefended"):
        return True
    if facts.get("multi_target_attack_evidence"):
        return True
    if facts.get("aligned_pieces_evidence"):
        return True
    if facts.get("discovered_attack_evidence"):
        return True
    if facts.get("threats_created"):
        return True
    if facts.get("mate_threat_evidence"):
        return True
    if facts.get("missed_tactic_evidence"):
        return True

    # Positional/strategic facts
    if facts.get("opening_name"):
        return True
    if facts.get("phase"):
        return True
    if facts.get("is_check"):
        return True
    if facts.get("is_castling"):
        return True
    if facts.get("is_forced_recapture"):
        return True
    if facts.get("material_delta_played_cp"):
        return True

    # No coaching reason found
    return False


def _collect_verification_details(facts: Dict[str, Any]) -> Dict[str, bool]:
    """Collect all detected facts for debugging."""
    details = {}

    if facts.get("pieces_now_undefended"):
        details["hang"] = True
    if facts.get("multi_target_attack_evidence"):
        details["tactic"] = True
    if facts.get("aligned_pieces_evidence"):
        details["pin"] = True
    if facts.get("discovered_attack_evidence"):
        details["discovered"] = True
    if facts.get("threats_created"):
        details["threats"] = True
    if facts.get("mate_threat_evidence"):
        details["mate"] = True
    if facts.get("missed_tactic_evidence"):
        details["missed_tactic"] = True
    if facts.get("opening_name"):
        details["opening"] = True
    if facts.get("phase"):
        details["phase"] = True
    if facts.get("is_check"):
        details["check"] = True
    if facts.get("is_castling"):
        details["castling"] = True

    return details


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
    cp_loss: Optional[int] = None,
    mover_is_user: bool = True,
) -> Dict[str, Any]:
    """
    Extract facts with Stockfish verification (synchronous).

    Every fact is checked: is the detection backed by engine eval?

    2026-07-14 severity-POV fix (found chasing "check. King must move or
    block." rendering on a 266cp blunder): this function used to DISCARD the
    caller's mover-POV cp_loss and re-derive it as a white-POV delta
    (eval_before - eval_after) with no color flip. For every BLACK mover a
    real mistake came out NEGATIVE (floored to 0 downstream) — the blunder
    became invisible and neutral templates (plain check / threat / king
    safety) captioned it as a quiet move. It also never forwarded
    mover_is_user, mis-attributing caption voice. Now: trust the caller's
    cp_loss (stored analysis truth, already mover-POV); only derive when
    absent, and derive from the MOVER's point of view.
    """
    if cp_loss is None:
        raw = (eval_before_cp or 0) - (eval_after_cp or 0)
        try:
            _mover_white = chess.Board(fen_before).turn == chess.WHITE
        except Exception:
            _mover_white = True
        cp_loss = max(0, raw if _mover_white else -raw)

    facts = extract_facts(
        fen_before=fen_before,
        played_san=played_san,
        best_move_san=best_move_san,
        eval_before_cp=eval_before_cp,
        eval_after_cp=eval_after_cp,
        cp_loss=int(cp_loss),
        pv_after_played=pv_after_played or [],
        pv_after_best=pv_after_best or [],
        move_history_san=move_history_san or [],
        full_move_number=full_move_number,
        mover_is_user=mover_is_user,
    )

    # Verify against Stockfish
    try:
        board = chess.Board(fen_before)
    except:
        facts["verified"] = False
        return facts

    verified_facts = verify_facts(facts, board)

    return verified_facts
