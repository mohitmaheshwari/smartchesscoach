"""Categorize the 40 residual_low caption MDs against the patterns
established via Mohit's approved-caption-rewrites session.

After 4 approvals (Qe2/d4, e4/Nh4, Bb5/Nxe5, Bf1/d3) we have four
recognizable pattern families. Each residual_low position can be
classified into one of them — which tells Mohit what to review
manually vs. what's already handled.

Categories:
  A — attack-with-tempo: engine's best move attacks a piece (opp's
      first PV reply moves that same piece away). Well-understood;
      we already have the approved caption shape.
  B — clearance_then_check: v56 detector handles this. Mohit doesn't
      need to review these MDs — they'll auto-improve to HIGH on the
      next regen.
  C — un-developing principle: user's played move returns a piece
      to its starting home square (e.g. Bf1 from e2). New detector
      candidate; need a few more examples to lock the spec.
  D — novel: doesn't fit any of the above. Needs human judgment.

Run inside container:
    python /app/backend/scripts/categorize_residual_low.py \\
        --residual-dir /app/docs/caption_backlog_500/residual_low \\
        --out /tmp/categorized_review_queue.md
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from typing import Optional

import chess

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from services.shape_detectors import (
    simulate_clearance_then_check,
    simulate_clearance_for_attack,
)


# Starting-rank home squares for non-pawn pieces (used by category C).
HOME_SQUARES_WHITE = {"Ra1", "Nb1", "Bc1", "Qd1", "Ke1", "Bf1", "Ng1", "Rh1"}
HOME_SQUARES_BLACK = {"Ra8", "Nb8", "Bc8", "Qd8", "Ke8", "Bf8", "Ng8", "Rh8"}


def _parse_md(path: str) -> Optional[dict]:
    """Extract FEN, played move, engine best, caption, and engine PV
    from a residual_low MD file."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except Exception:
        return None

    fen_m = re.search(r"\*\*Position \(FEN\):\*\*\s*`([^`]+)`", text)
    played_m = re.search(r"\*\*Move played:\*\*\s*`([^`]+)`\s*\(cp_loss\s*`(\d+)`", text)
    best_m = re.search(r"\*\*Engine's best \(stored\):\*\*\s*`([^`]+)`", text)
    color_m = re.search(r"\*\*User color:\*\*\s*(\w+)", text)
    pv_m = re.search(r"#1 eval\(W\)\s*`([+-]?\d+)cp`\s*PV:\s*`([^`]+)`", text)

    if not (fen_m and played_m and best_m):
        return None

    return {
        "fen": fen_m.group(1),
        "played_san": played_m.group(1),
        "cp_loss": int(played_m.group(2)),
        "best_san": best_m.group(1),
        "user_color": (color_m.group(1) if color_m else "white"),
        "pv1_eval_cp": int(pv_m.group(1)) if pv_m else None,
        "pv1_moves": pv_m.group(2).split() if pv_m else [],
        "path": path,
    }


def _is_pattern_b_clearance_then_check(pos: dict) -> Optional[dict]:
    """Returns evidence dict if the v56 clearance_then_check detector
    will fire on the engine's best move from the pre-move position."""
    try:
        ev = simulate_clearance_then_check(pos["fen"], pos["best_san"])
        return ev[0] if ev else None
    except Exception:
        return None


def _is_pattern_b_clearance_for_attack(pos: dict) -> Optional[dict]:
    """1-move clearance — already shipped in v53."""
    try:
        ev = simulate_clearance_for_attack(pos["fen"], pos["best_san"])
        return ev[0] if ev else None
    except Exception:
        return None


def _is_pattern_a_attack_with_tempo(pos: dict) -> Optional[dict]:
    """Engine's best move attacks a piece; the opponent's first PV
    reply moves THAT same piece away. Heuristic: parse PV, check that
    PV[0]'s destination square attacks a square containing the piece
    that moves in PV[1].

    Returns evidence dict (attacker_piece, target_piece, target_sq)
    or None.
    """
    pv = pos["pv1_moves"]
    if len(pv) < 2:
        return None
    try:
        board = chess.Board(pos["fen"])
        mv0 = board.parse_san(pv[0])
        # Compute squares attacked by the piece on mv0.to_square AFTER
        # the move (i.e. the new attack pattern).
        board_after = board.copy()
        board_after.push(mv0)
        attacked_squares = board_after.attacks(mv0.to_square)

        # Parse opponent's reply
        mv1 = board_after.parse_san(pv[1])
        # Is the FROM square of mv1 in the attacked set?
        if mv1.from_square in attacked_squares:
            piece_at_from = board_after.piece_at(mv1.from_square)
            # In python-chess after .push(mv1) the piece has moved, but
            # we computed attacked_squares BEFORE pushing mv1, and we
            # accessed piece_at on board_after which is post-mv0 / pre-mv1.
            # So piece_at_from is the piece that's about to move.
            piece_type_name = chess.piece_name(piece_at_from.piece_type) if piece_at_from else "?"
            return {
                "best_move_piece_to": chess.square_name(mv0.to_square),
                "attacked_piece": piece_type_name,
                "attacked_square": chess.square_name(mv1.from_square),
                "opp_reply": pv[1],
            }
    except Exception:
        return None
    return None


def _is_pattern_c_undeveloping(pos: dict) -> Optional[dict]:
    """User played a piece move that returns a non-pawn piece to its
    starting home square. Heuristic: parse played_san, get from + to
    squares. If to_square is a home square for that piece AND that
    square was originally a home square for the same color's piece
    of the same type, classify as un-developing.

    Returns evidence dict or None.
    """
    san = pos["played_san"]
    if san.startswith(("O-O", "O-O-O")):
        return None
    if not san or not san[0].isupper() or san[0] == "K":
        return None  # not a non-king piece move

    try:
        board = chess.Board(pos["fen"])
        mv = board.parse_san(san)
        moved_piece = board.piece_at(mv.from_square)
        if moved_piece is None:
            return None
        # Build SAN-style square names for the home squares.
        to_sq_name = chess.square_name(mv.to_square)
        piece_san = san[0] + to_sq_name  # crude form e.g. "Bf1"
        home_set = HOME_SQUARES_WHITE if board.turn == chess.WHITE else HOME_SQUARES_BLACK
        # Match against home squares (loose — strip captures / disambig)
        for home in home_set:
            if home == piece_san:
                return {
                    "from_square": chess.square_name(mv.from_square),
                    "to_square": to_sq_name,
                    "piece_type": chess.piece_name(moved_piece.piece_type),
                }
    except Exception:
        return None
    return None


def categorize(pos: dict) -> dict:
    """Run all classifiers; return the first matching category."""
    # Order matters — most specific first.
    ev = _is_pattern_b_clearance_then_check(pos)
    if ev:
        return {"category": "B-then-check", "evidence": ev}
    ev = _is_pattern_b_clearance_for_attack(pos)
    if ev:
        return {"category": "B-1move", "evidence": ev}
    ev = _is_pattern_a_attack_with_tempo(pos)
    if ev:
        return {"category": "A-tempo", "evidence": ev}
    ev = _is_pattern_c_undeveloping(pos)
    if ev:
        return {"category": "C-undeveloping", "evidence": ev}
    return {"category": "D-novel", "evidence": None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--residual-dir", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    files = sorted(
        os.path.join(args.residual_dir, f)
        for f in os.listdir(args.residual_dir)
        if f.endswith(".md") and f != "README.md"
    )

    buckets: dict[str, list[dict]] = {
        "A-tempo": [],
        "B-then-check": [],
        "B-1move": [],
        "C-undeveloping": [],
        "D-novel": [],
    }

    for path in files:
        pos = _parse_md(path)
        if not pos:
            continue
        result = categorize(pos)
        buckets[result["category"]].append({
            "pos": pos,
            "evidence": result.get("evidence"),
            "file": os.path.basename(path),
        })

    lines = ["# Residual LOW captions — prioritized review queue\n"]
    lines.append("Categorized after 4 approved captions (Qe2/d4, e4/Nh4, "
                 "Bb5/Nxe5, Bf1/d3) established four pattern families. "
                 "Categorization runs the v56 `clearance_then_check` detector "
                 "+ heuristic classifiers for the other patterns.\n")
    lines.append("**Read order: D → C → A → B.** D needs Mohit's judgment; "
                 "B is already handled by v56 (will auto-improve on next regen).\n")
    lines.append("---\n")

    section_titles = {
        "D-novel": ("D — Novel patterns (need your judgment)",
                    "Doesn't fit any established family. Review these first — "
                    "each may surface a new detector or template."),
        "C-undeveloping": ("C — Un-developing principle violations",
                           "User returned a developed piece to its home "
                           "square. New detector candidate; review 2-3 to "
                           "lock the spec, then we can build it."),
        "A-tempo": ("A — Attack-with-tempo (well-understood pattern)",
                    "Same family as Qe2/d4 and e4/Nh4. Approved-caption "
                    "shape: name the piece attacked + the follow-up resource. "
                    "Review 1-2 to confirm, then we can batch-apply the "
                    "template or build a detector."),
        "B-then-check": ("B — Légal's-family clearance_then_check (v56-FIXED)",
                         "v56 detector handles these automatically on next "
                         "regen. **Skip the manual review.**"),
        "B-1move": ("B — 1-move clearance_for_attack (already detected pre-v53)",
                    "Already handled by the surviving 1-move clearance "
                    "detector. If they still showed up in residual_low, the "
                    "eval-guard or coordination check missed — surface as "
                    "borderline."),
    }

    for cat in ("D-novel", "C-undeveloping", "A-tempo", "B-then-check", "B-1move"):
        items = buckets[cat]
        title, blurb = section_titles[cat]
        lines.append(f"## {title} — {len(items)} positions\n")
        lines.append(f"_{blurb}_\n")
        if not items:
            lines.append("(none)\n")
            continue
        for it in items:
            pos = it["pos"]
            ev = it["evidence"] or {}
            fen_url = pos["fen"].replace(" ", "_")
            lichess = f"https://lichess.org/analysis/standard/{fen_url}"
            lines.append(f"- [{it['file']}](residual_low/{it['file']}) — "
                         f"`{pos['played_san']}` vs engine `{pos['best_san']}` "
                         f"(cp_loss {pos['cp_loss']}, {pos['user_color']}) "
                         f"[lichess]({lichess})")
            if ev:
                if cat == "A-tempo":
                    lines.append(f"  - best move attacks `{ev['attacked_piece']}` on "
                                 f"`{ev['attacked_square']}`, opp reply `{ev['opp_reply']}`")
                elif cat == "B-then-check":
                    lines.append(f"  - v56 will produce: opens line → "
                                 f"`{ev.get('follow_up_san','?')}` chases king on "
                                 f"`{ev.get('king_square','?')}`")
                elif cat == "C-undeveloping":
                    lines.append(f"  - {ev['piece_type']} retreated from "
                                 f"`{ev['from_square']}` to home `{ev['to_square']}`")
        lines.append("")

    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"Wrote {args.out}")
    for cat in ("D-novel", "C-undeveloping", "A-tempo", "B-then-check", "B-1move"):
        print(f"  {cat:18s} {len(buckets[cat])}")


if __name__ == "__main__":
    main()
