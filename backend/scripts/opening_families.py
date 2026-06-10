import pymongo, os
from collections import Counter, defaultdict
db = pymongo.MongoClient(os.environ['MONGO_URL'])[os.environ['DB_NAME']]

# Ordered most-specific -> general. First match wins. Names normalized for the
# chess.com strings which drop apostrophes (Kings, Queens, Caro Kann).
FAMILIES = [
    ("Ruy Lopez (Spanish)", ["Ruy Lopez", "Spanish Game", "Spanish Opening"]),
    ("Italian Game",        ["Italian Game", "Giuoco Piano", "Two Knights"]),
    ("Scotch Game",         ["Scotch"]),
    ("Petrov / Russian",    ["Petrov", "Petroff", "Russian Game"]),
    ("Philidor Defense",    ["Philidor"]),
    ("Vienna Game",         ["Vienna"]),
    ("Bishop's Opening",    ["Bishops Opening", "Bishop's Opening"]),
    ("Ponziani",            ["Ponziani"]),
    ("Four Knights",        ["Four Knights"]),
    ("Three Knights",       ["Three Knights"]),
    ("King's Gambit",       ["Kings Gambit", "King's Gambit"]),
    ("Sicilian Defense",    ["Sicilian"]),
    ("Caro-Kann Defense",   ["Caro Kann", "Caro-Kann"]),
    ("French Defense",      ["French"]),
    ("Scandinavian Defense",["Scandinavian", "Center Counter"]),
    ("Pirc Defense",        ["Pirc"]),
    ("Modern Defense",      ["Modern Defense"]),
    ("Alekhine Defense",    ["Alekhine"]),
    ("Nimzowitsch Defense", ["Nimzowitsch Defense"]),
    ("Queen's Gambit Declined", ["Queens Gambit Declined", "Queen's Gambit Declined"]),
    ("Queen's Gambit Accepted", ["Queens Gambit Accepted", "Queen's Gambit Accepted"]),
    ("Queen's Gambit",      ["Queens Gambit", "Queen's Gambit", "Slav"]),
    ("King's Indian Defense", ["Kings Indian", "King's Indian"]),
    ("Nimzo-Indian Defense",["Nimzo Indian", "Nimzo-Indian"]),
    ("Queen's Indian Defense",["Queens Indian", "Queen's Indian"]),
    ("Grunfeld Defense",    ["Grunfeld", "Gruenfeld"]),
    ("Catalan Opening",     ["Catalan"]),
    ("Benoni / Benko",      ["Benoni", "Benko"]),
    ("Dutch Defense",       ["Dutch"]),
    ("London System",       ["London"]),
    ("Trompowsky",          ["Trompowsky"]),
    ("Englund Gambit",      ["Englund"]),
    ("English Opening",     ["English"]),
    ("Reti Opening",        ["Reti", "Reti Opening"]),
    ("Bird's Opening",      ["Bird"]),
    ("Queen's Pawn Game",   ["Queens Pawn", "Queen's Pawn", "Chigorin", "Colle"]),
    ("King's Pawn / Open Game", ["Kings Pawn", "King's Pawn", "Kings Knight", "Center Game", "Danish"]),
]

def family(s):
    if not s: return None
    for fam, keys in FAMILIES:
        for k in keys:
            if k.lower() in s.lower():
                return fam
    return None  # unrecognized

by_color = {"white": Counter(), "black": Counter()}
unrec = Counter()
total = unrec_n = 0
for x in db.games.find({"is_analyzed": True}, {"opening":1,"user_color":1}):
    o = x.get("opening")
    if not o: continue
    total += 1
    col = (x.get("user_color") or "").lower()
    fam = family(o)
    if fam is None:
        unrec_n += 1; unrec[o[:40]] += 1; continue
    if col in by_color: by_color[col][fam] += 1

allfam = Counter()
for c in by_color.values(): allfam.update(c)

print("Analysed games with an opening:", total)
print("Mapped to a known popular family:", total - unrec_n,
      "(%.0f%%)" % (100*(total-unrec_n)/total))
print("Unrecognized (rarer/messy strings):", unrec_n)
print("DISTINCT known popular families seen:", len(allfam))
print()
print("=== TOP FAMILIES — when USER played WHITE ===")
for fam, n in by_color["white"].most_common(18):
    print("  %4d  %s" % (n, fam))
print()
print("=== TOP FAMILIES — when USER played BLACK ===")
for fam, n in by_color["black"].most_common(18):
    print("  %4d  %s" % (n, fam))
print()
print("=== top unrecognized strings (candidates to add) ===")
for v, n in unrec.most_common(10):
    print("  %4d  %s" % (n, v))
