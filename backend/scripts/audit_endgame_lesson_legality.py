#!/usr/bin/env python3
"""Read-only: is every move an endgame lesson names actually legal?

A lesson that tells a player to play an illegal move is worse than a lesson
with no advice, because they try it and the board refuses. Found exactly that
in rook_endgames/lucena[0], whose on_correct reads "Rh4 prepares the bridge.
Next: Kc7" -- and Kc7 is illegal, since Black's king stands on d7, adjacent
to c7.

Two kinds of check, with different confidence:

  STRUCTURAL (definitive) -- fen parses, correct_move_san and
  wrong_example_san are legal in it. All 60 positions pass today.

  PROSE (heuristic, needs a human) -- SAN named in advice text that is legal
  neither in the position nor after the correct move. Most hits are NOT bugs:
  "the King marches (Ke4, Kd3, Kc2)" is a route several moves long, and
  "...Nxb6" is conditional on White pushing b6 first. Read each one; do not
  mass-fix from this list.

Usage:  python -m scripts.audit_endgame_lesson_legality
"""
import json, re, chess
SAN = re.compile(r'\b([KQRBN][a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?)\+?#?\b')
PROSE = ("idea", "on_correct", "on_wrong", "rule_reminder", "prompt")
d = json.load(open('backend/data/coaching/endgame_theory_tree.json', encoding='utf-8'))
flags = []
total = 0
for cat in [k for k in d if not k.startswith('_')]:
    for lkey, lesson in (d[cat].get('lessons') or {}).items():
        for i, p in enumerate(lesson.get('positions') or []):
            total += 1
            where = f"{cat}/{lkey}[{i}]"
            board = chess.Board(p['fen'])
            after = board.copy()
            try:
                after.push(board.parse_san(p['correct_move_san']))
            except Exception:
                after = None
            for field in PROSE:
                for tok in dict.fromkeys(SAN.findall(p.get(field) or "")):
                    ok = False
                    for probe in [x for x in (board, after) if x is not None]:
                        try:
                            probe.parse_san(tok); ok = True; break
                        except Exception:
                            pass
                    if not ok:
                        flags.append((where, field, tok, p['fen']))
print(f"positions scanned: {total}")
print(f"prose moves illegal both now and after the correct move: {len(flags)}\n")
for w, f, t, fen in flags:
    print(f"  {w:<32} {f:<14} {t:<6} {fen}")
