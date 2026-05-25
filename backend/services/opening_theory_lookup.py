"""
opening_theory_lookup — FEN-keyed access to the opening theory tree.

Loads data/coaching/opening_theory_tree.json once at module import,
flattens it into a {normalized_fen: theory_record} dictionary, and
exposes `match_position(fen)` for the caption pipeline to call on
every opening-phase move.

Quality controls (per the 2026-05-25 audit on 137k user moves):

  1. PRE-COMMIT FILTER — the tree mixes two kinds of critical_positions:
       "after_<SAN>"      → a real anchor of the opening
       "move<N>_<SAN>"    → transposition hint (alternative move at ply N)
     The move<N>_* entries share FENs across many openings (the position
     after 1.e4 e5 2.Nf3 is "tagged" by italian/spanish/scotch/petrov/
     philidor) and collapse to a single lookup entry where the last
     opening loaded wins — leading to mis-attribution like "Petrov"
     on a position that isn't yet Petrov. Filter them out.

  2. FEN-REPLAY DERIVATION — 51 of 176 critical_positions lack an
     explicit fen_pattern. For these, replay main_line +
     moves_from_parent + continuation to derive the FEN. This unlocks
     the variation-level teaching positions (Scandinavian after_Nc3,
     Caro-Kann Classical after_Nxe4, etc.) — where the real lessons
     live.

  3. NORMALIZED FEN comparison — strip halfmove + fullmove counters so
     transposition-equivalent positions match. Keep placement, side-to-
     move, castling rights, and en-passant — all of which DO matter.

After filtering: 75 trustworthy positions across 23 openings. Audit
on 4,974 games shows 3,029 matches (2.2% of opening moves) with clean
opening attribution.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import chess

logger = logging.getLogger(__name__)


_THEORY_TREE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "coaching", "opening_theory_tree.json"
)


def _normalize_san(san: str) -> str:
    return (san or "").rstrip("+#!?")


def _normalize_fen(fen: str) -> str:
    """Strip halfmove + fullmove counters; keep placement/stm/castling/ep."""
    if not fen:
        return ""
    parts = fen.split()
    if len(parts) >= 4:
        return " ".join(parts[:4])
    return fen.strip()


def _is_transposition_hint_cp(cp_key: str) -> bool:
    """move1_/move2_/move3_ critical positions are transposition hints,
    not anchors of the opening. See module docstring for context."""
    return (
        cp_key.startswith("move1_")
        or cp_key.startswith("move2_")
        or cp_key.startswith("move3_")
    )


def _replay_path(plies: List[str]) -> List[Tuple[str, str]]:
    """Replay SAN plies from start. Returns (san, normalized_fen) per
    successful ply. Stops on first illegal SAN."""
    board = chess.Board()
    out: List[Tuple[str, str]] = []
    for san in plies:
        try:
            move = board.parse_san(san)
        except Exception:
            break
        board.push(move)
        out.append((_normalize_san(san), _normalize_fen(board.fen())))
    return out


def _derive_fens_for_path(
    main_line: List[str],
    moves_from_parent: Optional[List[str]],
    continuation: Optional[List[str]],
    cp_keys: List[str],
) -> Dict[str, str]:
    """For each cp_key shaped 'after_<SAN>', find the deepest ply along
    the path matching <SAN> and return its FEN."""
    plies = list(main_line or [])
    if moves_from_parent:
        plies += list(moves_from_parent)
    if continuation:
        plies += list(continuation)
    path = _replay_path(plies)
    out: Dict[str, str] = {}
    for cp_key in cp_keys:
        if not cp_key.startswith("after_"):
            continue
        target = _normalize_san(cp_key[len("after_"):])
        for i in range(len(path) - 1, -1, -1):
            if path[i][0] == target:
                out[cp_key] = path[i][1]
                break
    return out


def _build_lookup() -> Dict[str, Dict[str, Any]]:
    """Load the theory tree from disk and build {fen: record}.

    Returns an empty dict + logs a warning if the file is missing or
    malformed — the caption pipeline must keep working without theory
    enrichment in that case.
    """
    try:
        with open(_THEORY_TREE_PATH, encoding="utf-8") as f:
            tree = json.load(f)
    except Exception as exc:
        logger.warning(
            f"[opening_theory] failed to load theory tree at "
            f"{_THEORY_TREE_PATH}: {exc}"
        )
        return {}

    out: Dict[str, Dict[str, Any]] = {}
    for opening_key, opening in tree.items():
        if opening_key == "_meta":
            continue
        common = opening.get("common_learnings") or []
        main_line = opening.get("main_line") or []

        # Top-level critical positions
        top_cps = opening.get("critical_positions") or {}
        top_cp_keys = [k for k in top_cps if not _is_transposition_hint_cp(k)]
        top_derived = _derive_fens_for_path(main_line, None, None, top_cp_keys)
        for cp_key in top_cp_keys:
            cp = top_cps[cp_key]
            fen = cp.get("fen_pattern") or top_derived.get(cp_key)
            if not fen:
                continue
            key = _normalize_fen(fen)
            out[key] = _build_record(
                opening_key=opening_key,
                opening_name=opening.get("name"),
                variation_key=None,
                variation_name=None,
                cp_key=cp_key,
                cp=cp,
                common_learnings=common,
            )

        # Nested variation critical positions
        for var_key, var in (opening.get("variations") or {}).items():
            var_cps = var.get("critical_positions") or {}
            var_cp_keys = [k for k in var_cps if not _is_transposition_hint_cp(k)]
            var_derived = _derive_fens_for_path(
                main_line,
                var.get("moves_from_parent"),
                var.get("continuation"),
                var_cp_keys,
            )
            for cp_key in var_cp_keys:
                cp = var_cps[cp_key]
                fen = cp.get("fen_pattern") or var_derived.get(cp_key)
                if not fen:
                    continue
                key = _normalize_fen(fen)
                out[key] = _build_record(
                    opening_key=opening_key,
                    opening_name=opening.get("name"),
                    variation_key=var_key,
                    variation_name=var.get("name"),
                    cp_key=cp_key,
                    cp=cp,
                    common_learnings=common,
                )

    logger.info(f"[opening_theory] loaded {len(out)} positions")
    return out


def _build_record(
    *,
    opening_key: str,
    opening_name: Optional[str],
    variation_key: Optional[str],
    variation_name: Optional[str],
    cp_key: str,
    cp: Dict[str, Any],
    common_learnings: List[str],
) -> Dict[str, Any]:
    return {
        "opening_key": opening_key,
        "opening_name": opening_name,
        "variation_key": variation_key,
        "variation_name": variation_name,
        "cp_key": cp_key,
        "key_decision": cp.get("key_decision"),
        "best_moves": cp.get("best_moves") or cp.get("best_moves_white") or {},
        "mistake_moves": cp.get("mistake_moves") or {},
        "common_learnings": common_learnings,
    }


# Module-level singleton — built once on import.
_LOOKUP: Dict[str, Dict[str, Any]] = _build_lookup()


def match_position(fen: str) -> Optional[Dict[str, Any]]:
    """Return the theory record for `fen`, or None if no match.

    The caller passes the POST-move FEN (the position the player just
    reached). Normalizes internally — no need to strip clocks first.
    """
    if not fen:
        return None
    key = _normalize_fen(fen)
    return _LOOKUP.get(key)


def classify_played_move(theory: Dict[str, Any], played_san: str) -> str:
    """Classify a played move against the theory record's best_moves /
    mistake_moves dicts. Returns 'best' / 'mistake' / 'critical_only'.

    'best' / 'mistake' are precise teaching moments: "you played the
    main line" / "you walked into the typical mistake."
    'critical_only' means the user is in a known position but their
    move isn't catalogued — surface the key_decision + top idea as
    contextual teaching.
    """
    if not theory:
        return "critical_only"
    san = _normalize_san(played_san or "")
    for k in (theory.get("best_moves") or {}):
        if _normalize_san(k) == san:
            return "best"
    for k in (theory.get("mistake_moves") or {}):
        if _normalize_san(k) == san:
            return "mistake"
    return "critical_only"


def top_best_move(theory: Dict[str, Any]) -> Optional[Tuple[str, Dict[str, Any]]]:
    """Return the first (SAN, idea_dict) pair from best_moves, or None.

    Used when the played move isn't in best_moves — surface the most
    canonical alternative as the teaching moment ("the main line is X").
    """
    bm = theory.get("best_moves") or {}
    if not bm:
        return None
    san, info = next(iter(bm.items()))
    return san, info


def lookup_size() -> int:
    """How many positions are loaded — for diagnostics."""
    return len(_LOOKUP)
