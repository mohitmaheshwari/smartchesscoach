import pymongo, os, json
from collections import Counter
db = pymongo.MongoClient(os.environ['MONGO_URL'])[os.environ['DB_NAME']]

FAMILIES = [
    ("Ruy Lopez (Spanish)", ["Ruy Lopez","Spanish Game","Spanish Opening"]),
    ("Italian Game", ["Italian Game","Giuoco Piano","Two Knights"]),
    ("Scotch Game", ["Scotch"]),
    ("Petrov / Russian", ["Petrov","Petroff","Russian Game"]),
    ("Philidor Defense", ["Philidor"]),
    ("Vienna Game", ["Vienna"]),
    ("Bishop's Opening", ["Bishops Opening","Bishop's Opening"]),
    ("Ponziani", ["Ponziani"]),
    ("Four Knights", ["Four Knights"]),
    ("Three Knights", ["Three Knights"]),
    ("King's Gambit", ["Kings Gambit","King's Gambit"]),
    ("Sicilian Defense", ["Sicilian"]),
    ("Caro-Kann Defense", ["Caro Kann","Caro-Kann"]),
    ("French Defense", ["French"]),
    ("Scandinavian Defense", ["Scandinavian","Center Counter"]),
    ("Pirc Defense", ["Pirc"]),
    ("Modern Defense", ["Modern Defense"]),
    ("Alekhine Defense", ["Alekhine"]),
    ("Nimzowitsch Defense", ["Nimzowitsch Defense"]),
    ("Slav Defense", ["Slav"]),
    ("Queen's Gambit Declined", ["Queens Gambit Declined","Queen's Gambit Declined"]),
    ("Queen's Gambit Accepted", ["Queens Gambit Accepted","Queen's Gambit Accepted"]),
    ("Queen's Gambit", ["Queens Gambit","Queen's Gambit"]),
    ("King's Indian Defense", ["Kings Indian","King's Indian"]),
    ("Nimzo-Indian Defense", ["Nimzo Indian","Nimzo-Indian"]),
    ("Queen's Indian Defense", ["Queens Indian","Queen's Indian"]),
    ("Grunfeld Defense", ["Grunfeld","Gruenfeld"]),
    ("Catalan Opening", ["Catalan"]),
    ("Benoni / Benko", ["Benoni","Benko"]),
    ("Dutch Defense", ["Dutch"]),
    ("London System", ["London"]),
    ("Trompowsky", ["Trompowsky"]),
    ("Englund Gambit", ["Englund"]),
    ("English Opening", ["English"]),
    ("Reti Opening", ["Reti"]),
    ("Bird's Opening", ["Bird"]),
    ("Nimzo-Larsen Attack", ["Nimzowitsch Larsen","Nimzo Larsen","Larsen"]),
    ("Owen's Defense", ["Owens Defense","Owen's Defense"]),
    ("Van't Kruijs", ["Van t Kruijs","Vant Kruijs","Van't Kruijs"]),
    ("Queen's Pawn Game", ["Queens Pawn","Queen's Pawn","Chigorin","Colle"]),
    ("King's Pawn / Open Game", ["Kings Pawn","King's Pawn","Kings Knight","Center Game","Danish"]),
]
def family(s):
    if not s: return None
    for fam,keys in FAMILIES:
        for k in keys:
            if k.lower() in s.lower(): return fam
    return None

# What the curriculum covers, mapped to family labels:
COVERED = {
 "London System","Italian Game","Sicilian Defense","Caro-Kann Defense","French Defense",
 "Queen's Gambit","Queen's Gambit Declined","Queen's Gambit Accepted","Slav Defense",
 "Scandinavian Defense","Ruy Lopez (Spanish)","Scotch Game","Petrov / Russian",
 "King's Indian Defense","Nimzo-Indian Defense","English Opening","Modern Defense",
 "Philidor Defense","Bishop's Opening","Vienna Game","Englund Gambit",
}
GENERIC = {"King's Pawn / Open Game","Queen's Pawn Game"}

w=Counter(); b=Counter()
for x in db.games.find({"is_analyzed":True},{"opening":1,"user_color":1}):
    fam=family(x.get("opening"))
    if not fam: continue
    (w if (x.get("user_color") or "").lower()=="white" else b)[fam]+=1
allf=Counter(); allf.update(w); allf.update(b)

print("=== OPENING FAMILIES IN GAMES NOT COVERED BY CURRICULUM ===")
print("(total games | white | black)\n")
gaps=[(allf[f],w[f],b[f],f) for f in allf if f not in COVERED and f not in GENERIC]
for tot,wn,bn,f in sorted(gaps,reverse=True):
    print("  %4d  (W %3d / B %3d)  %s" % (tot,wn,bn,f))
print()
print("--- generic roots (not discrete teachable openings) ---")
for f in GENERIC:
    if f in allf: print("  %4d  %s" % (allf[f],f))
print()
covered_seen=[f for f in allf if f in COVERED]
print("Covered families that appear in games: %d / 21 curriculum entries" % len(covered_seen))
notseen=[c for c in COVERED if c not in allf and c not in ("Queen's Gambit Declined","Queen's Gambit Accepted","Slav Defense")]
print("Curriculum openings with ~no game volume:", notseen or "(none)")
