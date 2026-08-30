"""Snapshot exact Syzygy evidence for canonical endgame lesson positions.

This is an authoring/CI preparation tool, never a runtime dependency. It reads
the public Lichess tablebase API once, stores only the evidence needed by the
offline curriculum gate, and hashes each complete response for provenance.

Usage:
    python scripts/snapshot_curriculum_tablebase.py
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from typing import Any, Dict
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import chess


BACKEND_ROOT = Path(__file__).resolve().parent.parent
SOURCE_PATH = BACKEND_ROOT / "data" / "coaching" / "endgame_theory_tree.json"
OUTPUT_PATH = (
    BACKEND_ROOT
    / "data"
    / "corpus_snapshots"
    / "curriculum_endgame_tablebase_2026-08-29.json"
)
API_ENDPOINT = "https://tablebase.lichess.ovh/standard"

_WDL = {
    "win": 1,
    "cursed-win": 1,
    "draw": 0,
    "loss": -1,
    "blessed-loss": -1,
}


def _request_tablebase(fen: str) -> tuple[Dict[str, Any], str]:
    url = f"{API_ENDPOINT}?{urlencode({'fen': fen})}"
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "ChessGuru curriculum verifier/1.0",
        },
    )
    with urlopen(request, timeout=30) as response:
        raw = response.read()
    payload = json.loads(raw)
    return payload, hashlib.sha256(raw).hexdigest()


def _preserves_wdl(root_category: str, child_category: str) -> bool:
    root_wdl = _WDL[root_category]
    # Move entries describe the resulting position from the opponent's turn.
    selected_wdl = -_WDL[child_category]
    return selected_wdl >= root_wdl


def main() -> None:
    tree = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    entries = []

    for category_key, category in tree.items():
        if category_key.startswith("_"):
            continue
        for lesson_key, lesson in category.get("lessons", {}).items():
            for index, position in enumerate(lesson.get("positions", [])):
                board = chess.Board(position["fen"])
                if not board.is_valid() or len(board.piece_map()) > 7:
                    continue

                payload, response_hash = _request_tablebase(board.fen())
                stored_uci = position["correct_move_uci"].lower()
                move_evidence = next(
                    (
                        move
                        for move in payload.get("moves", [])
                        if move.get("uci", "").lower() == stored_uci
                    ),
                    None,
                )
                if move_evidence is None:
                    preserves = False
                    child_category = None
                else:
                    child_category = move_evidence.get("category")
                    preserves = _preserves_wdl(
                        payload["category"],
                        child_category,
                    )

                preserving_moves = [
                    {
                        "uci": move.get("uci"),
                        "san": move.get("san"),
                        "category_from_opponent_turn": move.get("category"),
                        "dtz": move.get("dtz"),
                        "precise_dtz": move.get("precise_dtz"),
                    }
                    for move in payload.get("moves", [])
                    if move.get("category") in _WDL
                    and _preserves_wdl(
                        payload["category"],
                        move["category"],
                    )
                ]

                entries.append(
                    {
                        "content_id": f"{category_key}/{lesson_key}",
                        "position_index": index,
                        "fen": board.fen(),
                        "stored_move_uci": stored_uci,
                        "root_category": payload.get("category"),
                        "move_category_from_opponent_turn": child_category,
                        "preserves_wdl": preserves,
                        "dtz": (
                            move_evidence.get("dtz")
                            if move_evidence is not None
                            else None
                        ),
                        "precise_dtz": (
                            move_evidence.get("precise_dtz")
                            if move_evidence is not None
                            else None
                        ),
                        "preserving_moves": preserving_moves,
                        "response_sha256": response_hash,
                    }
                )
                time.sleep(0.05)

    snapshot = {
        "schema_version": 1,
        "source": API_ENDPOINT,
        "source_documentation": (
            "https://github.com/lichess-org/lila-tablebase/blob/main/README.md"
        ),
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "canonical_content_source": (
            "backend/data/coaching/endgame_theory_tree.json"
        ),
        "eligibility": "valid standard-chess positions with seven pieces or fewer",
        "entries": entries,
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(entries)} positions to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
