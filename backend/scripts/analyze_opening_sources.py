"""Phase 1 analysis for opening source consolidation (docs/opening_source_consolidation_scope.md).
Reads the 3 opening sources, normalizes each entry to a canonical family name, and reports
the union + per-source coverage + name conflicts + caption coverage. NON-DESTRUCTIVE — read only.

Run: docker exec chess-coach-backend python /app/backend/scripts/analyze_opening_sources.py
"""
import json, os, sys
sys.path.insert(0, "/app/backend")
from services.opening_normalizer import normalize_opening

D = "/app/backend/data"

def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)

curr = load(f"{D}/opening_curriculum.json")
tree = load(f"{D}/coaching/opening_theory_tree.json")
import re
ob_raw = open("/app/backend/services/decryption_voice/opening_book.py", encoding="utf-8").read()

# opening_book entries: name + whether it has a caption
import ast
m = re.search(r"_OPENINGS\s*=\s*(\[.*?\n\])", ob_raw, re.S)
ob = ast.literal_eval(m.group(1)) if m else []

def norm(n):
    try:
        return normalize_opening(n) or n
    except Exception:
        return n

# Collect: family -> which sources have it
fam = {}
def add(family, src, extra=""):
    fam.setdefault(family, {"curriculum": False, "tree": False, "book": 0, "book_caption": 0})
    if src == "book":
        fam[family]["book"] += 1
        if extra:
            fam[family]["book_caption"] += 1
    else:
        fam[family][src] = True

for k, v in curr.items():
    if isinstance(v, dict) and v.get("name"):
        add(norm(v["name"]), "curriculum")
for k, v in tree.items():
    if isinstance(v, dict) and not k.startswith("_") and v.get("name"):
        add(norm(v["name"]), "tree")
for e in ob:
    nm = e.get("name", "")
    add(norm(nm), "book", e.get("caption", ""))

print(f"opening_book raw entries: {len(ob)} | curriculum: {len([1 for v in curr.values() if isinstance(v,dict) and v.get('name')])} | tree: {len([1 for k,v in tree.items() if isinstance(v,dict) and not k.startswith('_')])}")
print(f"distinct families (normalized): {len(fam)}")
in_all3 = [f for f, s in fam.items() if s["curriculum"] and s["tree"] and s["book"]]
in_1 = [f for f, s in fam.items() if (s["curriculum"] + s["tree"] + (1 if s["book"] else 0)) == 1]
print(f"in all 3 sources: {len(in_all3)} | in exactly 1 source: {len(in_1)}")
print()
print(f"{'family':32} curr tree book(cap)")
for f in sorted(fam):
    s = fam[f]
    print(f"  {f[:30]:32} {'Y' if s['curriculum'] else '.':>4} {'Y' if s['tree'] else '.':>4} {s['book']:>3}({s['book_caption']})")
