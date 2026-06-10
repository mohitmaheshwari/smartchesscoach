import pymongo, os, re
from collections import Counter, defaultdict
db = pymongo.MongoClient(os.environ['MONGO_URL'])[os.environ['DB_NAME']]

# Families we cover, with the keyword that identifies them in chess.com strings.
COVERED = {
    "Caro-Kann": ["Caro Kann","Caro-Kann"],
    "Sicilian": ["Sicilian"],
    "Italian": ["Italian Game","Giuoco","Two Knights"],
    "Scandinavian": ["Scandinavian","Center Counter"],
    "French": ["French"],
    "Scotch": ["Scotch"],
    "Ruy Lopez": ["Ruy Lopez"],
    "Queen's Gambit": ["Queens Gambit","Queen's Gambit"],
    "Vienna": ["Vienna"],
    "Philidor": ["Philidor"],
}
def fam(s):
    for f,keys in COVERED.items():
        for k in keys:
            if k.lower() in s.lower(): return f
    return None

buckets = defaultdict(Counter)
for x in db.games.find({"is_analyzed":True},{"opening":1}):
    o = x.get("opening")
    if not o: continue
    f = fam(o)
    if not f: continue
    # strip the family prefix to reveal the variation tail
    tail = o
    buckets[f][o.strip()] += 1

for f in ["Caro-Kann","Sicilian","Italian","Scandinavian","French","Scotch"]:
    c = buckets[f]
    print(f"=== {f}  (total {sum(c.values())} games, {len(c)} distinct labels) ===")
    for label, n in c.most_common(10):
        print("  %4d  %s" % (n, label[:70]))
    print()
