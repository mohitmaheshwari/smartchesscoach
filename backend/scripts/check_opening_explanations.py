"""Does every node in every teaching tree actually explain itself?

Counting nodes says nothing about whether a student is told anything when
they reach one. A node earns its place only if it carries the text the
lesson will show: what the opponent just did, a hint before the answer,
the reason the right move is right, and something useful when the student
plays something else.
"""
import io
import json
import sys

PATH = sys.argv[1] if len(sys.argv) > 1 else "backend/data/opening_curriculum.json"
data = json.loads(io.open(PATH, encoding="utf-8").read())

# right_feedback is what _derive_guided_tree_steps shows for the taught move,
# so a node with a `next` and no right_feedback silently shows something else.
NEEDED = ["idea_opponent", "hint", "right_feedback", "wrong_feedback"]


def walk(responses, opening, path, rows, is_root=False, preview=False):
    for san, child in (responses or {}).items():
        if not isinstance(child, dict):
            continue
        here = path + [san]
        missing = [f for f in NEEDED if not str(child.get(f) or "").strip()]
        # In a White opening the root key is our own first move and its `next`
        # is only a preview of the move after the reply, so it is never the
        # move a student is asked for. Nothing there is shown as coaching.
        if is_root:
            missing = [m for m in missing if m != "idea_opponent"]
        if preview:
            missing = [m for m in missing
                       if m not in ("hint", "right_feedback", "wrong_feedback")]
        # a leaf teaches nothing further, so it needs no hint for a next move
        if not child.get("next"):
            missing = [m for m in missing if m not in ("hint", "right_feedback", "wrong_feedback")]
        rows.append({
            "opening": opening, "path": " ".join(here),
            "has_next": bool(child.get("next")), "missing": missing,
            "leaf": not (child.get("responses") or {}),
        })
        walk(child.get("responses"), opening, here, rows)


rows = []
for key, entry in data.items():
    if not isinstance(entry, dict) or not entry.get("tree"):
        continue
    plays_white = str(entry.get("color") or "white").lower() != "black"
    walk(entry["tree"], key, [], rows, is_root=True, preview=plays_white)

total = len(rows)
clean = sum(1 for r in rows if not r["missing"])
print(f"  tree nodes across the curriculum : {total}")
print(f"  fully explained                  : {clean} ({100*clean//max(total,1)}%)")
print(f"  missing something                : {total-clean}")
print()

from collections import Counter
per_field = Counter()
per_opening = Counter()
for r in rows:
    for m in r["missing"]:
        per_field[m] += 1
    if r["missing"]:
        per_opening[r["opening"]] += 1

print("  which field is missing:")
for f, n in per_field.most_common():
    print(f"     {f:18} {n}")
print()
print("  worst openings:")
for o, n in per_opening.most_common(14):
    tot = sum(1 for r in rows if r["opening"] == o)
    print(f"     {o:32} {n:3} of {tot:3} nodes incomplete")

MINE = ["kings_pawn_opening", "scandinavian_defense", "scotch_game", "vienna_game",
        "caro_kann", "ruy_lopez", "french_defense", "philidor_defense", "bishops_opening"]
print()
print("  the nine openings authored in this session:")
for o in MINE:
    sub = [r for r in rows if r["opening"] == o]
    bad = [r for r in sub if r["missing"]]
    print(f"     {o:24} {len(sub)-len(bad):2}/{len(sub):2} complete")
    for r in bad[:4]:
        print(f"        missing {','.join(r['missing']):40} at {r['path'][:46]}")
