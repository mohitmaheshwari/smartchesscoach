"""Aligned-corpus-table: for each gold record, run the production detector layer
(extract_facts -> extract_primary_reason) over the FEN and JOIN the system's chosen
lesson against the gold lesson/caption. Re-derives best_move + PVs with Stockfish
(records dropped them). This is the substrate the lesson_selector is learned from.

Emits _aligned_table.jsonl (one row/move) + prints the three locked analyses:
  1. conditional gold-lesson dataset shape (system primary_reason x gold type)
  2. detector firing-distribution (how often each system reason fires)
  3. fired-but-gold-silent set (system would teach; gold stayed routine) = FP candidates
  + system-silent-but-gold-teaches (gold teaches; system has no reason) = MISS candidates

Env: none (reads scripts/_gold_records_wg.jsonl). Usage: python scripts/build_aligned_table.py
"""
import os, sys, json, shutil, collections
from concurrent.futures import ThreadPoolExecutor, as_completed
sys.path.insert(0, "/app/backend")
import chess, chess.engine
from services.caption_facts import extract_facts, extract_primary_reason

SF = shutil.which("stockfish") or "/usr/games/stockfish"
REC = "/app/backend/scripts/_gold_records_wg.jsonl"
OUT = "/app/backend/scripts/_aligned_table.jsonl"
ROUTINE = {"good_other", "opp_other", "good_develop", "opp_develop"}  # "quiet/routine" gold buckets


def pv_san(board, pv, k=6):
    b = board.copy(); out = []
    for mv in pv[:k]:
        try: out.append(b.san(mv))
        except Exception: break
        b.push(mv)
    return out


def enrich(eng, r):
    """Add best_move_san, pv_after_best, pv_after_played via Stockfish."""
    fb = r["fen_before"]
    try:
        bb = chess.Board(fb)
        info = eng.analyse(bb, chess.engine.Limit(depth=16))
        pvb = info.get("pv", [])
        best_san = bb.san(pvb[0]) if pvb else None
        pv_best = pv_san(bb, pvb, 6)
    except Exception:
        best_san, pv_best = None, []
    pv_played = []
    fa = r.get("fen_after")
    if fa:
        try:
            ba = chess.Board(fa)
            if not ba.is_game_over():
                pv_played = pv_san(ba, eng.analyse(ba, chess.engine.Limit(depth=14)).get("pv", []), 6)
        except Exception:
            pass
    return best_san, pv_best, pv_played


def process_chunk(records):
    try:
        eng = chess.engine.SimpleEngine.popen_uci(SF)
    except Exception:
        return []
    rows = []
    try:
        for r in records:
            best_san, pv_best, pv_played = enrich(eng, r)
            reason_kind = None
            try:
                facts = extract_facts(
                    fen_before=r["fen_before"], played_san=r["move_san"],
                    best_move_san=best_san, cp_loss=int(r.get("cp_loss") or 0),
                    pv_after_played=pv_played, pv_after_best=pv_best,
                    full_move_number=r.get("move_number"),
                    mover_is_user=bool(r.get("is_user_move")),
                )
                pr = extract_primary_reason(facts)
                reason_kind = (pr or {}).get("category") if pr else None
            except Exception:
                reason_kind = "__error__"
            rows.append({
                "game": r["game"], "move_number": r.get("move_number"), "move_san": r["move_san"],
                "is_user_move": bool(r.get("is_user_move")), "cp_loss": int(r.get("cp_loss") or 0),
                "gold_type": r["type"], "gold_caption": r["caption"],
                "best_move_san": best_san, "system_reason": reason_kind,
            })
    finally:
        eng.quit()
    return rows


def main():
    recs = [json.loads(l) for l in open(REC, encoding="utf-8")]
    print(f"{len(recs)} records; re-deriving engine truth + running detectors (8 workers)", flush=True)
    W = 8
    chunks = [recs[i::W] for i in range(W)]
    rows = []
    with ThreadPoolExecutor(max_workers=W) as ex:
        futs = [ex.submit(process_chunk, c) for c in chunks]
        done = 0
        for fut in as_completed(futs):
            rows.extend(fut.result()); done += 1
            print(f"  chunk {done}/{W} done, {len(rows)} rows", flush=True)
    with open(OUT, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    # ── Analyses ───────────────────────────────────────────────────────
    has_reason = lambda x: x and x != "__error__"
    fires = [r for r in rows if has_reason(r["system_reason"])]
    silent = [r for r in rows if not has_reason(r["system_reason"])]
    gold_routine = lambda r: r["gold_type"] in ROUTINE

    print(f"\n=== {len(rows)} rows | system FIRES on {len(fires)} ({len(fires)*100//len(rows)}%), "
          f"SILENT on {len(silent)} ===")

    print("\n[1] system reason -> gold type (top pairings)")
    pair = collections.Counter((r["system_reason"], r["gold_type"]) for r in fires)
    for (sr, gt), n in pair.most_common(20):
        print(f"  {n:5}  {sr:22} -> {gt}")

    print("\n[2] detector firing-distribution")
    fd = collections.Counter(r["system_reason"] for r in fires)
    for sr, n in fd.most_common():
        print(f"  {n:5}  {sr}")

    print("\n[3a] FIRED-but-gold-routine (false-positive candidates)")
    fp = [r for r in fires if gold_routine(r)]
    fpc = collections.Counter(r["system_reason"] for r in fp)
    print(f"  total {len(fp)} ({len(fp)*100//max(1,len(fires))}% of firings land on a routine gold)")
    for sr, n in fpc.most_common(10):
        print(f"  {n:5}  {sr}")

    print("\n[3b] SILENT-but-gold-teaches (miss candidates: gold non-routine, system no reason)")
    miss = [r for r in silent if not gold_routine(r)]
    mc = collections.Counter(r["gold_type"] for r in miss)
    print(f"  total {len(miss)} ({len(miss)*100//max(1,len(silent))}% of silences sit on a teaching gold)")
    for gt, n in mc.most_common(12):
        print(f"  {n:5}  {gt}")
    print(f"\nWROTE {OUT}", flush=True)


if __name__ == "__main__":
    main()
