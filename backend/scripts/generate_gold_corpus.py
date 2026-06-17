"""Generate a DIVERSE easy-English Opus gold corpus across many games, classified by
template-type, for re-distilling templates (skill: distill-caption-template, step 1).
Each move: easy-English Opus gold (verified + correct-loop) + its move-type. Pools
examples per type into a corpus json. NON-DESTRUCTIVE (does not touch gold_tester_captions).

Env: PMONGO, LLM_EXPOSER_URL, LLM_EXPOSER_KEY
Usage: python scripts/generate_gold_corpus.py <gid1> <gid2> ...   (game ids space-separated)
"""
import os, sys, json
from concurrent.futures import ThreadPoolExecutor, as_completed
sys.path.insert(0, "/app/backend"); sys.path.insert(0, "/app/backend/scripts")
import pymongo
import regen_gold_easy as R          # gold_for (easy-English Opus + verify), facts_from
from group_gold_by_type import move_type

OUT = "/app/backend/scripts/_gold_corpus.json"


def main():
    gids = [a for a in sys.argv[1:] if not a.startswith("-")]
    db = pymongo.MongoClient(os.environ["PMONGO"])["chess_coach"]
    moves = []
    for gid in gids:
        dd = (db.game_analyses.find_one({"game_id": gid}, {"_id": 0, "decryption_v5_data": 1}) or {}).get("decryption_v5_data") or []
        for m in dd:
            if m.get("move_san") and m.get("fen_before"):
                moves.append(m)
    print(f"corpus: {len(gids)} games, {len(moves)} moves to caption (Opus 4.8, easy English)", flush=True)

    def work(m):
        cap, status = R.gold_for(R.facts_from(m), "white")  # student-pov framing; type carries side
        if not cap or "verif" not in status:   # keep only verified / verified_after_correction
            return None
        return (move_type(m), cap)

    corpus = {}
    done = 0
    with ThreadPoolExecutor(max_workers=10) as ex:
        futs = [ex.submit(work, m) for m in moves]
        for fut in as_completed(futs):
            r = fut.result()
            done += 1
            if r:
                t, cap = r
                corpus.setdefault(t, []).append(cap)
            if done % 50 == 0:
                print(f"  {done}/{len(moves)} done", flush=True)

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(corpus, f, ensure_ascii=False, indent=1)
    print("\n=== corpus per-type counts ===")
    for t in sorted(corpus, key=lambda x: -len(corpus[x])):
        print(f"  {t:24} {len(corpus[t])}")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
