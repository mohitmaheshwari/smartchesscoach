"""
Diagnostic V2 — offline puzzle pool curation.

Builds the `diagnostic_pool` collection from the 4.1M-row `lichess_puzzles`
collection: 10 concepts x 3 rating tiers, every puzzle engine-verified to
have ONE clear idea (best move beats 2nd-best by >=150cp, or is mate).

Run inside the backend container (needs Stockfish + Mongo):
    docker exec chess-coach-backend python3 scripts/build_diagnostic_pool.py
    docker exec chess-coach-backend python3 scripts/build_diagnostic_pool.py --dry-run
    docker exec chess-coach-backend python3 scripts/build_diagnostic_pool.py --depth 14

Idempotent: wipes and rebuilds `diagnostic_pool` on each run (unless --dry-run).

Stored doc shape (consumed by services/diagnostic_service.DiagnosticGrader):
    {
      puzzle_id: "lichess_<id>",
      lichess_id: "<id>",
      concept: "fork",                # one of CONCEPTS keys
      subtype: "offense"|"defense"|None,
      fen: "...",                     # SOLVE position (after Lichess setup move)
      fen_original: "...",            # raw Lichess fen (before setup move)
      setup_move_uci: "e2e4",
      moves: ["d5e7", "g8h8", ...],   # UCI from the solve position; [0]=user's move
      solution_san: "Ne7+",
      user_move_idx: 0,
      puzzle_rating: 1208,
      tier: "low"|"mid"|"high",
      multipv: [{"move_uci","move_san","eval_cp","mate_in"}, ...],  # solver POV
      eval_before: 2.5,               # pawns, solver POV (= multipv[0] eval)
      reserve: false,
      themes: [...], popularity, nb_plays, rating_dev, game_url,
      curated_at, pool_version: 1
    }
"""

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import chess
import chess.engine
from motor.motor_asyncio import AsyncIOMotorClient

from config import STOCKFISH_PATH
from services.diagnostic_service import (
    DIAGNOSTIC_GRADE_VERSION,
    classify_diagnostic_eval,
    diagnostic_grade_fingerprint,
)

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("build_diagnostic_pool")

POOL_VERSION = 2

# Mate scores use the same convention as stockfish_service:
# cp = 10000 - |mate_in| * 10, signed toward the mating side.
MATE_CP_BASE = 10000

# ---------------------------------------------------------------------------
# Concept definitions (priority order = diagnosis "headline gap" order).
#
# themes: which Lichess themes feed this concept (tried in order).
# disc:   this concept's DISCRIMINATIVE themes. A candidate is "pure" for the
#         concept iff its discriminative themes are a non-empty subset of
#         `disc` — except concepts with disc=[] (calculation/winning_technique)
#         which require ZERO discriminative themes (pure calculation /
#         conversion, no named tactic that belongs to another concept).
# ---------------------------------------------------------------------------

DISCRIMINATIVE_THEMES = {
    "hangingPiece", "defensiveMove", "fork", "pin", "skewer",
    "mateIn1", "mateIn2", "backRankMate", "exposedKing",
    "pawnEndgame", "rookEndgame", "opening",
}

CONCEPTS: Dict[str, Dict[str, Any]] = {
    "threat_response": {
        "themes": ["exposedKing", "defensiveMove"],
        "disc": ["exposedKing", "defensiveMove"],
    },
    "piece_safety": {
        "themes": ["hangingPiece", "defensiveMove"],
        "disc": ["hangingPiece", "defensiveMove"],
    },
    "mate_patterns": {
        "themes": ["mateIn1", "backRankMate"],
        "disc": ["mateIn1", "backRankMate"],
    },
    "fork": {"themes": ["fork"], "disc": ["fork"]},
    "pin": {"themes": ["pin"], "disc": ["pin"]},
    "skewer": {"themes": ["skewer"], "disc": ["skewer"]},
    "calculation": {
        # multi-move walk concept — needs >=2 user moves in the solution.
        # allow_empty_disc: a pure "short"/"crushing" line with NO named
        # tactic is exactly what a calculation probe wants.
        "themes": ["mateIn2", "short", "crushing"],
        "disc": ["mateIn2"],
        "allow_empty_disc": True,
        "min_user_moves": 2,
    },
    "opening": {"themes": ["opening"], "disc": ["opening"]},
    "endgame": {
        "themes": ["pawnEndgame", "rookEndgame"],
        "disc": ["pawnEndgame", "rookEndgame"],
    },
    "winning_technique": {
        "themes": ["crushing", "advantage"],
        "disc": [],  # pure conversion: no named-tactic theme allowed
    },
}

# piece_safety spec split: offense (spot the hanging piece) vs defense
# (save your own). Tagged for copy; both live under the one concept.
def _piece_safety_subtype(themes: List[str]) -> Optional[str]:
    if "hangingPiece" in themes:
        return "offense"
    if "defensiveMove" in themes:
        return "defense"
    return None


TIERS = [
    ("low", 800, 700, 900),
    ("mid", 1200, 1100, 1300),
    ("high", 1600, 1500, 1700),
]

# Quality gates
MIN_POPULARITY = 90
MIN_NB_PLAYS = 1000
MAX_RATING_DEV = 80
MULTIPV_GAP_CP = 150       # best must beat 2nd-best by this much (or be mate)
CANDIDATES_PER_TIER = 50   # how many gated candidates to pull before engine pass
ACCEPT_PER_TIER = 2        # 1 primary + 1 reserve


def _score_to_cp(score: chess.engine.PovScore, pov: chess.Color) -> (int, Optional[int]):
    """(cp from `pov` perspective, mate_in or None) — codebase mate convention."""
    s = score.pov(pov)
    if s.is_mate():
        mate_in = s.mate()
        cp = MATE_CP_BASE - abs(mate_in) * 10
        return (cp if mate_in > 0 else -cp), mate_in
    return s.score() or 0, None


def _is_pure(themes: List[str], concept_cfg: Dict[str, Any]) -> bool:
    disc_here = set(themes) & DISCRIMINATIVE_THEMES
    allowed = set(concept_cfg["disc"])
    if not disc_here <= allowed:
        return False  # carries a theme that belongs to another concept
    # Concepts with named themes normally require one to be present;
    # allow_empty_disc opts out (pure-calculation / pure-conversion lines).
    allow_empty = concept_cfg.get("allow_empty_disc", not allowed)
    return bool(disc_here) or allow_empty


def _prepare_candidate(raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Advance the Lichess setup move; return normalized candidate or None."""
    fen = raw.get("fen") or ""
    uci_moves = raw.get("moves") or []
    if not fen or len(uci_moves) < 2:
        return None
    try:
        board = chess.Board(fen)
        setup = chess.Move.from_uci(uci_moves[0])
        if setup not in board.legal_moves:
            return None
        board.push(setup)
        solution = uci_moves[1:]
        first = chess.Move.from_uci(solution[0])
        if first not in board.legal_moves:
            return None
        return {
            "solve_fen": board.fen(),
            "solution": solution,
            "solution_san": board.san(first),
            "setup_move_uci": uci_moves[0],
            "raw": raw,
        }
    except Exception:
        return None


def _engine_gate(engine: chess.engine.SimpleEngine, cand: Dict[str, Any],
                 depth: int) -> Optional[Dict[str, Any]]:
    """ONE multipv=3 analysis on the solve position. Pass iff:
      - engine best == puzzle's stated solution move (or both are mate), AND
      - best beats 2nd-best by >= MULTIPV_GAP_CP, or best is mate.
    Returns {"multipv": [...], "eval_before": float} or None on reject.
    """
    board = chess.Board(cand["solve_fen"])
    pov = board.turn
    try:
        infos = engine.analyse(board, chess.engine.Limit(depth=depth), multipv=3)
    except Exception as e:
        logger.warning(f"engine analyse failed: {e}")
        return None
    if not infos:
        return None

    lines = []
    for info in infos:
        pv = info.get("pv") or []
        if not pv:
            continue
        cp, mate_in = _score_to_cp(info["score"], pov)
        lines.append({
            "move_uci": pv[0].uci(),
            "move_san": board.san(pv[0]),
            "eval_cp": cp,
            "mate_in": mate_in,
        })
    if not lines:
        return None

    best = lines[0]
    stated = cand["solution"][0]

    # Best move must agree with the puzzle's stated solution. Exception:
    # both are mates (Lichess accepts any mate; keep the stated line so the
    # multi-move walk stays consistent).
    if best["move_uci"] != stated:
        stated_is_mate = False
        for ln in lines:
            if ln["move_uci"] == stated and ln["mate_in"] is not None:
                stated_is_mate = True
        if not (best["mate_in"] is not None and stated_is_mate):
            return None

    # Single-idea gate
    if best["mate_in"] is None:
        if len(lines) >= 2 and best["eval_cp"] - lines[1]["eval_cp"] < MULTIPV_GAP_CP:
            return None

    return {"multipv": lines, "eval_before": round(best["eval_cp"] / 100.0, 2)}


def _freeze_step_grades(
    engine: chess.engine.SimpleEngine,
    cand: Dict[str, Any],
    puzzle_rating: Optional[int],
    depth: int,
) -> Optional[List[Dict[str, Any]]]:
    """Evaluate every legal user reply once, offline, at each lesson step."""
    board = chess.Board(cand["solve_fen"])
    solution = cand["solution"]
    frozen_steps: List[Dict[str, Any]] = []
    n_user_moves = (len(solution) + 1) // 2

    for step_index in range(n_user_moves):
        solution_index = step_index * 2
        if solution_index >= len(solution):
            return None
        try:
            solution_move = chess.Move.from_uci(solution[solution_index])
        except ValueError:
            return None
        if solution_move not in board.legal_moves:
            return None

        legal_moves = list(board.legal_moves)
        try:
            raw_infos = engine.analyse(
                board,
                chess.engine.Limit(depth=depth),
                multipv=len(legal_moves),
            )
        except Exception as exc:
            logger.warning(f"offline legal-move grading failed: {exc}")
            return None
        infos = raw_infos if isinstance(raw_infos, list) else [raw_infos]
        eval_by_uci: Dict[str, int] = {}
        for info in infos:
            pv = info.get("pv") or []
            if not pv:
                continue
            root_move = pv[0]
            eval_cp, _ = _score_to_cp(info["score"], board.turn)
            eval_by_uci[root_move.uci()] = int(eval_cp)
        if len(eval_by_uci) != len(legal_moves):
            logger.warning(
                "offline grading map incomplete: "
                f"{len(eval_by_uci)}/{len(legal_moves)} legal moves"
            )
            return None

        solution_eval = eval_by_uci.get(solution_move.uci())
        if solution_eval is None:
            return None
        grade_by_uci: Dict[str, Dict[str, Any]] = {}
        for legal_move in legal_moves:
            move_uci = legal_move.uci()
            eval_after = eval_by_uci[move_uci]
            verdict, cp_loss = classify_diagnostic_eval(
                solution_eval,
                eval_after,
                puzzle_rating,
            )
            if move_uci == solution_move.uci():
                verdict, cp_loss = "UNDERSTOOD", 0
            grade_by_uci[move_uci] = {
                "eval_after_cp": eval_after,
                "cp_loss": cp_loss,
                "verdict": verdict,
            }

        frozen_steps.append({
            "step": step_index,
            "fen": board.fen(),
            "solution_uci": solution_move.uci(),
            "solution_eval_cp": solution_eval,
            "grade_by_uci": grade_by_uci,
        })

        board.push(solution_move)
        opponent_index = solution_index + 1
        if opponent_index < len(solution):
            try:
                opponent_move = chess.Move.from_uci(solution[opponent_index])
            except ValueError:
                return None
            if opponent_move not in board.legal_moves:
                return None
            board.push(opponent_move)

    return frozen_steps


async def build_pool(db, depth: int, dry_run: bool) -> List[Dict[str, Any]]:
    curated: List[Dict[str, Any]] = []
    used_ids: set = set()
    engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
    engine.configure({"Threads": 1, "Hash": 128})
    engine_calls = 0

    try:
        for concept, cfg in CONCEPTS.items():
            min_user_moves = cfg.get("min_user_moves", 1)
            for tier_name, tier_rating, lo, hi in TIERS:
                accepted = 0
                for theme in cfg["themes"]:
                    if accepted >= ACCEPT_PER_TIER:
                        break
                    cursor = db.lichess_puzzles.find(
                        {
                            "themes": theme,
                            "rating": {"$gte": lo, "$lte": hi},
                            "popularity": {"$gte": MIN_POPULARITY},
                            "nb_plays": {"$gte": MIN_NB_PLAYS},
                            "rating_dev": {"$lte": MAX_RATING_DEV},
                        },
                        {"_id": 0},
                    ).sort("nb_plays", -1).limit(CANDIDATES_PER_TIER)

                    async for raw in cursor:
                        if accepted >= ACCEPT_PER_TIER:
                            break
                        pid = raw.get("puzzle_id")
                        if not pid or pid in used_ids:
                            continue
                        themes = raw.get("themes") or []
                        if not _is_pure(themes, cfg):
                            continue
                        cand = _prepare_candidate(raw)
                        if not cand:
                            continue
                        # user moves are solution[0], solution[2], ...
                        n_user_moves = (len(cand["solution"]) + 1) // 2
                        if n_user_moves < min_user_moves:
                            continue
                        # Non-calculation concepts: single decisive move keeps
                        # grading unambiguous (we grade move 0 only).
                        if concept != "calculation" and n_user_moves > 2:
                            continue

                        gate = _engine_gate(engine, cand, depth)
                        engine_calls += 1
                        if not gate:
                            continue
                        step_grades = _freeze_step_grades(
                            engine,
                            cand,
                            raw.get("rating"),
                            depth,
                        )
                        engine_calls += (len(cand["solution"]) + 1) // 2
                        if not step_grades:
                            continue

                        used_ids.add(pid)
                        subtype = (
                            _piece_safety_subtype(themes)
                            if concept == "piece_safety" else None
                        )
                        document = {
                            "puzzle_id": f"lichess_{pid}",
                            "lichess_id": pid,
                            "concept": concept,
                            "subtype": subtype,
                            "matched_theme": theme,
                            "fen": cand["solve_fen"],
                            "fen_original": raw.get("fen"),
                            "setup_move_uci": cand["setup_move_uci"],
                            "moves": cand["solution"],
                            "solution_san": cand["solution_san"],
                            "user_move_idx": 0,
                            "puzzle_rating": raw.get("rating"),
                            "tier": tier_name,
                            "tier_rating": tier_rating,
                            "multipv": gate["multipv"],
                            "eval_before": gate["eval_before"],
                            "reserve": accepted >= 1,  # first accept = primary
                            "themes": themes,
                            "popularity": raw.get("popularity"),
                            "nb_plays": raw.get("nb_plays"),
                            "rating_dev": raw.get("rating_dev"),
                            "game_url": raw.get("game_url"),
                            "curated_at": datetime.now(timezone.utc).isoformat(),
                            "pool_version": POOL_VERSION,
                            "grade_version": DIAGNOSTIC_GRADE_VERSION,
                            "step_grades": step_grades,
                        }
                        document["grade_fingerprint"] = (
                            diagnostic_grade_fingerprint(document)
                        )
                        curated.append(document)
                        accepted += 1
                if accepted == 0:
                    logger.warning(
                        f"  !! {concept}@{tier_name}: no puzzle passed the gates"
                    )
    finally:
        engine.quit()

    logger.info(f"\nEngine calls: {engine_calls}")

    if not dry_run:
        await db.diagnostic_pool.delete_many({})
        if curated:
            await db.diagnostic_pool.insert_many(
                [dict(d) for d in curated]  # insert_many mutates (_id) — keep copies
            )
        await db.diagnostic_pool.create_index("puzzle_id", unique=True)
        await db.diagnostic_pool.create_index([("concept", 1), ("tier", 1)])
    return curated


def summarize(curated: List[Dict[str, Any]]) -> bool:
    """Log the per-concept summary; return True iff every concept has >=2
    primary puzzles."""
    ok = True
    primaries = [d for d in curated if not d["reserve"]]
    reserves = [d for d in curated if d["reserve"]]
    logger.info(
        f"\n{len(primaries)} primary + {len(reserves)} reserve = "
        f"{len(curated)} puzzles curated"
    )
    for concept in CONCEPTS:
        parts = []
        n_primary = 0
        for tier_name, tier_rating, _, _ in TIERS:
            n = sum(1 for d in primaries
                    if d["concept"] == concept and d["tier"] == tier_name)
            n_primary += n
            parts.append(f"{n}@{tier_rating}")
        n_res = sum(1 for d in reserves if d["concept"] == concept)
        flag = ""
        if n_primary < 2:
            flag = "  <-- UNDER 2 PUZZLES"
            ok = False
        logger.info(f"  {concept:18s} {' + '.join(parts)} (+{n_res} reserve){flag}")
    return ok


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--depth", type=int, default=16,
                        help="engine depth for the multipv gate (default 16)")
    parser.add_argument("--dry-run", action="store_true",
                        help="curate + summarize without writing to Mongo")
    args = parser.parse_args()

    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "chess_coach")
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    n_lichess = await db.lichess_puzzles.estimated_document_count()
    logger.info(f"lichess_puzzles: ~{n_lichess} rows | depth={args.depth} "
                f"| dry_run={args.dry_run}\n")
    if n_lichess == 0:
        logger.error("lichess_puzzles is empty — nothing to curate from.")
        sys.exit(1)

    curated = await build_pool(db, depth=args.depth, dry_run=args.dry_run)
    ok = summarize(curated)
    if not args.dry_run:
        logger.info(f"\nWrote {len(curated)} docs to diagnostic_pool "
                    f"(db={db_name}).")
    if not ok:
        logger.error("\nFAIL: at least one concept has <2 primary puzzles.")
        sys.exit(2)
    logger.info("\nOK: every concept has >=2 primary puzzles.")


if __name__ == "__main__":
    asyncio.run(main())
