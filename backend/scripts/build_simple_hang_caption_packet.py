"""Build the two evidence pieces simple_hang still needs for Caption-grade.

docs/detector_quality_threshold_lock_2026_08_27.md sets Caption-grade at:
  - reviewed semantic precision >=95%        simple_hang: 96.9%   (have)
  - 95% Wilson precision lower bound >=85%   simple_hang: ~94.0%  (have)
  - at least 50 reviewed fires               simple_hang: 260     (have)
  - at least 20 true negative / non-opportunity cases            (MISSING)
  - zero critical false claims in an adversarial packet          (MISSING)
  - no recall floor -- a caption detector may safely stay silent

So the documented recall gap (61.61% taxonomy recall) blocks Plan-grade, not
Caption-grade. Only the two missing pieces stand between simple_hang and
being allowed to speak to a player.

Both are mined from real production moves rather than hand-authored, and every
case is re-derived from the board with python-chess and the same
material_hung_after used by the detector -- never from a stored label.

NON-OPPORTUNITY (true negative): a move after which the opponent has a
capture, but the position is NOT a simple hang, and the detector must stay
silent. Reasons recorded per case:
  defended        the capture loses material for the opponent (SEE <= 0)
  compensated     material is loose but the engine says it costs little
  below_floor     value at risk sits under the 150cp floor

ADVERSARIAL: real positions sitting within +/-40cp of either D_live floor,
where a small threshold slip flips the verdict. A critical false claim is a
case the detector calls a hang while board truth says otherwise.

    python backend/scripts/build_simple_hang_caption_packet.py --limit 4000
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import chess
from motor.motor_asyncio import AsyncIOMotorClient

BACKEND_ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = (
    BACKEND_ROOT / "data" / "corpus_snapshots" / "simple_hang_caption_packet.json"
)

SEE_FLOOR_CP = 150          # D_LIVE_SEE_FLOOR_CP
CP_LOSS_FLOOR = 150         # D_LIVE_CP_LOSS_FLOOR
ADVERSARIAL_BAND_CP = 40    # how close to a floor counts as adversarial

TARGET_NON_OPPORTUNITIES = 40   # bar is 20; collect double
TARGET_ADVERSARIAL = 40


def _cp(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def board_truth(fen_before: str, move_uci: str) -> Optional[Dict[str, Any]]:
    """Re-derive hang facts from the board. None when the row is unusable.

    material_hung_after reports only the WORST outcome and returns no capture
    move when nothing is actually hanging -- so a properly defended piece
    (the most meaningful true negative) is invisible through it alone. The
    opponent's captures are therefore enumerated directly, and best_capture_see
    records what the best capture is actually worth to them.
    """
    from coach_play.coach_blunder_guard import material_hung_after, see_gain

    try:
        board = chess.Board(fen_before)
        move = chess.Move.from_uci(move_uci)
    except (ValueError, TypeError):
        return None
    if move not in board.legal_moves:
        return None
    if board.piece_type_at(move.from_square) == chess.KING:
        return {"skip": "king_move"}
    try:
        worst_cp, capture = material_hung_after(board, move)
    except (ValueError, AttributeError, IndexError):
        return None

    after = board.copy(stack=False)
    after.push(move)
    captures = [m for m in after.legal_moves if after.is_capture(m)]
    best_see = None
    best_capture = None
    for candidate in captures:
        try:
            gain = see_gain(after, candidate)
        except (ValueError, AttributeError, IndexError):
            continue
        if best_see is None or gain > best_see:
            best_see, best_capture = gain, candidate

    return {
        "see_cp": int(worst_cp or 0),
        "capture_uci": capture.uci() if capture else None,
        "opponent_has_capture": bool(captures),
        "best_capture_uci": best_capture.uci() if best_capture else None,
        "best_capture_see": int(best_see) if best_see is not None else None,
        "skip": None,
    }


def classify(see_cp: int, cp_loss: Optional[float]) -> Dict[str, Any]:
    """The detector's own two-gate decision, plus why a negative is negative."""
    loss = cp_loss if cp_loss is not None else 0.0
    is_hang = see_cp >= SEE_FLOOR_CP and loss >= CP_LOSS_FLOOR
    if is_hang:
        return {"is_hang": True, "reason": "both_gates_met"}
    if see_cp <= 0:
        reason = "defended"
    elif see_cp < SEE_FLOOR_CP:
        reason = "below_floor"
    else:
        reason = "compensated"      # material loose, engine says it costs little
    return {"is_hang": False, "reason": reason}


def near_a_floor(see_cp: int, cp_loss: Optional[float]) -> bool:
    loss = cp_loss if cp_loss is not None else 0.0
    return (
        abs(see_cp - SEE_FLOOR_CP) <= ADVERSARIAL_BAND_CP
        or abs(loss - CP_LOSS_FLOOR) <= ADVERSARIAL_BAND_CP
    )


async def collect(limit: int) -> Dict[str, Any]:
    url = os.environ.get("MONGO_URL")
    if not url:
        raise SystemExit("MONGO_URL is required")
    client = AsyncIOMotorClient(url, serverSelectionTimeoutMS=8000)
    db = client[os.environ.get("DB_NAME", "chess_coach")]

    stats: Counter = Counter()
    negatives: List[Dict[str, Any]] = []
    adversarial: List[Dict[str, Any]] = []
    seen_fens = set()

    cursor = db.game_analyses.find(
        {"stockfish_analysis.move_evaluations.0": {"$exists": True}},
        {"game_id": 1, "user_id": 1, "stockfish_analysis.move_evaluations": 1},
    ).limit(limit)

    async for doc in cursor:
        stats["games"] += 1
        for mv in doc.get("stockfish_analysis", {}).get("move_evaluations", []):
            if mv.get("is_opponent_move"):
                continue
            fen, uci = mv.get("fen_before"), mv.get("move_uci")
            if not fen or not uci:
                continue
            stats["moves"] += 1
            truth = board_truth(fen, uci)
            if truth is None:
                stats["unusable"] += 1
                continue
            if truth.get("skip"):
                stats[truth["skip"]] += 1
                continue

            see_cp = truth["see_cp"]
            cp_loss = _cp(mv.get("cp_loss"))
            verdict = classify(see_cp, cp_loss)
            stats["hang" if verdict["is_hang"] else "not_hang"] += 1

            key = fen.split(" ")[0] + uci
            if key in seen_fens:
                continue

            case = {
                "game_id": doc.get("game_id"),
                "user_id": doc.get("user_id"),
                "fen_before": fen,
                "move_uci": uci,
                "move_san": mv.get("move"),
                "see_cp": see_cp,
                "cp_loss": cp_loss,
                "opponent_capture_uci": truth["capture_uci"],
                "best_capture_uci": truth["best_capture_uci"],
                "best_capture_see": truth["best_capture_see"],
                "detector_says_hang": verdict["is_hang"],
                "reason": verdict["reason"],
            }

            # A non-opportunity must have a real capture available to the
            # opponent, else it is a quiet move and proves nothing about
            # restraint. "Defended" cases have a capture whose SEE is <= 0.
            if (
                not verdict["is_hang"]
                and truth["opponent_has_capture"]
                and len(negatives) < TARGET_NON_OPPORTUNITIES
            ):
                negatives.append(case)
                seen_fens.add(key)
                stats[f"negative:{verdict['reason']}"] += 1
            elif near_a_floor(see_cp, cp_loss) and len(adversarial) < TARGET_ADVERSARIAL:
                adversarial.append(case)
                seen_fens.add(key)
                stats["adversarial"] += 1

        if (
            len(negatives) >= TARGET_NON_OPPORTUNITIES
            and len(adversarial) >= TARGET_ADVERSARIAL
        ):
            break

    client.close()
    return {
        "schema_version": "simple_hang_caption_packet.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "quality_id": "gap:piece_safety:simple_hang",
        "thresholds": {
            "see_floor_cp": SEE_FLOOR_CP,
            "cp_loss_floor": CP_LOSS_FLOOR,
            "adversarial_band_cp": ADVERSARIAL_BAND_CP,
        },
        "counts": dict(stats),
        "non_opportunities": negatives,
        "adversarial": adversarial,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=4000,
                        help="max game_analyses documents to scan")
    args = parser.parse_args()

    packet = asyncio.run(collect(args.limit))
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(packet, indent=1), encoding="utf-8")

    counts = packet["counts"]
    print(f"scanned games={counts.get('games', 0)} moves={counts.get('moves', 0)}")
    print(f"  hang={counts.get('hang', 0)} not_hang={counts.get('not_hang', 0)}")
    print(f"non_opportunities={len(packet['non_opportunities'])} "
          f"(bar is 20)")
    for reason in ("defended", "compensated", "below_floor"):
        print(f"  {reason}={counts.get(f'negative:{reason}', 0)}")
    print(f"adversarial={len(packet['adversarial'])}")
    print(f"written -> {OUT_PATH}")


if __name__ == "__main__":
    main()
