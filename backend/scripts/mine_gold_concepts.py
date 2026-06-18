"""Mine the easy-English gold corpus for recurring COACHING CONCEPTS, ranked by
frequency + flagged board-verifiable. Data-first input to the Why-Now Coach Layer
build order (docs/why_now_coach_layer_scope.md). Two views:
  (1) deterministic phrase-frequency (free, reproducible)
  (2) one Opus extraction pass over a diverse sample (clean concept names + verifiability)
Env: LLM_EXPOSER_URL, LLM_EXPOSER_KEY. Usage: python scripts/mine_gold_concepts.py
"""
import os, sys, json, re, time, urllib.request

CORPUS = "/app/backend/scripts/_gold_corpus.json"

# concept -> (regex, board-verifiable?)
CONCEPTS = [
    ("development",        r"\b(develop|bring[s]?\s+\w+\s+out|brought\s+\w+\s+out|comes? out|out into the game|out toward)\b", "yes"),
    ("attack/pressure",    r"\b(attack|hits?|pressure|press|eyes?|aim(s|ing)?|target)\b", "yes"),
    ("castle/king-safety", r"\b(castl|king[\s\w]{0,12}(safe|air|corner)|safe spot[\s\w]{0,8}king)\b", "yes"),
    ("center",             r"\b(center|centre|middle of the board|the middle|grab the middle)\b", "yes"),
    ("space",              r"\bspace\b", "partial"),
    ("open-file",          r"\bopen (file|line|column)\b", "yes"),
    ("hanging/free",       r"\b(hang|undefended|unguarded|for free|free (piece|pawn|knight|bishop|rook|queen))\b", "yes"),
    ("trade/recapture",    r"\b(trade|take[s]? back|recaptur|keep[s]? .*even|material even)\b", "yes"),
    ("safe/retreat",       r"\b(safe spot|out of danger|back to safety|keep[s]? it safe)\b", "yes"),
    ("pin",                r"\bpin(s|ned|ning)?\b", "yes"),
    ("fork",               r"\bfork(s|ed|ing)?\b", "yes"),
    ("check",              r"\bcheck\b", "yes"),
    ("passed-pawn",        r"\bpassed pawn\b", "yes"),
    ("tempo/queen-chase",  r"\b(tempo|chase|too early|gain[s]?\s+time|kick)\b", "yes"),
    ("moved-twice",        r"\b(twice|same piece)\b", "yes"),
    ("pawn-break",         r"\b(break|push[\s\w]{0,12}open|open[\s\w]{0,8}up)\b", "partial"),
    ("mate",               r"\bmate\b", "yes"),
    ("weak-square/pawn",   r"\b(weak|weakness|hole)\b", "partial"),
    ("active-piece",       r"\b(active|busy line|more active|good spot)\b", "partial"),
    ("defend/guard",       r"\b(defend|guard|protect|cover)\b", "yes"),
]


def main():
    corpus = json.load(open(CORPUS, encoding="utf-8"))
    caps = [c for lst in corpus.values() for c in lst]
    print(f"corpus: {len(caps)} captions across {len(corpus)} types\n")
    print("=== deterministic concept frequency (share of captions containing the concept) ===")
    rows = []
    for name, rx, verif in CONCEPTS:
        n = sum(1 for c in caps if re.search(rx, c, re.I))
        rows.append((name, n, verif))
    for name, n, verif in sorted(rows, key=lambda x: -x[1]):
        bar = "#" * int(40 * n / max(1, len(caps)))
        print(f"  {name:20} {n:4} ({100*n/len(caps):4.1f}%) [{verif:7}] {bar}")

    # one Opus extraction pass on a diverse sample
    url = os.environ.get("LLM_EXPOSER_URL", "").rstrip("/"); key = os.environ.get("LLM_EXPOSER_KEY", "")
    if not url:
        print("\n(no exposer env — skipping Opus extraction)"); return
    sample = []
    per = max(1, 150 // max(1, len(corpus)))
    for lst in corpus.values():
        sample.extend(lst[:per])
    q = ("Here are easy-English chess coaching captions. List the recurring COACHING CONCEPTS they teach "
         "(e.g. 'develop a piece', 'attack a square', 'king safety/castle', 'hanging piece', 'recapture/trade', "
         "'control the center', 'gain space', 'open file', 'tempo/queen chased'). For each: a short name, rough "
         "frequency (high/med/low), and whether it is BOARD-VERIFIABLE from the position+engine line (yes/partial/no). "
         "Return ONLY JSON: {\"concepts\":[{\"name\":..,\"freq\":..,\"verifiable\":..}]}.\n\nCAPTIONS:\n"
         + "\n".join(f"- {c}" for c in sample[:150]))
    h = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    try:
        d = json.dumps({"provider": "claude", "question": q, "timeout_seconds": 150}).encode()
        r = urllib.request.Request(url + "/ask", data=d, headers=h, method="POST")
        tid = json.loads(urllib.request.urlopen(r, timeout=40).read().decode()).get("task_id")
        ans = ""
        for _ in range(50):
            time.sleep(4)
            try:
                rec = json.loads(urllib.request.urlopen(urllib.request.Request(url + f"/tasks/{tid}", headers=h), timeout=40).read().decode())
            except Exception:
                continue
            if rec.get("status") in ("completed", "done", "finished", "succeeded"):
                ans = rec.get("answer") or ""; break
        print("\n=== Opus concept extraction (sample of 150) ===")
        try:
            j = json.loads(ans[ans.index("{"):ans.rindex("}") + 1])
            for c in j.get("concepts", []):
                print(f"  {c.get('name','?'):28} freq={c.get('freq','?'):5} verifiable={c.get('verifiable','?')}")
        except Exception:
            print(ans[:1500])
    except Exception as e:
        print("Opus extraction failed:", str(e)[:100])


if __name__ == "__main__":
    main()
