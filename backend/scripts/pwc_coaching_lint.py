"""
pwc_coaching_lint.py — ABSOLUTE mechanical linter for PWC coaching text.

Catches the class of basic defects that must never reach the user and that
Mohit has been catching by hand: empty captions, snake_case key leaks
(piece_activity), grammar ("1 mistakes", "3th time"), banned jargon, a pawn
described as a "piece", and identical repetition.

Design: the coaching text is TEMPLATE-DRIVEN, so we lint the templates + the
selection logic directly — NO slow per-user DB rendering (that timed out over the
tunnel). This is ABSOLUTE (flags defects on their own terms, not drift vs a
baseline) and MECHANICAL only (not "is it insightful" — that needs judgment).
Fast (~seconds, no Mongo). Run after ANY change to the coaching surfaces.

Passes:
  1. Session-goal templates  — every LEAK/PHASE/BAND goal string + leak x phase blends
  2. Coach-move templates     — every R17 variant's 4 narrative fields (static)
  3. Coach-move SELECTION     — R17 populate_coach_extras over an opening+quiet corpus
                                (catches the e5 'pawn called a piece' mis-selection)

Usage:  docker exec -i chess-coach-backend python -m scripts.pwc_coaching_lint
Exit 0 = clean, 1 = defects.
"""
import re
import sys

sys.path.insert(0, "/app/backend")

BANNED = [
    "zwischenzug", "prophylaxis", "zugzwang", "luft", "outpost",
    "minority attack", "centipawn", "cp loss", "stockfish", "en prise",
    "fianchetto",
]
_SNAKE = re.compile(r"\b[a-z]{3,}_[a-z]{3,}\b")


def lint_text(text, *, expect_text=False, is_pawn=False):
    if text is None or not str(text).strip():
        return [("EMPTY", "")] if expect_text else []
    t = str(text); lo = t.lower(); out = []
    # Strip {placeholder} tokens before the snake_case check — they are
    # intentional template slots (filled at render time), not leaked keys.
    # A real leak (e.g. a bare "piece_activity") survives the strip.
    bare = re.sub(r"\{[^}]*\}", "", t)
    m = _SNAKE.search(bare)
    if m:
        out.append(("SNAKE_CASE_LEAK", m.group()))
    if re.search(r"\b1 mistakes\b", lo):
        out.append(("GRAMMAR_PLURAL", "'1 mistakes'"))
    mo = re.search(r"\b(1th|2th|3th|0th)\b", lo)
    if mo:
        out.append(("GRAMMAR_ORDINAL", mo.group()))
    if "  " in t:
        out.append(("DOUBLE_SPACE", repr(t[:50])))
    for term in BANNED:
        if term in lo:
            out.append(("JARGON", term))
    if is_pawn and ("piece's position" in lo or "improving the piece" in lo
                    or re.search(r"\bthe piece\b", lo)):
        out.append(("PAWN_CALLED_PIECE", t[:70]))
    return out


def run():
    flags = []

    def add(typ, where, detail, text):
        flags.append({"type": typ, "where": where, "detail": detail, "text": str(text)})

    def lint(where, text, **kw):
        for typ, detail in lint_text(text, **kw):
            add(typ, where, detail, text)

    # ── Pass 1: session-goal templates + blends ─────────────────────────
    print("=== Pass 1: session-goal templates ===")
    from services import session_goal_service as G
    n = 0
    for k, v in G._LEAK_GOALS.items():
        lint(f"goal/leak/{k}", v, expect_text=True); n += 1
        for pk, tail in G._PHASE_TAIL.items():
            lint(f"goal/blend/{k}+{pk}", f"{v} {tail}", expect_text=True); n += 1
    for k, v in G._PHASE_GOALS.items():
        lint(f"goal/phase/{k}", v, expect_text=True); n += 1
    for k, v in G._BAND_GOALS.items():
        lint(f"goal/band/{k}", v, expect_text=True); n += 1
    lint("goal/band/fallback", G._BAND_GOAL_FALLBACK, expect_text=True); n += 1
    print(f"  linted {n} goal strings (incl. leak x phase blends)")

    # ── Pass 2: coach-move R17 template strings (static) ────────────────
    print("\n=== Pass 2: coach-move R17 templates ===")
    import json, os
    r17_path = os.path.join("/app/backend", "data", "captions", "R17_coach_move.json")
    cfg = json.load(open(r17_path, encoding="utf-8"))
    n = 0
    for vname, body in (cfg.get("variants") or {}).items():
        if not isinstance(body, dict):
            continue
        # A pawn-specific variant must not call the pawn "the piece".
        is_pawn = "central_pawn" in vname
        for fld in ("explanation", "plan", "teaching_point", "hint_for_user"):
            lint(f"r17/{vname}/{fld}", body.get(fld), is_pawn=is_pawn); n += 1
    print(f"  linted {n} R17 template fields")

    # ── Pass 3: coach-move SELECTION (synthetic render) ─────────────────
    print("\n=== Pass 3: coach-move selection (R17 render corpus) ===")
    from services.caption_pipeline import populate_coach_extras
    corpus = [
        ("e5", "pawn", "e5", "opening"), ("e4", "pawn", "e4", "opening"),
        ("d4", "pawn", "d4", "opening"), ("d5", "pawn", "d5", "opening"),
        ("c5", "pawn", "c5", "opening"), ("Nf6", "knight", "f6", "opening"),
        ("Nf3", "knight", "f3", "opening"), ("Bc4", "bishop", "c4", "opening"),
        ("Bb5", "bishop", "b5", "opening"), ("Qe2", "queen", "e2", "middlegame"),
        ("Rd1", "rook", "d1", "middlegame"), ("Kg2", "king", "g2", "endgame"),
        ("a4", "pawn", "a4", "middlegame"), ("Nd2", "knight", "d2", "middlegame"),
    ]
    n = 0
    for san, pt, sq, phase in corpus:
        facts = {"coach_move_is_active": True, "played_san": san,
                 "moving_piece_type": pt, "target_square": sq, "phase": phase}
        ce = populate_coach_extras(facts)
        is_pawn = pt == "pawn"
        for fld in ("explanation", "plan", "teaching_point", "hint_for_user"):
            lint(f"sel/{san}/{fld}", getattr(ce, fld, None), is_pawn=is_pawn); n += 1
    print(f"  rendered+linted {len(corpus)} coach moves x4 fields")

    # ── Report ──────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    if not flags:
        print("RESULT: CLEAN — no mechanical defects")
        return 0
    from collections import Counter
    by_type = Counter(f["type"] for f in flags)
    print(f"RESULT: {len(flags)} DEFECTS across {len(by_type)} types")
    for typ, c in by_type.most_common():
        print(f"  {typ}: {c}")
    print("  --- details ---")
    for f in flags:
        print(f"  [{f['type']}] {f['where']}: {f['detail']}  ::  {f['text'][:80]!r}")
    return 1


if __name__ == "__main__":
    sys.exit(run())
