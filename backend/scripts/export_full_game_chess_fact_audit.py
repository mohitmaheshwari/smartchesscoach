#!/usr/bin/env python3
"""Read-only, privacy-safe exporter for the locked 80-game chess-fact audit.

Run inside the production backend container, one rating band at a time. The
script prints base64-encoded JSON so shells cannot alter Unicode or newlines.
It never writes to MongoDB and never emits source identifiers.
"""

import base64
import hashlib
import io
import json
import os
import re
import sys
from collections import Counter

import chess
import chess.pgn
from pymongo import MongoClient


BANDS = {
    "600-899": (600, 899),
    "900-1199": (900, 1199),
    "1200-1499": (1200, 1499),
    "1500-1999": (1500, 1999),
}
STRATA = ("opening", "endgame", "tactical", "general")
TARGET_LINE_PHASES = ("opening", "middlegame", "endgame")
TARGET_LINE_POSITIONS_PER_BAND = 375
TARGET_LINE_PHASE_MINIMUM = 50
V5_FIELDS = (
    "move_number", "move_san", "best_move_san", "caption", "narrative",
    "caption_facts_primary_reason",
    "caption_facts_principles_violated", "caption_tier", "severity",
    "severity_canonical", "severity_practical", "phase",
    "concept_id", "concept_type", "concept_applied", "rule_name",
    "principle_cue", "principle_id_used", "opening", "opening_name",
    "trap", "coach_line_moves",
    "shape_pattern_id", "shape_pattern_name", "shape_pattern_desc",
    "shape_pattern_targets", "shape_pattern_executing_move",
    "has_teaching_content",
)
TRAP_FIELDS = (
    "description", "difficulty", "full_sprung", "gold_class", "opening_key",
    "result_type", "role", "setter_color", "setup_moves",
    "setup_reached_ply", "sprung_moves", "training_weakness", "trap_line",
    "trap_name", "user_color",
)
FORBIDDEN_KEYS = {
    "_id", "user_id", "game_id", "email", "username", "chess_com_username",
    "chesscom_username", "lichess_username", "profile_id", "date_played",
    "date_played_iso", "imported_at", "analyzed_at", "created_at", "url",
    "source_url", "white_player", "black_player", "white", "black",
    "pgn",
}
EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
URL_RE = re.compile(r"https?://|www\.", re.I)


def threshold(rating):
    if rating < 1000:
        return 150
    if rating < 1400:
        return 75
    if rating < 1800:
        return 50
    return 30


def parse_move(board, token):
    if not token:
        raise ValueError("missing move token")
    text = str(token)
    try:
        move = chess.Move.from_uci(text)
        if move in board.legal_moves:
            return move
    except ValueError:
        pass
    return board.parse_san(text)


def fen_core(fen):
    return " ".join(str(fen).split()[:4])


def replay(pgn_text, move_evaluations):
    parsed = chess.pgn.read_game(io.StringIO(pgn_text or ""))
    if parsed is None:
        raise ValueError("invalid or empty PGN")
    board = parsed.board()
    initial_fen = board.fen()
    moves = []
    positions = []
    for ply, move in enumerate(parsed.mainline_moves(), 1):
        san = board.san(move)
        uci = move.uci()
        actor = "white" if board.turn == chess.WHITE else "black"
        before = board.fen()
        board.push(move)
        moves.append({"ply": ply, "actor": actor, "san": san, "uci": uci})
        positions.append((fen_core(before), uci, fen_core(board.fen())))
    if not moves:
        raise ValueError("PGN has no moves")

    # Stored analyses may contain every ply or only the evaluated player''s
    # turns. Align each record to the canonical PGN instead of assuming the
    # analysis array itself is a complete game trace.
    matched_plies = []
    cursor = 0
    for item in move_evaluations:
        item_board = chess.Board(item["fen_before"])
        item_move = parse_move(item_board, item.get("move_uci") or item.get("move"))
        wanted = (fen_core(item_board.fen()), item_move.uci())
        found = None
        for index in range(cursor, len(positions)):
            if positions[index][:2] == wanted:
                found = index
                break
        if found is None:
            raise ValueError("stored evaluation does not align to PGN")
        if item.get("fen_after") and positions[found][2] != fen_core(item["fen_after"]):
            raise ValueError("stored fen_after does not align to PGN")
        matched_plies.append(found + 1)
        cursor = found + 1
    return initial_fen, moves, matched_plies


def is_user_move(item, user_color):
    board = chess.Board(item["fen_before"])
    return board.turn == (chess.WHITE if user_color == "white" else chess.BLACK)


def phase(item):
    board = chess.Board(item["fen_before"])
    if board.fullmove_number <= 12:
        return "opening"
    queens = sum(len(board.pieces(chess.QUEEN, color)) for color in (chess.WHITE, chess.BLACK))
    nonpawns = sum(
        len(board.pieces(piece, color))
        for piece in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN)
        for color in (chess.WHITE, chess.BLACK)
    )
    pawns = sum(len(board.pieces(chess.PAWN, color)) for color in (chess.WHITE, chess.BLACK))
    if queens == 0 and (nonpawns <= 4 or nonpawns + pawns <= 12):
        return "endgame"
    return "middlegame"


def validate_continuation(item, first_key, pv_key):
    board = chess.Board(item["fen_before"])
    first = item.get(first_key)
    if not first:
        return
    first_move = parse_move(board, first)
    board.push(first_move)
    for index, token in enumerate((item.get(pv_key) or [])[:4]):
        try:
            move = parse_move(board, token)
        except Exception:
            if index == 0 and str(token) in {str(first), first_move.uci()}:
                continue
            raise
        board.push(move)


def normalized_continuation_san(item, first_token, pv_key):
    """Legally replay one stored branch and return continuation SAN only."""
    board = chess.Board(item["fen_before"])
    first_move = parse_move(board, first_token)
    first_san = board.san(first_move)
    board.push(first_move)
    normalized = []
    for index, token in enumerate(item.get(pv_key) or []):
        if index == 0 and str(token) in {
            str(first_token), first_move.uci(), first_san
        }:
            continue
        try:
            move = parse_move(board, token)
        except Exception:
            raise
        normalized.append(board.san(move))
        board.push(move)
        if len(normalized) == 4:
            break
    if len(normalized) < 4 and not board.is_game_over(claim_draw=True):
        raise ValueError("stored continuation ends before four plies")
    return normalized


def target_line_position(item, rating_band):
    """Return the privacy-safe chess evidence needed by the local proof."""
    board = chess.Board(item["fen_before"])
    played_token = item.get("move_uci") or item.get("move")
    best_token = item.get("best_move_uci") or item.get("best_move")
    if not played_token or not best_token:
        raise ValueError("missing played or better move")
    played_move = parse_move(board, played_token)
    played_san = board.san(played_move)
    best_move = parse_move(board, best_token)
    best_san = board.san(best_move)
    played_line = normalized_continuation_san(
        item, played_token, "pv_after_played"
    )
    best_line = normalized_continuation_san(
        item, best_token, "pv_after_best"
    )
    return {
        "rating_band": rating_band,
        "phase": phase(item),
        "fen_before": board.fen(),
        "side_to_move": "white" if board.turn else "black",
        "played_san": played_san,
        "best_move_san": best_san,
        "pv_after_played": played_line,
        "pv_after_best": best_line,
        "cp_loss": int(item.get("cp_loss") or 0),
    }


def target_line_position_signature(position):
    payload = {
        "fen_before": position["fen_before"],
        "played_san": position["played_san"],
        "best_move_san": position["best_move_san"],
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def load_target_line_excluded_signatures():
    """Load content-only exclusions supplied by the local export runner."""
    encoded = os.environ.get("TARGET_LINE_EXCLUDED_SIGNATURES_B64", "")
    if not encoded:
        return set()
    values = json.loads(base64.b64decode(encoded).decode("utf-8"))
    if not isinstance(values, list) or any(
        not isinstance(value, str)
        or not re.fullmatch(r"[0-9a-f]{64}", value)
        for value in values
    ):
        raise ValueError("invalid target-line exclusion payload")
    return set(values)


def select_target_line_candidates(
    candidates,
    *,
    total=TARGET_LINE_POSITIONS_PER_BAND,
    phase_minimum=TARGET_LINE_PHASE_MINIMUM,
):
    """Select a label-blind, phase-covered set with one position per game."""
    selected = []
    selected_games = set()
    selected_signatures = set()

    def add(candidate):
        game_id = candidate["source_game_id"]
        signature = candidate["position_signature"]
        if game_id in selected_games or signature in selected_signatures:
            return False
        selected.append(candidate)
        selected_games.add(game_id)
        selected_signatures.add(signature)
        return True

    for wanted_phase in TARGET_LINE_PHASES:
        for candidate in sorted(
            (
                row
                for row in candidates
                if row["position"]["phase"] == wanted_phase
            ),
            key=lambda row: row["rank"],
        ):
            if add(candidate) and sum(
                row["position"]["phase"] == wanted_phase
                for row in selected
            ) == phase_minimum:
                break
        actual = sum(
            row["position"]["phase"] == wanted_phase
            for row in selected
        )
        if actual != phase_minimum:
            raise ValueError(
                f"thin target-line phase: {wanted_phase}={actual}"
            )

    for candidate in sorted(candidates, key=lambda row: row["rank"]):
        if len(selected) >= total:
            break
        add(candidate)
    if len(selected) != total:
        raise ValueError(
            f"target-line sample shortfall: {len(selected)} of {total}"
        )
    return selected


def export_target_line_population(
    db, games, rating_band, *, excluded_signatures=None
):
    """Print one 375-position, detector-label-blind band packet."""
    candidates = []
    sensitive_values = set()
    rejected = Counter()
    excluded_signatures = set(excluded_signatures or ())
    supplied_matches_excluded = 0
    eligible_phase_games = {
        phase_name: set() for phase_name in TARGET_LINE_PHASES
    }
    projection = {
        "_id": 0,
        "game_id": 1,
        "user_id": 1,
        "stockfish_analysis.move_evaluations": 1,
    }
    query = {
        "game_id": {"$in": list(games)},
        "stockfish_analysis.move_evaluations.0": {"$exists": True},
    }
    for analysis in db.game_analyses.find(query, projection):
        source_game_id = analysis.get("game_id")
        game = games.get(source_game_id)
        if not game:
            continue
        user_color = str(game.get("user_color") or "").lower()
        if user_color not in {"white", "black"}:
            continue
        sensitive_values.update(
            str(value)
            for value in (
                source_game_id,
                analysis.get("user_id"),
                game.get("user_id"),
                game.get("white"),
                game.get("black"),
                game.get("white_player"),
                game.get("black_player"),
            )
            if value
        )
        for item in (
            (analysis.get("stockfish_analysis") or {}).get(
                "move_evaluations"
            )
            or []
        ):
            if not is_user_move(item, user_color):
                continue
            if int(item.get("cp_loss") or 0) < threshold(
                int(game["user_rating"])
            ):
                continue
            try:
                position = target_line_position(item, rating_band)
            except Exception as exc:
                rejected[type(exc).__name__ + ": " + str(exc)] += 1
                continue
            signature = target_line_position_signature(position)
            if signature in excluded_signatures:
                supplied_matches_excluded += 1
                continue
            eligible_phase_games[position["phase"]].add(source_game_id)
            rank = hashlib.sha256(
                (
                    "target-line-population-export-v1|"
                    + signature
                ).encode("ascii")
            ).hexdigest()
            candidates.append({
                "source_game_id": source_game_id,
                "position_signature": signature,
                "rank": rank,
                "position": position,
            })

    selected = select_target_line_candidates(candidates)
    positions = [row["position"] for row in selected]
    signatures = [row["position_signature"] for row in selected]
    packet = {
        "schema_version": "target_line_population_export.v1",
        "generated_on": "2026-09-04",
        "source": "read-only production export of stored Stockfish evidence",
        "rating_band": rating_band,
        "requested_positions": TARGET_LINE_POSITIONS_PER_BAND,
        "selected_positions": len(positions),
        "distinct_source_games": len({
            row["source_game_id"] for row in selected
        }),
        "eligible_phase_source_games": {
            key: len(value)
            for key, value in eligible_phase_games.items()
        },
        "selected_phase_counts": dict(Counter(
            row["phase"] for row in positions
        )),
        "selection_fingerprint_sha256": hashlib.sha256(
            "|".join(signatures).encode("ascii")
        ).hexdigest(),
        "selection": (
            "Detector-label-blind chess-content hash; one position per "
            "source game; at least 50 positions per phase; all supplied "
            "prior-evidence signatures excluded before selection."
        ),
        "excluded_position_signatures_supplied": len(excluded_signatures),
        "excluded_position_matches": supplied_matches_excluded,
        "rejected_incomplete_or_illegal": sum(rejected.values()),
        "rejection_reasons": dict(sorted(rejected.items())),
        "privacy": (
            "No source ids, user ids, names, usernames, emails, dates, URLs, "
            "PGN headers, credentials, captions, cognitive labels, or detector "
            "outputs."
        ),
        "positions": positions,
    }
    text = assert_private(packet, sensitive_values)
    print(base64.b64encode(text.encode("utf-8")).decode("ascii"))


def tactical_candidate(item):
    if int(item.get("cp_loss") or 0) < 300:
        return False
    board = chess.Board(item["fen_before"])
    tokens = [item.get("best_move_uci") or item.get("best_move")]
    tokens.extend(list(item.get("pv_after_best") or [])[:3])
    for token in tokens:
        if not token:
            continue
        try:
            move = parse_move(board, token)
        except Exception:
            continue
        forcing = board.is_capture(move) or move.promotion is not None
        board.push(move)
        if forcing or board.is_check():
            return True
    return False


def classify_stratum(meaningful):
    phases = [phase(item) for item in meaningful]
    if "opening" in phases:
        return "opening"
    if "endgame" in phases:
        return "endgame"
    if any(p == "middlegame" and tactical_candidate(m) for m, p in zip(meaningful, phases)):
        return "tactical"
    return "general"


def content_key(initial_fen, moves):
    body = initial_fen + "|" + " ".join(move["uci"] for move in moves)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def clean_value(value, secrets):
    if isinstance(value, dict):
        return {
            key: clean_value(val, secrets)
            for key, val in value.items()
            if key not in FORBIDDEN_KEYS
        }
    if isinstance(value, list):
        return [clean_value(val, secrets) for val in value]
    if isinstance(value, str):
        text = value
        for secret in secrets:
            if len(secret) >= 3:
                text = re.sub(re.escape(secret), "[redacted]", text, flags=re.I)
        return text
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)


def v5_for_move(rows, item):
    number = item.get("move_number")
    san = item.get("move")
    side = chess.Board(item["fen_before"]).turn
    candidates = [
        row for row in rows
        if row.get("move_number") == number
        and (not san or row.get("move_san") == san)
        and (row.get("is_white") is None or bool(row.get("is_white")) == bool(side))
    ]
    if not candidates:
        candidates = [
            row for row in rows
            if row.get("move_number") == number and (not san or row.get("move_san") == san)
        ]
    if not candidates:
        return None
    row = candidates[0]
    return {key: row.get(key) for key in V5_FIELDS if row.get(key) is not None}


def export_game(candidate, rating_band):
    game = candidate["game"]
    analysis = candidate["analysis"]
    move_evaluations = (analysis.get("stockfish_analysis") or {}).get("move_evaluations") or []
    user_color = str(game.get("user_color") or "").lower()
    rating = int(game["user_rating"])
    cutoff = threshold(rating)
    secrets = {
        str(value)
        for value in (
            candidate["source_game_id"], analysis.get("user_id"), game.get("user_id"),
            game.get("white"), game.get("black"), game.get("white_player"),
            game.get("black_player"),
        )
        if value
    }
    all_user = []
    meaningful = []
    v5_rows = analysis.get("decryption_v5_data") or []
    for item_index, item in enumerate(move_evaluations):
        if not is_user_move(item, user_color):
            continue
        ply = candidate["matched_plies"][item_index]
        compact = {
            "ply": ply,
            "move_number": item.get("move_number"),
            "played_san": item.get("move"),
            "played_uci": item.get("move_uci"),
            "cp_loss": int(item.get("cp_loss") or 0),
            "stored_cognitive_gap": item.get("cognitive_gap"),
            "is_critical": bool(item.get("is_critical")),
        }
        all_user.append(compact)
        if compact["cp_loss"] < cutoff:
            continue
        validate_continuation(item, "move_uci", "pv_after_played")
        validate_continuation(item, "best_move_uci", "pv_after_best")
        detail = {
            **compact,
            "phase": phase(item),
            "fen_before": item.get("fen_before"),
            "fen_after": item.get("fen_after"),
            "best_move_san": item.get("best_move"),
            "best_move_uci": item.get("best_move_uci"),
            "eval_before": item.get("eval_before"),
            "eval_after": item.get("eval_after"),
            "pv_after_played": list(item.get("pv_after_played") or [])[:4],
            "pv_after_best": list(item.get("pv_after_best") or [])[:4],
            "stored_critical_reason": item.get("critical_reason"),
            "stored_gap_confidence": item.get("gap_confidence"),
            "stored_threat": item.get("threat"),
            "stored_mate_info": item.get("mate_info"),
            "current_review": v5_for_move(v5_rows, item),
        }
        meaningful.append(clean_value(detail, secrets))
    opening_deviation = clean_value(analysis.get("opening_deviation") or {}, secrets)
    traps = [
        clean_value({key: row.get(key) for key in TRAP_FIELDS if row.get(key) is not None}, secrets)
        for row in (analysis.get("trap_fires") or [])
    ]
    return {
        "anonymous_game_key": candidate["content_key"],
        "rating_band": rating_band,
        "audit_stratum": candidate["stratum"],
        "user_color": user_color,
        "result": clean_value(game.get("result"), secrets),
        "opening": clean_value(game.get("opening"), secrets),
        "time_control_category": clean_value(game.get("time_control_category"), secrets),
        "initial_fen": candidate["initial_fen"],
        "moves_uci": [move["uci"] for move in candidate["moves"]],
        "moves_san": [move["san"] for move in candidate["moves"]],
        "user_move_count": len(all_user),
        "meaningful_decisions": meaningful,
        "opening_deviation": opening_deviation,
        "trap_fires": traps,
    }


def assert_private(packet, sensitive_values):
    def walk(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key in FORBIDDEN_KEYS:
                    raise ValueError(f"forbidden output key: {key}")
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
    walk(packet)
    text = json.dumps(packet, ensure_ascii=True, sort_keys=True)
    if EMAIL_RE.search(text) or URL_RE.search(text):
        raise ValueError("email or URL pattern in output")
    lowered = text.lower()
    for value in sensitive_values:
        value = str(value)
        if len(value) >= 6 and value.lower() in lowered:
            raise ValueError("source identifier survived sanitization")
    return text


def main(rating_band, mode="full"):
    if rating_band not in BANDS:
        raise SystemExit(f"rating band must be one of: {'', ''.join(BANDS)}")
    low, high = BANDS[rating_band]
    db = MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "chess_coach")]
    games = {
        row.get("game_id"): row
        for row in db.games.find(
            {},
            {
                "_id": 0, "game_id": 1, "user_id": 1, "user_rating": 1,
                "user_color": 1, "result": 1, "opening": 1, "pgn": 1,
                "time_control_category": 1, "white": 1, "black": 1,
                "white_player": 1, "black_player": 1,
            },
        )
        if str(row.get("user_rating") or "").isdigit()
        and low <= int(row["user_rating"]) <= high
    }
    if mode == "target-line-population":
        export_target_line_population(
            db,
            games,
            rating_band,
            excluded_signatures=load_target_line_excluded_signatures(),
        )
        return
    chosen = {stratum: [] for stratum in STRATA}
    counts = Counter()
    sensitive_values = set()
    invalid_replays = Counter()
    query = {
        "game_id": {"$in": list(games)},
        "stockfish_analysis.move_evaluations.0": {"$exists": True},
        "decryption_v5_data.0": {"$exists": True},
    }
    scan_projection = {
        "_id": 0, "game_id": 1, "stockfish_analysis.move_evaluations": 1,
    }
    for analysis in db.game_analyses.find(query, scan_projection):
        source_game_id = analysis.get("game_id")
        game = games.get(source_game_id)
        if not game:
            continue
        user_color = str(game.get("user_color") or "").lower()
        if user_color not in {"white", "black"}:
            continue
        try:
            initial_fen, moves, matched_plies = replay(
                game.get("pgn"),
                (analysis.get("stockfish_analysis") or {}).get("move_evaluations") or [],
            )
        except Exception as exc:
            invalid_replays[type(exc).__name__ + ": " + str(exc)] += 1
            continue
        meaningful = [
            item for item in (analysis.get("stockfish_analysis") or {}).get("move_evaluations") or []
            if is_user_move(item, user_color)
            and int(item.get("cp_loss") or 0) >= threshold(int(game["user_rating"]))
        ]
        if not meaningful:
            continue
        key = content_key(initial_fen, moves)
        stratum = classify_stratum(meaningful)
        candidate = {
            "source_game_id": source_game_id, "game": game,
            "initial_fen": initial_fen, "moves": moves, "content_key": key,
            "stratum": stratum, "matched_plies": matched_plies,
        }
        candidate["rank"] = hashlib.sha256(
            ("full-game-chess-fact-audit-v1|" + key).encode("ascii")
        ).hexdigest()
        counts[stratum] += 1
        chosen[stratum].append(candidate)
        chosen[stratum].sort(key=lambda row: row["rank"])
        # Retain a small reserve because the same public game can exist from
        # both players'' perspectives. The final sample must contain unique
        # chess traces even when their user-colour strata differ.
        del chosen[stratum][25:]

    selected = []
    seen = set()
    for stratum in STRATA:
        for candidate in chosen[stratum]:
            if candidate["content_key"] in seen:
                continue
            selected.append(candidate)
            seen.add(candidate["content_key"])
            if sum(row["stratum"] == stratum for row in selected) == 5:
                break
        if sum(row["stratum"] == stratum for row in selected) != 5:
            raise ValueError(f"thin audit cell: {rating_band}/{stratum}")

    full_projection = {
        "_id": 0, "game_id": 1, "user_id": 1,
        "stockfish_analysis.move_evaluations": 1, "decryption_v5_data": 1,
        "decryption_v5_version": 1,
        "opening_deviation": 1, "trap_fires": 1,
    }
    for candidate in selected:
        analysis = db.game_analyses.find_one(
            {"game_id": candidate["source_game_id"]}, full_projection
        )
        if not analysis:
            raise ValueError("selected analysis disappeared")
        candidate["analysis"] = analysis
        sensitive_values.update(
            str(value) for value in (
                candidate["source_game_id"], analysis.get("user_id"),
                candidate["game"].get("user_id"),
            ) if value
        )

    if mode == "classifier-supplement":
        games_out = []
        for candidate in selected:
            rating = int(candidate["game"]["user_rating"])
            user_color = str(candidate["game"].get("user_color") or "").lower()
            moves = (candidate["analysis"].get("stockfish_analysis") or {}).get("move_evaluations") or []
            decisions = []
            for index, item in enumerate(moves):
                if (
                    is_user_move(item, user_color)
                    and int(item.get("cp_loss") or 0) >= threshold(rating)
                ):
                    decisions.append({
                        "ply": candidate["matched_plies"][index],
                        "evaluation": item.get("evaluation"),
                        "eval_swing": item.get("eval_swing"),
                        "is_turning_point": item.get("is_turning_point"),
                        "is_best": item.get("is_best"),
                        "is_brilliant": item.get("is_brilliant"),
                        "is_sacrifice": item.get("is_sacrifice"),
                    })
            games_out.append({
                "anonymous_game_key": candidate["content_key"],
                "decryption_v5_version": candidate["analysis"].get(
                    "decryption_v5_version"
                ),
                "decisions": decisions,
            })
        supplement = {
            "schema_version": "full_game_chess_fact_classifier_inputs.v1",
            "generated_on": "2026-09-03",
            "rating_band": rating_band,
            "games": games_out,
        }
        text = assert_private(supplement, sensitive_values)
        print(base64.b64encode(text.encode("utf-8")).decode("ascii"))
        return
    exported = [export_game(candidate, rating_band) for candidate in selected]
    packet = {
        "schema_version": "full_game_chess_fact_audit.v1",
        "generated_on": "2026-09-03",
        "source": "read-only production export of stored Stockfish evidence",
        "rating_band": rating_band,
        "meaningful_cp_loss_rule": "150cp below 1000; 75cp at 1000-1399; 50cp at 1400-1799; 30cp at 1800+",
        "eligible_cell_counts": {stratum: counts[stratum] for stratum in STRATA},
        "selected_cell_counts": dict(Counter(row["audit_stratum"] for row in exported)),
        "rejected_unreplayable_games": sum(invalid_replays.values()),
        "replay_rejection_reasons": dict(sorted(invalid_replays.items())),
        "privacy": "No source ids, user ids, names, usernames, emails, dates, URLs, PGN headers, or credentials.",
        "games": exported,
    }
    text = assert_private(packet, sensitive_values)
    print(base64.b64encode(text.encode("utf-8")).decode("ascii"))


if __name__ == "__main__":
    main(
        sys.argv[1] if len(sys.argv) > 1 else "",
        sys.argv[2] if len(sys.argv) > 2 else "full",
    )
