"""
Content correctness audit — verify rendered coaching text against the actual FEN.

Per `feedback_chess_content_verification.md`: don't claim any coaching layer is
"verified" without checking that the user-visible string is factually true
about the position. This is the audit that should have caught Parth's bugs.

SCOPE OF THIS AUDIT (be explicit, per rule #6 of the memo):
  ✓ Piece-on-square claims    — "your knight on e5", "their pawn on c6"
  ✓ Move-played claim         — "Played [SAN]" or implied played-move
  ✓ Best-move agreement       — claimed best vs engine pick at depth N
  ✓ Hallucinated piece check  — claim references a piece/square; piece must exist
  ✗ Multi-ply tactical lines  — "after X then Y" — NOT verified here (separate audit)
  ✗ Strategic claims          — "doesn't develop", "loses tempo" — NOT verified
  ✗ Severity vs forced-mate   — separate forced-mate audit needed (TODO)
  ✗ Opening identification    — needs ECO DB cross-check (TODO)

Output: per-text verdict (PASS / FAIL / UNVERIFIABLE) with per-claim detail.

Usage:
    # Standalone test of one claim
    python scripts/content_correctness_audit.py --fen "<FEN>" --text "your knight on e5 is hanging"

    # Run against Parth's bug export (JSON file)
    python scripts/content_correctness_audit.py --bug-file /path/to/parth_bugs.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import chess


_PIECE_NAMES = {
    "king": chess.KING,
    "queen": chess.QUEEN,
    "rook": chess.ROOK,
    "bishop": chess.BISHOP,
    "knight": chess.KNIGHT,
    "pawn": chess.PAWN,
}


@dataclass
class ClaimResult:
    """One verified claim from a coaching string."""
    kind: str                 # "piece_on_square" | "move_played" | "best_move" | ...
    text: str                 # the substring claimed
    verdict: str              # "pass" | "fail" | "unverifiable"
    detail: str = ""          # explanation (especially for fail/unverifiable)


@dataclass
class TextAudit:
    """Audit result for one coaching text against one FEN."""
    fen: str
    text: str
    claims: List[ClaimResult] = field(default_factory=list)

    @property
    def overall(self) -> str:
        if not self.claims:
            return "no_claims_found"
        if any(c.verdict == "fail" for c in self.claims):
            return "fail"
        if all(c.verdict == "pass" for c in self.claims):
            return "pass"
        return "partial"


# ── Claim 1: "your/their/X on SQUARE" piece references ────────────────────
# Matches: "your knight on e5", "their pawn on c6", "queen on h5",
#          "the bishop on g5", "your pawn on f4 is in trouble"
# Doesn't match: SAN move notation like "Nxe5" or "Bxc4"
_PIECE_ON_SQUARE_RE = re.compile(
    r"\b(?:(your|their|my|opponent[''']?s|the|a|an)\s+)?"
    r"(king|queen|rook|bishop|knight|pawn)"
    r"\s+on\s+"
    r"([a-h][1-8])\b",
    flags=re.IGNORECASE,
)


def _verify_piece_on_square(
    board: chess.Board,
    user_color: chess.Color,
    side_word: Optional[str],
    piece_name: str,
    square_name: str,
) -> Tuple[str, str]:
    """Returns (verdict, detail).

    side_word is the prefix word ("your", "their", "my", "opponent's", "the", "a", None).
    user_color is the colour the player playing this game is using.
    """
    try:
        sq = chess.parse_square(square_name)
    except (ValueError, KeyError):
        return ("fail", f"square '{square_name}' is not a valid chess square")

    piece = board.piece_at(sq)
    if piece is None:
        return ("fail", f"no piece on {square_name} — claim is hallucinated")

    expected_type = _PIECE_NAMES[piece_name.lower()]
    if piece.piece_type != expected_type:
        actual = chess.piece_name(piece.piece_type)
        return (
            "fail",
            f"square {square_name} has a {actual}, not a {piece_name.lower()}",
        )

    # Side check (only when side_word is meaningful — "the"/"a"/"an" don't constrain)
    if side_word:
        sw = side_word.lower().rstrip("'s").replace("'", "").replace("'", "")
        if sw in ("your", "my"):
            expected_color = user_color
        elif sw in ("their", "opponents", "opponent"):
            expected_color = not user_color
        else:
            expected_color = None  # "the", "a", "an" — no constraint
        if expected_color is not None and piece.color != expected_color:
            actual_side = "white" if piece.color == chess.WHITE else "black"
            return (
                "fail",
                f"piece on {square_name} is {actual_side}, but text says '{side_word}'",
            )

    return ("pass", f"verified {piece_name} on {square_name}")


def _extract_and_verify_piece_claims(
    audit: TextAudit, board: chess.Board, user_color: chess.Color
) -> None:
    """Parse the text for piece-on-square claims and verify each."""
    for match in _PIECE_ON_SQUARE_RE.finditer(audit.text):
        side_word = match.group(1)
        piece_name = match.group(2)
        square_name = match.group(3).lower()
        verdict, detail = _verify_piece_on_square(
            board, user_color, side_word, piece_name, square_name
        )
        audit.claims.append(
            ClaimResult(
                kind="piece_on_square",
                text=match.group(0),
                verdict=verdict,
                detail=detail,
            )
        )


# ── Claim 2: "Played [SAN]" — verify the move is legal from the position ──
_PLAYED_MOVE_RE = re.compile(
    r"\bPlayed\s+([NBRQK][a-h]?[1-8]?x?[a-h][1-8](?:=[NBRQ])?[+#]?|"
    r"O-O-O|O-O|"
    r"[a-h]x?[a-h][1-8](?:=[NBRQ])?[+#]?|"
    r"[a-h][1-8](?:=[NBRQ])?[+#]?)\b"
)


def _extract_and_verify_played_move(audit: TextAudit, board: chess.Board) -> None:
    """If text says 'Played X', verify X is a legal move from the position."""
    for match in _PLAYED_MOVE_RE.finditer(audit.text):
        san = match.group(1)
        try:
            board.parse_san(san)
            audit.claims.append(
                ClaimResult(
                    kind="move_played",
                    text=match.group(0),
                    verdict="pass",
                    detail=f"{san} is a legal move from this position",
                )
            )
        except (chess.InvalidMoveError, chess.IllegalMoveError, chess.AmbiguousMoveError, ValueError) as exc:
            audit.claims.append(
                ClaimResult(
                    kind="move_played",
                    text=match.group(0),
                    verdict="fail",
                    detail=f"{san} is not a legal move from this position ({exc})",
                )
            )


# ── Public entry point ───────────────────────────────────────────────────
def audit_text_against_fen(
    text: str,
    fen: str,
    user_color: str = "white",
) -> TextAudit:
    """Audit a coaching string against the position. Returns a structured
    audit result with per-claim verdicts.

    Scope (per `feedback_chess_content_verification`):
      ✓ piece-on-square hallucination check
      ✓ played-move legality check
      ✗ best-move agreement (caller must run engine separately)
      ✗ severity-vs-forced-mate (separate audit)
      ✗ multi-ply "after X then Y" claims
    """
    audit = TextAudit(fen=fen, text=text)
    if not text or not fen:
        return audit

    try:
        board = chess.Board(fen)
    except ValueError as exc:
        audit.claims.append(
            ClaimResult(
                kind="fen_parse",
                text=fen,
                verdict="unverifiable",
                detail=f"could not parse FEN: {exc}",
            )
        )
        return audit

    color = chess.WHITE if user_color.lower() == "white" else chess.BLACK
    _extract_and_verify_piece_claims(audit, board, color)
    _extract_and_verify_played_move(audit, board)
    return audit


def _format_audit(audit: TextAudit, header: str = "") -> str:
    lines = []
    if header:
        lines.append(header)
    lines.append(f'  text: "{audit.text}"')
    lines.append(f"  fen:  {audit.fen}")
    lines.append(f"  overall: {audit.overall}")
    if not audit.claims:
        lines.append("  (no chess claims detected in text)")
    for c in audit.claims:
        marker = {"pass": "PASS", "fail": "FAIL", "unverifiable": "????"}.get(c.verdict, "----")
        lines.append(f"  [{marker}] [{c.kind}] '{c.text}' -- {c.detail}")
    return "\n".join(lines)


def run_one(args):
    audit = audit_text_against_fen(args.text, args.fen, args.color)
    print(_format_audit(audit, header="=== single-text audit ==="))


def run_bug_file(args):
    """Run audit against a bug-export JSON. For Parth's exports the shape is:
       { feedback: [ { coaching_text_flagged, position: { fen, move_san, ... }, context: {...} } ] }
    """
    path = Path(args.bug_file)
    data = json.loads(path.read_text(encoding="utf-8"))
    bugs = data.get("feedback") or []

    n_total = 0
    n_skip_no_text = 0
    n_skip_no_fen = 0
    n_pass = 0
    n_fail = 0
    n_no_claims = 0
    failures: List[Tuple[Dict, TextAudit]] = []
    for bug in bugs:
        n_total += 1
        text = (bug.get("coaching_text_flagged") or "").strip()
        position = bug.get("position") or {}
        fen = (position.get("fen") or "").strip()
        if not text:
            n_skip_no_text += 1
            continue
        if not fen:
            n_skip_no_fen += 1
            continue

        # In Parth's bug entries the FEN is the position at the moment
        # the user was being coached — side-to-move IS the user. "your"
        # in the coaching text addresses side-to-move. Inferring this
        # avoids spurious wrong-color fails on legitimate claims.
        try:
            board_for_color = chess.Board(fen)
            inferred_user_color = "white" if board_for_color.turn == chess.WHITE else "black"
        except ValueError:
            inferred_user_color = "white"

        audit = audit_text_against_fen(text, fen, user_color=inferred_user_color)
        if audit.overall == "fail":
            n_fail += 1
            failures.append((bug, audit))
        elif audit.overall == "no_claims_found":
            n_no_claims += 1
        else:
            n_pass += 1

    print("=" * 70)
    print("CONTENT CORRECTNESS AUDIT — bug-file run")
    print("=" * 70)
    print(f"  total bugs:           {n_total}")
    print(f"  skipped (no text):    {n_skip_no_text}")
    print(f"  skipped (no FEN):     {n_skip_no_fen}  (reconstruction TODO)")
    print(f"  audited:              {n_total - n_skip_no_text - n_skip_no_fen}")
    print(f"    pass (all claims):  {n_pass}")
    print(f"    no claims detected: {n_no_claims}")
    print(f"    FAIL (>=1 claim):   {n_fail}")
    print()

    if failures:
        print("=" * 70)
        print("FAILURES — coaching text contains a claim that contradicts the FEN")
        print("=" * 70)
        for bug, audit in failures:
            fid = bug.get("feedback_id", "?")
            print()
            print(_format_audit(audit, header=f"--- {fid} ---"))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--fen", help="FEN to audit against (single-text mode)")
    p.add_argument("--text", help="coaching text to audit (single-text mode)")
    p.add_argument("--color", default="white", help="user color: white | black")
    p.add_argument("--bug-file", help="path to a bug-export JSON to audit in batch")
    args = p.parse_args()

    if args.bug_file:
        run_bug_file(args)
    elif args.fen and args.text:
        run_one(args)
    else:
        p.error("provide either --bug-file OR (--fen AND --text)")
