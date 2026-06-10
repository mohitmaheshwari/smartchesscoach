import json
d = json.load(open("/app/backend/data/opening_curriculum.json"))
KEYS = {"caro_kann":"Caro-Kann","sicilian_defense":"Sicilian","italian_game":"Italian",
        "scandinavian_defense":"Scandinavian","french_defense":"French","scotch_game":"Scotch"}

def walk(node, moves, out):
    nm = node.get("name")
    if nm: out.append((nm, " ".join(moves)))
    nxt = node.get("next")
    for opp, child in (node.get("responses") or {}).items():
        walk(child, moves + ([nxt] if nxt else []) + [opp], out)

for k, fam in KEYS.items():
    e = d.get(k)
    if not e: print(f"[{fam}] MISSING"); continue
    out = []
    for root_san, root in e["tree"].items():
        walk(root, [root_san], out)
    print(f"=== {fam} ({k}) — branches the tree teaches ===")
    for nm, path in out:
        print(f"  • {nm:42s} {path}")
    print()
