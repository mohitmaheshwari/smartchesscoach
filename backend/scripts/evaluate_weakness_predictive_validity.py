"""Does ChessGuru predict what a player will get wrong NEXT?

This is the experiment that decides whether the learner-model thesis holds.
It runs retrospectively on games already in the corpus -- no new users, no
human-behaviour model, no training loop, no waiting.

Method (temporal, per player):
  order the player's analysed games by date_played_iso, split 70/30, rank
  their weaknesses from the TRAIN window only, then score that ranking
  against what actually happened in the TEST window.

Predictors compared:
  GLOBAL    corpus-wide gap ranking -- IDENTICAL for every player.
            THE CONTROL. If a personalised predictor cannot beat this,
            the personalisation is decorative: everyone's top weakness is
            simply the most common weakness.
  FREQ      the player's own gap rate in the train window.
  SEVERITY  the player's summed cp_loss per gap (frequency x cost).
  RECENCY   exponentially recency-weighted rate, the pattern_decay idea.

Scored with precision@3 against the player's true test-window top 3, plus
Spearman rank correlation over all gaps, plus lift of the predicted #1
weakness over that player's own average gap rate.

Only date_played_iso is used for ordering: raw date_played mixes YYYY.MM.DD
with YYYY-MM-DD, and "." sorts above "-", so every dotted game would land at
the end of the timeline and leak future games into the train window.

    python backend/scripts/evaluate_weakness_predictive_validity.py
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from motor.motor_asyncio import AsyncIOMotorClient

BACKEND_ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = (
    BACKEND_ROOT / "data" / "corpus_snapshots" / "weakness_predictive_validity.json"
)

MIN_GAMES = 30
TRAIN_FRACTION = 0.7
MIN_TEST_MOVES = 40          # a test window too small to rank is dropped
TOP_K = 3
RECENCY_DECAY = 0.9          # per game, most recent weighted 1.0


def _rank(scores: Dict[str, float]) -> List[str]:
    """Gaps ordered strongest-signal first; ties broken by name for determinism."""
    return [g for g, _ in sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))]


def _precision_at_k(predicted: Sequence[str], truth: Sequence[str], k: int) -> float:
    if not truth:
        return float("nan")
    top_pred, top_true = set(predicted[:k]), set(truth[:k])
    return len(top_pred & top_true) / float(min(k, len(top_true)))


def _spearman(a_rank: Sequence[str], b_rank: Sequence[str]) -> float:
    """Rank correlation over the union of gaps present in either ranking."""
    gaps = [g for g in a_rank if g in b_rank]
    n = len(gaps)
    if n < 3:
        return float("nan")
    ai = {g: i for i, g in enumerate(a_rank)}
    bi = {g: i for i, g in enumerate(b_rank)}
    d2 = sum((ai[g] - bi[g]) ** 2 for g in gaps)
    return 1 - (6 * d2) / (n * (n * n - 1))


def _gap_counts(moves: List[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
    """Per-gap count and summed cp_loss over a list of user moves."""
    out: Dict[str, Dict[str, float]] = defaultdict(lambda: {"n": 0.0, "cp": 0.0})
    for mv in moves:
        gap = str(mv.get("cognitive_gap") or "").strip()
        if not gap:
            continue
        try:
            cp = float(mv.get("cp_loss") or 0)
        except (TypeError, ValueError):
            cp = 0.0
        out[gap]["n"] += 1
        out[gap]["cp"] += max(0.0, cp)
    return dict(out)


async def load_player_games(db, user_id: str) -> List[Dict[str, Any]]:
    """Analysed games for a player, ordered by normalised date."""
    games = await db.games.find(
        {"user_id": user_id, "date_played_iso": {"$exists": True}},
        {"game_id": 1, "date_played_iso": 1},
    ).to_list(length=5000)
    games.sort(key=lambda g: (g.get("date_played_iso") or "", str(g.get("game_id"))))
    by_id = {str(g["game_id"]): g for g in games}
    if not by_id:
        return []

    analyses = await db.game_analyses.find(
        {"game_id": {"$in": list(by_id)}},
        {"game_id": 1, "stockfish_analysis.move_evaluations": 1},
    ).to_list(length=5000)
    moves_by_game: Dict[str, List[Dict[str, Any]]] = {}
    for doc in analyses:
        moves = [
            m for m in doc.get("stockfish_analysis", {}).get("move_evaluations", [])
            if not m.get("is_opponent_move")
        ]
        if moves:
            moves_by_game[str(doc.get("game_id"))] = moves

    ordered = []
    for g in games:
        gid = str(g["game_id"])
        if gid in moves_by_game:
            ordered.append({"game_id": gid,
                            "date": g.get("date_played_iso"),
                            "moves": moves_by_game[gid]})
    return ordered


def build_predictions(train_games: List[Dict[str, Any]],
                      global_rank: List[str]) -> Dict[str, List[str]]:
    flat = [m for g in train_games for m in g["moves"]]
    counts = _gap_counts(flat)

    freq = {g: v["n"] for g, v in counts.items()}
    severity = {g: v["cp"] for g, v in counts.items()}

    recency: Dict[str, float] = defaultdict(float)
    n_games = len(train_games)
    for idx, game in enumerate(train_games):
        weight = RECENCY_DECAY ** (n_games - 1 - idx)     # newest weight 1.0
        for gap, v in _gap_counts(game["moves"]).items():
            recency[gap] += v["n"] * weight

    return {
        "GLOBAL": list(global_rank),
        "FREQ": _rank(freq),
        "SEVERITY": _rank(severity),
        "RECENCY": _rank(dict(recency)),
    }


async def run(min_games: int) -> Dict[str, Any]:
    url = os.environ.get("MONGO_URL")
    if not url:
        raise SystemExit("MONGO_URL is required")
    client = AsyncIOMotorClient(url, serverSelectionTimeoutMS=8000)
    db = client[os.environ.get("DB_NAME", "chess_coach")]

    user_ids = await db.games.distinct("user_id", {"date_played_iso": {"$exists": True}})

    # Corpus-wide gap ranking = the control predictor.
    global_counts: Counter = Counter()
    per_player: List[Dict[str, Any]] = []
    loaded: Dict[str, List[Dict[str, Any]]] = {}
    for uid in user_ids:
        if not uid:
            continue
        games = await load_player_games(db, uid)
        if len(games) < min_games:
            continue
        loaded[uid] = games
        for g in games:
            for gap, v in _gap_counts(g["moves"]).items():
                global_counts[gap] += v["n"]
    client.close()

    global_rank = [g for g, _ in global_counts.most_common()]

    results: Dict[str, List[float]] = defaultdict(list)
    spearman: Dict[str, List[float]] = defaultdict(list)
    lifts: List[float] = []
    skipped = 0

    for uid, games in loaded.items():
        split = int(len(games) * TRAIN_FRACTION)
        train, test = games[:split], games[split:]
        test_moves = [m for g in test for m in g["moves"]]
        if len(test_moves) < MIN_TEST_MOVES or not train:
            skipped += 1
            continue

        truth_counts = _gap_counts(test_moves)
        if len(truth_counts) < 2:
            skipped += 1
            continue
        truth_rank = _rank({g: v["n"] for g, v in truth_counts.items()})

        preds = build_predictions(train, global_rank)
        for name, ranking in preds.items():
            p = _precision_at_k(ranking, truth_rank, TOP_K)
            if not math.isnan(p):
                results[name].append(p)
            s = _spearman(ranking, truth_rank)
            if not math.isnan(s):
                spearman[name].append(s)

        # Lift: how much more often the FREQ-predicted #1 occurs in the test
        # window than this player's average gap.
        total_test = sum(v["n"] for v in truth_counts.values())
        avg = total_test / len(truth_counts)
        top1 = preds["FREQ"][0] if preds["FREQ"] else None
        if top1 and avg > 0:
            lifts.append(truth_counts.get(top1, {"n": 0.0})["n"] / avg)

        per_player.append({
            "user_id": uid, "games": len(games),
            "train_games": len(train), "test_games": len(test),
            "test_moves": len(test_moves),
            "truth_top3": truth_rank[:3],
            "freq_top3": preds["FREQ"][:3],
            "global_top3": global_rank[:3],
        })

    summary = {}
    for name in ("GLOBAL", "FREQ", "SEVERITY", "RECENCY"):
        vals, sp = results.get(name, []), spearman.get(name, [])
        summary[name] = {
            "players": len(vals),
            "precision_at_3": round(statistics.mean(vals), 3) if vals else None,
            "spearman": round(statistics.mean(sp), 3) if sp else None,
        }

    return {
        "schema_version": "weakness_predictive_validity.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "params": {"min_games": min_games, "train_fraction": TRAIN_FRACTION,
                   "top_k": TOP_K, "recency_decay": RECENCY_DECAY,
                   "min_test_moves": MIN_TEST_MOVES},
        "global_gap_ranking": global_rank,
        "summary": summary,
        "median_lift_of_predicted_top1": (
            round(statistics.median(lifts), 2) if lifts else None),
        "players_evaluated": len(per_player),
        "players_skipped": skipped,
        "per_player": per_player[:40],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-games", type=int, default=MIN_GAMES)
    args = parser.parse_args()
    report = asyncio.run(run(args.min_games))
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(report, indent=1), encoding="utf-8")

    print(f"players evaluated={report['players_evaluated']} "
          f"skipped={report['players_skipped']}")
    print(f"corpus gap ranking: {report['global_gap_ranking'][:5]}")
    print(f"{'predictor':10s} {'players':>8s} {'prec@3':>8s} {'spearman':>9s}")
    for name, s in report["summary"].items():
        print(f"  {name:8s} {str(s['players']):>8s} "
              f"{str(s['precision_at_3']):>8s} {str(s['spearman']):>9s}")
    print(f"median lift of predicted #1 weakness: "
          f"{report['median_lift_of_predicted_top1']}")
    print(f"written -> {OUT_PATH}")


if __name__ == "__main__":
    main()
