"""Strict-gate authoring audit — output the SAFE-TO-APPLY subset.

Mohit 2026-06-03. Built after the loose heuristic in
authoring_audit_pass2.json mis-classified ~20-30% of items. This
stricter version requires ALL of:

  1. Has FEN on the document
  2. Move SAN is present and parseable
  3. Parth's first SAN-shaped token in suggested_caption matches either:
       - the played move (the one being captioned), OR
       - the engine's best_move from diagnostics
     (catches the "F3 vs f5" type wrong-move-referenced errors)
  4. suggested_caption is materially longer than original (≥30% more)
  5. No chess jargon in suggested_caption (full list per memory rule)
  6. No junk formatting (no dot-separators, no underscore-runs, no
     embedded ">>>" markers, no all-caps walls)
  7. If severity is 'blunder' or 'mistake', suggested_caption must
     either name the engine's best_move OR explain the failure mode
     concretely (mentions ≥2 squares or piece names)
  8. suggested_caption is not a hollow validation
     ("you're on track", "good move", etc.)
  9. Not flagged as severity-cp mismatched (e.g. severity=blunder +
     cp_loss<100 = something's off, skip)

Output: writes _snapshots/authoring_safe_subset.json containing a
list of {feedback_id, game_id, move_number, move_san, fen,
caption} entries — ready to be applied as overrides AFTER Mohit
reviews the markdown summary.

Also writes _snapshots/authoring_safe_subset.md with a human-readable
table for review.

This script does NOT apply anything to mongo. The apply step is a
separate command (authoring_apply_safe_subset.py) that writes the
approved overrides + marks the feedback items as acknowledged.
"""
import os
import asyncio
import json
import re
from collections import Counter
from pathlib import Path

import chess
from motor.motor_asyncio import AsyncIOMotorClient


SNAP_DIR = Path("/app/backend/scripts/_snapshots")

SAN_RE = re.compile(
    r"\b([KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?|O-O(?:-O)?)\b"
)

HOLLOW_PATTERNS = [
    r"^you are on track", r"^you'?re winning", r"^\.+\s*$",
    r"^good move\.?$", r"^winning\.?$", r"^this is a winning",
    r"^correct\.?$", r"^well played", r"^excellent",
    r"^the position is",
]

JARGON_WORDS = [
    "fianchetto", "zwischenzug", "zugzwang", "prophylaxis",
    "prophylactic", "luft", "deflection", "outpost",
]
# Note: "tempo" deliberately NOT in jargon list — Parth uses it in
# valid teaching contexts ("comes with tempo, attacking the pawn").
# It's borderline, but excluding it from the gate avoids over-rejecting.

JUNK_PATTERNS = [
    r"\.[a-z]+\.[a-z]+\.",     # dot-separated words like "Look.for.loose.pieces"
    r"_[a-z]+_[a-z]+_",        # underscore-separated like "Both_position_has_same_idea"
    r">>>",                    # arrow-style markers
    r"[A-Z]{8,}",              # all-caps walls (8+ chars)
]


def _safe_san_match(played: str, parths: list, best: str) -> bool:
    """Does Parth's first SAN-shaped token match the played move OR
    the engine's best_move? Lowercase comparison, strips +/#."""
    if not parths:
        # No SAN-shaped token at all in Parth's caption — that's OK if
        # the caption is principle-only (e.g., "Castle early before
        # opening attacks"). We don't require SAN reference. So PASS.
        return True
    first = parths[0].lower().replace("+", "").replace("#", "")
    played_clean = played.lower().replace("+", "").replace("#", "")
    best_clean = (best or "").lower().replace("+", "").replace("#", "")
    return first == played_clean or first == best_clean


def _has_jargon(text: str) -> str:
    t = text.lower()
    for j in JARGON_WORDS:
        if j in t:
            return j
    return ""


def _is_junk_format(text: str) -> bool:
    for p in JUNK_PATTERNS:
        if re.search(p, text):
            return True
    return False


def _is_hollow(text: str) -> bool:
    t = text.lower().strip()
    for p in HOLLOW_PATTERNS:
        if re.match(p, t):
            return True
    return False


def _count_squares_and_pieces(text: str) -> tuple:
    squares = len(re.findall(r"\b[a-h][1-8]\b", text))
    pieces = len(re.findall(
        r"\b(knight|bishop|rook|queen|king|pawn|kings?ide|queens?ide)\b",
        text.lower()
    ))
    return squares, pieces


def _gate_item(fb: dict) -> tuple:
    """Returns (passed: bool, reject_reasons: list)."""
    d = fb.get("diagnostics") or {}
    sg = (fb.get("suggested_caption") or "").strip()
    orig = (fb.get("coaching_text") or "").strip()
    fen = (fb.get("fen") or "").strip()
    san = (fb.get("move_san") or "").strip()
    sev = d.get("severity") or ""
    cp = d.get("cp_loss") or 0
    best = d.get("best_move")

    reasons = []

    if not fen:
        reasons.append("no_fen")
    if not san:
        reasons.append("no_move_san")
    if fen and san:
        try:
            board = chess.Board(fen)
            board.parse_san(san)
        except Exception as e:
            reasons.append(f"fen_san_unparseable:{type(e).__name__}")

    if not sg:
        reasons.append("empty_suggestion")
        return False, reasons
    if sg == orig:
        reasons.append("identical_to_original")

    parth_sans = SAN_RE.findall(sg)
    if not _safe_san_match(san, parth_sans, best):
        reasons.append(
            f"wrong_move_referenced (parth='{parth_sans[0]}', "
            f"played='{san}', best='{best}')"
        )

    if len(sg) < len(orig) * 1.3:
        reasons.append(f"not_materially_longer ({len(sg)} vs {len(orig)})")

    j = _has_jargon(sg)
    if j:
        reasons.append(f"jargon:{j}")

    if _is_junk_format(sg):
        reasons.append("junk_format")

    if _is_hollow(sg):
        reasons.append("hollow")

    # For severe positions, require concrete content
    if sev in ("blunder", "mistake", "opp_blunder", "opp_mistake"):
        squares, pieces = _count_squares_and_pieces(sg)
        mentions_best = bool(best) and best.lower() in sg.lower()
        if not mentions_best and (squares + pieces) < 2:
            reasons.append(
                f"severe_but_vague (squares={squares}, pieces={pieces}, "
                f"mentions_best={mentions_best})"
            )

    # Severity-cp sanity
    if sev == "blunder" and isinstance(cp, (int, float)) and cp < 100:
        reasons.append(f"severity_cp_mismatch (sev=blunder, cp={cp})")

    return len(reasons) == 0, reasons


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[
        os.environ.get("DB_NAME", "chess_coach")
    ]
    SNAP_DIR.mkdir(parents=True, exist_ok=True)

    safe = []
    rejected = []
    async for fb in db.move_feedback.find(
        {"is_authoring_submission": True}, {"_id": 0}
    ):
        passed, reasons = _gate_item(fb)
        d = fb.get("diagnostics") or {}
        entry = {
            "feedback_id": fb.get("feedback_id"),
            "game_id": fb.get("game_id"),
            "move_number": fb.get("move_number"),
            "move_san": fb.get("move_san"),
            "fen": fb.get("fen"),
            "severity": d.get("severity"),
            "cp_loss": d.get("cp_loss"),
            "best_move": d.get("best_move"),
            "original_caption": (fb.get("coaching_text") or "").strip(),
            "suggested_caption": (fb.get("suggested_caption") or "").strip(),
            "user_name": fb.get("user_name"),
            "passed": passed,
            "reject_reasons": reasons,
        }
        if passed:
            safe.append(entry)
        else:
            rejected.append(entry)

    print(f"TOTAL: {len(safe) + len(rejected)}")
    print(f"  passed strict gate: {len(safe)}")
    print(f"  rejected:           {len(rejected)}")
    print(f"  pass rate:          {100*len(safe)/(len(safe)+len(rejected)):.1f}%")
    print()
    rej_reason_counts = Counter()
    for r in rejected:
        for reason in r["reject_reasons"]:
            # Strip parenthetical details for aggregation
            base = reason.split(" (")[0].split(":")[0]
            rej_reason_counts[base] += 1
    print("Top reject reasons (count):")
    for r, n in rej_reason_counts.most_common(15):
        print(f"  {r:<30}: {n}")

    # Write outputs
    safe_path = SNAP_DIR / "authoring_safe_subset.json"
    rej_path = SNAP_DIR / "authoring_rejected.json"
    safe_path.write_text(json.dumps(safe, indent=2, default=str))
    rej_path.write_text(json.dumps(rejected, indent=2, default=str))
    print(f"\nwrote {safe_path}")
    print(f"wrote {rej_path}")


if __name__ == "__main__":
    asyncio.run(main())
