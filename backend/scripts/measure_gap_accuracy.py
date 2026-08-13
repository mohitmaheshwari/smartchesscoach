"""measure_gap_accuracy.py — GROUND-TRUTH accuracy harness for cognitive_gap.

docs/reasoning_correctness_scope.md. The cognitive_gap classifier
(analysis_interpreter.py) assigns a label from move-type PROXIES and stamps a
HARDCODED confidence — never measured. This harness derives the ENGINE-VERIFIED
cause of each user mistake from the stored PVs (pv_after_played = the opponent's
forced refutation; pv_after_best = what the user missed) using pure python-chess
material accounting, then cross-checks it against the stored label.

The point is not to grade every fuzzy positional call — it's to find, per category,
what fraction of mistakes have a HARD, verifiable cause (a material swing in the
engine's own line) and whether the stored label agrees. That tells us which tags are
shippable at ~100% truth (verifiable) vs which must abstain (positional residue).

Run:  python -m scripts.measure_gap_accuracy   (from backend/)
"""
import os
import asyncio
from collections import Counter, defaultdict

import chess
from motor.motor_asyncio import AsyncIOMotorClient

PROD = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
VAL = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0}

# A material swing this large (pawns) over the engine's forced line counts as a real,
# verifiable material cause (a hang / dropped tactic / won-tactic-missed).
MATERIAL_CP = 1.5

# The categories the classifier treats as material/tactical vs positional.
MATERIAL_LABELS = {"piece_safety", "tactical_oversight", "missed_tactic"}
POSITIONAL_LABELS = {"piece_activity", "pawn_structure", "calculation_depth",
                     "opening_knowledge", "endgame_technique", "king_safety"}


def _mat(board, color):
    return sum(VAL[p.piece_type] for p in board.piece_map().values() if p.color == color)


def _swing_over_line(fen_before, first_move_san, pv_sans, user_color):
    """User-POV material delta from fen_before, through first_move + the pv line.
    Negative = the user is DOWN material at the end of the forced line."""
    b = chess.Board(fen_before)
    before = _mat(b, user_color) - _mat(b, not user_color)
    try:
        b.push_san(first_move_san)
    except Exception:
        return None
    for san in (pv_sans or []):
        try:
            b.push_san(san)
        except Exception:
            break
    after = _mat(b, user_color) - _mat(b, not user_color)
    return after - before


def verified_cause(m):
    """Return one of: 'material_loss' | 'missed_gain' | 'positional' | None(unusable)."""
    fen = m.get("fen_before")
    played = m.get("move")
    best = m.get("best_move")
    if not fen or not played:
        return None
    try:
        user_color = chess.Board(fen).turn
    except Exception:
        return None
    swing_played = _swing_over_line(fen, played, m.get("pv_after_played"), user_color)
    if swing_played is None:
        return None
    if swing_played <= -MATERIAL_CP:
        return "material_loss"
    swing_best = None
    if best:
        swing_best = _swing_over_line(fen, best, m.get("pv_after_best"), user_color)
    if swing_best is not None and (swing_best - swing_played) >= MATERIAL_CP:
        return "missed_gain"
    return "positional"


async def main():
    db = AsyncIOMotorClient(PROD)["chess_coach"]
    n = 0
    verified_counts = Counter()
    label_vs_verified = defaultdict(Counter)   # stored label -> verified cause counts
    cur = db.game_analyses.find({}, {"_id": 0, "stockfish_analysis.move_evaluations": 1}).limit(600)
    async for a in cur:
        for m in (a.get("stockfish_analysis") or {}).get("move_evaluations") or []:
            if m.get("is_opponent_move"):
                continue
            g = m.get("cognitive_gap")
            if not g or abs(int(m.get("cp_loss") or 0)) < 100:
                continue
            vc = verified_cause(m)
            if vc is None:
                continue
            n += 1
            verified_counts[vc] += 1
            label_vs_verified[g][vc] += 1

    print(f"sampled {n} user mistakes (cp_loss >= 100) with usable PVs\n")
    print("VERIFIABLE vs POSITIONAL (the shippable fraction):")
    for k in ("material_loss", "missed_gain", "positional"):
        print(f"  {k:14} {verified_counts[k]:5} ({round(100*verified_counts[k]/max(n,1))}%)")
    verifiable = verified_counts["material_loss"] + verified_counts["missed_gain"]
    print(f"  >>> verifiable (hard cause): {verifiable}/{n} = {round(100*verifiable/max(n,1))}%\n")

    print("STORED LABEL vs VERIFIED CAUSE (mislabels jump out):")
    print(f"  {'label':20} {'n':>4}  {'material_loss':>13} {'missed_gain':>11} {'positional':>10}   verdict")
    for g in sorted(label_vs_verified, key=lambda x: -sum(label_vs_verified[x].values())):
        cc = label_vs_verified[g]
        tot = sum(cc.values())
        ml, mg, po = cc["material_loss"], cc["missed_gain"], cc["positional"]
        # a MATERIAL label that's mostly positional (or vice-versa) is suspicious
        verdict = ""
        if g in MATERIAL_LABELS and po > (ml + mg):
            verdict = f"⚠ {round(100*po/tot)}% have NO material cause"
        if g == "piece_activity" and (ml + mg) > po:
            verdict = f"⚠ {round(100*(ml+mg)/tot)}% actually LOST/MISSED material (not 'activity')"
        if g in ("opening_knowledge", "king_safety") and ml > po:
            verdict = f"⚠ {round(100*ml/tot)}% actually dropped material (tactical, not '{g}')"
        print(f"  {g:20} {tot:>4}  {ml:>13} {mg:>11} {po:>10}   {verdict}")


if __name__ == "__main__":
    asyncio.run(main())
