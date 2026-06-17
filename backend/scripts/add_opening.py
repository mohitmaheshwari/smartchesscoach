"""add_opening — scaffold a new opening across every source in ONE command.

The opening sources are purpose-built (recognition+caption / theory / repertoire /
traps), so adding an opening legitimately needs entries in several files. This
removes the "hunt-the-files" pain: one command stubs schema-correct entries in all
of them with the SAME identity (kills name-drift), leaving TODO placeholders for the
human to fill the actual teaching content. See docs/opening_source_consolidation_scope.md
(FINAL VERDICT: no merge; scaffold instead).

Files touched:
  data/coaching/opening_theory_tree.json   key=<slug_us>   (PWC theory)
  data/opening_curriculum.json             key=<slug_us>   (repertoire/tracking)
  data/traps.json                          key=<slug-dash> (canonical traps home, stub [])
  services/decryption_voice/opening_book.py  _OPENINGS      (review-caption recognizer)

Usage (dry-run by default; --apply to write):
  python scripts/add_opening.py --name "Vienna Game" --color white \
      --moves "e4 e5 Nc3" --eco C25 --caption "Vienna Game. ..." [--apply]
"""
import argparse, json, os, re, sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
TREE = os.path.join(ROOT, "data", "coaching", "opening_theory_tree.json")
CURR = os.path.join(ROOT, "data", "opening_curriculum.json")
TRAPS = os.path.join(ROOT, "data", "traps.json")
BOOK = os.path.join(ROOT, "services", "decryption_voice", "opening_book.py")


def _load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _save(p, d):
    with open(p, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True, help='Display name, e.g. "Vienna Game"')
    ap.add_argument("--moves", required=True, help='Defining SAN line, space-separated, e.g. "e4 e5 Nc3"')
    ap.add_argument("--color", default="white", choices=["white", "black"], help="Repertoire side (default white)")
    ap.add_argument("--eco", default="", help="ECO code(s), comma-separated, e.g. C25")
    ap.add_argument("--caption", default="", help="Review caption (1-2 sentences naming the opening + key idea)")
    ap.add_argument("--apply", action="store_true", help="Write changes (default: dry-run)")
    a = ap.parse_args()

    moves = a.moves.split()
    slug_us = re.sub(r"[^a-z0-9]+", "_", a.name.lower()).strip("_")
    slug_dash = slug_us.replace("_", "-")
    eco = [e.strip().upper() for e in a.eco.split(",") if e.strip()]
    caption = a.caption or f"TODO: 1-2 sentence caption naming the {a.name} + its key idea (square/threat)."

    tree, curr, traps = _load(TREE), _load(CURR), _load(TRAPS)
    book_src = open(BOOK, encoding="utf-8").read()

    # ── existence check (single identity guard) ─────────────────────────
    exists = []
    if slug_us in tree: exists.append("theory_tree")
    if slug_us in curr: exists.append("curriculum")
    if slug_dash in traps: exists.append("traps.json")
    if re.search(rf'"name":\s*"{re.escape(slug_us)}"', book_src): exists.append("opening_book")
    if exists:
        print(f"!! '{a.name}' (slug {slug_us}) already present in: {', '.join(exists)}. Aborting to avoid a duplicate identity.")
        sys.exit(1)

    # ── stubs (schema-correct; TODO placeholders for content) ───────────
    tree_stub = {
        "name": a.name, "eco_prefix": eco, "main_line": moves,
        "white_plan": "TODO: white's plan in one line",
        "black_plan": "TODO: black's plan in one line",
        "critical_positions": {}, "variations": {}, "common_learnings": [], "move_ideas": {},
    }
    curr_stub = {
        "name": a.name, "color": a.color,
        "summary": "TODO: one-line beginner summary of the idea",
        "difficulty": "beginner", "setup_order": moves,
        "golden_rules": ["TODO: golden rule 1"],
        "traps": [],  # traps live in traps.json (canonical) — see traps key below
        "tree": {}, "middlegame_plans": [], "endgame_tips": [],
    }
    book_entry = f'    {{"moves": {json.dumps(moves)}, "name": "{slug_us}", "caption": {json.dumps(caption)}}},\n'

    print(f"== add-opening: {a.name}  (slug_us={slug_us}, slug-dash={slug_dash}, color={a.color}, eco={eco or '(none)'}) ==")
    print(f"  theory_tree.json   + key '{slug_us}'  (white_plan/black_plan = TODO)")
    print(f"  curriculum.json    + key '{slug_us}'  (summary/golden_rules = TODO)")
    print(f"  traps.json         + key '{slug_dash}' = []  (canonical home; add this opening's traps here)")
    print(f"  opening_book.py    + _OPENINGS entry  (caption {'given' if a.caption else '= TODO'})")
    if not a.apply:
        print("\n(dry-run - re-run with --apply to write)")
        return

    tree[slug_us] = tree_stub
    curr[slug_us] = curr_stub
    traps[slug_dash] = []
    _save(TREE, tree); _save(CURR, curr); _save(TRAPS, traps)
    # insert the recognizer entry right after `_OPENINGS = [`
    new_src, n = re.subn(r"(_OPENINGS\s*=\s*\[\n)", r"\1" + book_entry, book_src, count=1)
    if n != 1:
        print("!! could not locate `_OPENINGS = [` in opening_book.py — JSONs written, add the recognizer entry by hand:")
        print(book_entry.strip())
    else:
        with open(BOOK, "w", encoding="utf-8") as f:
            f.write(new_src)
    print(f"\nOK - wrote stubs. Now fill the TODOs, then a new game playing {a.name} is named + taught everywhere.")


if __name__ == "__main__":
    main()
