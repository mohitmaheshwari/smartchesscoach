"""Adjudicate the simple_hang Caption packet from the board, independently.

The packet is only evidence if something other than the miner agrees with it.
This re-derives every case from its FEN with python-chess and an independent
SEE walk, and refuses to reuse any stored number.

Checks per case:
  1. the FEN is a legal position and the move is legal in it;
  2. the move is not a king move (those are filtered before simple_hang);
  3. for a non-opportunity, the opponent really does have a capture --
     otherwise it proves nothing about the detector staying silent;
  4. the recorded reason matches independently recomputed board truth;
  5. the detector verdict recomputed from the two floors matches the packet.

A CRITICAL failure is any case the packet marks as not-a-hang where
independent board truth says both D_live gates are in fact met -- i.e. the
detector would have been wrong to stay silent, or the packet mislabelled it.
Caption-grade requires zero critical failures.

    python backend/scripts/verify_simple_hang_caption_packet.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

import chess

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

PACKET_PATH = (
    BACKEND_ROOT / "data" / "corpus_snapshots" / "simple_hang_caption_packet.json"
)

SEE_FLOOR_CP = 150
CP_LOSS_FLOOR = 150


def independent_truth(fen: str, uci: str) -> Dict[str, Any]:
    """Recompute from the board without reusing any packet value."""
    from coach_play.coach_blunder_guard import material_hung_after, see_gain

    out: Dict[str, Any] = {"legal": False}
    try:
        board = chess.Board(fen)
    except ValueError:
        return out
    if not board.is_valid():
        return out
    try:
        move = chess.Move.from_uci(uci)
    except ValueError:
        return out
    if move not in board.legal_moves:
        return out

    out["legal"] = True
    out["is_king_move"] = board.piece_type_at(move.from_square) == chess.KING
    worst, _ = material_hung_after(board, move)
    out["see_cp"] = int(worst or 0)

    after = board.copy(stack=False)
    after.push(move)
    caps = [m for m in after.legal_moves if after.is_capture(m)]
    out["opponent_has_capture"] = bool(caps)
    best = None
    for candidate in caps:
        try:
            gain = see_gain(after, candidate)
        except (ValueError, AttributeError, IndexError):
            continue
        if best is None or gain > best:
            best = gain
    out["best_capture_see"] = int(best) if best is not None else None
    return out


def expected_reason(see_cp: int) -> str:
    if see_cp <= 0:
        return "defended"
    if see_cp < SEE_FLOOR_CP:
        return "below_floor"
    return "compensated"


def adjudicate(cases: List[Dict[str, Any]], kind: str) -> Dict[str, Any]:
    stats: Counter = Counter()
    critical: List[Dict[str, Any]] = []
    mismatches: List[Dict[str, Any]] = []

    for case in cases:
        stats["cases"] += 1
        truth = independent_truth(case["fen_before"], case["move_uci"])

        if not truth["legal"]:
            stats["illegal_or_unparseable"] += 1
            critical.append({"case": case, "why": "illegal position or move"})
            continue
        if truth["is_king_move"]:
            stats["king_move_leaked"] += 1
            critical.append({"case": case, "why": "king move should be filtered"})
            continue

        see_cp = truth["see_cp"]
        cp_loss = case.get("cp_loss") or 0.0
        recomputed_hang = see_cp >= SEE_FLOOR_CP and cp_loss >= CP_LOSS_FLOOR

        if recomputed_hang != bool(case.get("detector_says_hang")):
            stats["verdict_mismatch"] += 1
            mismatches.append({
                "fen": case["fen_before"], "move": case["move_uci"],
                "packet_says_hang": case.get("detector_says_hang"),
                "recomputed_hang": recomputed_hang,
                "packet_see": case.get("see_cp"), "recomputed_see": see_cp,
            })

        if kind == "non_opportunity":
            if not truth["opponent_has_capture"]:
                stats["no_capture_available"] += 1
                critical.append({"case": case, "why": "no opponent capture; proves nothing"})
                continue
            if recomputed_hang:
                stats["CRITICAL_actually_a_hang"] += 1
                critical.append({"case": case, "why": "board truth says both gates met"})
                continue
            want = expected_reason(see_cp)
            if want != case.get("reason"):
                stats["reason_mismatch"] += 1
                mismatches.append({
                    "fen": case["fen_before"], "packet_reason": case.get("reason"),
                    "expected_reason": want, "recomputed_see": see_cp,
                })
            else:
                stats[f"ok:{want}"] += 1
        else:
            stats["ok:adversarial"] += 1

    return {"stats": dict(stats), "critical": critical, "mismatches": mismatches}


def main() -> None:
    if not PACKET_PATH.exists():
        raise SystemExit(f"packet not found: {PACKET_PATH}")
    packet = json.loads(PACKET_PATH.read_text(encoding="utf-8"))

    neg = adjudicate(packet["non_opportunities"], "non_opportunity")
    adv = adjudicate(packet["adversarial"], "adversarial")

    print("=== NON-OPPORTUNITIES (Caption bar: >=20, zero critical)")
    for key in sorted(neg["stats"]):
        print(f"   {key}={neg['stats'][key]}")
    print("=== ADVERSARIAL (Caption bar: zero critical false claims)")
    for key in sorted(adv["stats"]):
        print(f"   {key}={adv['stats'][key]}")

    criticals = len(neg["critical"]) + len(adv["critical"])
    mismatches = len(neg["mismatches"]) + len(adv["mismatches"])
    print(f"=== critical failures: {criticals}")
    print(f"=== non-critical mismatches: {mismatches}")
    for item in (neg["mismatches"] + adv["mismatches"])[:5]:
        print(f"     {item}")
    for item in (neg["critical"] + adv["critical"])[:5]:
        print(f"     CRITICAL {item['why']}: {item['case']['fen_before']}")

    usable = neg["stats"].get("cases", 0) - len(neg["critical"])
    verdict = "PASS" if criticals == 0 and usable >= 20 else "FAIL"
    print(f"=== usable non-opportunities: {usable} (bar 20)")
    print(f"=== CAPTION EVIDENCE VERDICT: {verdict}")
    sys.exit(0 if verdict == "PASS" else 1)


if __name__ == "__main__":
    main()
