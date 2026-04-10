"""Canonical, verified opening trap source-of-truth for coaching flows.

Split into two categories:
  1. TRAPS — Lead to checkmate or winning major material (queen/rook)
  2. WARNINGS — Common mistakes/dangers to know about (positional)

The live coach must never label a trap unless the current opening line matches
an exact, legal setup from this registry.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import chess


def _normalize(move: str) -> str:
    return (
        (move or "")
        .replace("+", "")
        .replace("#", "")
        .replace("!", "")
        .replace("?", "")
        .strip()
        .lower()
    )


@dataclass(frozen=True)
class VerifiedOpeningTrap:
    trap_id: str
    name: str
    opening_key: str
    opening_name: str
    variation_name: str
    setup_moves: List[str]       # moves leading up to the trap
    full_line: List[str]         # full line including the payoff
    trap_move: str               # the key move that springs the trap
    explanation: str             # what happens and why
    refutation: str              # how to avoid falling for it
    victim_color: str            # who gets trapped: "white" or "black"
    trap_for: str                # who benefits: "white" or "black"
    difficulty: str              # "beginner", "intermediate", "advanced"
    category: str = "trap"       # "trap" (mate/major material) or "warning" (positional)


# ─── VERIFIED TRAPS (checkmate or +5 material) ──────────────────

VERIFIED_TRAP_REGISTRY: Dict[str, VerifiedOpeningTrap] = {

    # === CHECKMATE TRAPS ===

    "legals_mate": VerifiedOpeningTrap(
        trap_id="legals_mate",
        name="Legal's Mate",
        opening_key="italian_game",
        opening_name="Italian Game",
        variation_name="Giuoco Piano",
        setup_moves=["e4", "e5", "Nf3", "Nc6", "Bc4", "d6", "Nc3", "Bg4", "h3", "Bh5"],
        full_line=["e4", "e5", "Nf3", "Nc6", "Bc4", "d6", "Nc3", "Bg4", "h3", "Bh5", "Nxe5", "Bxd1", "Bxf7+", "Ke7", "Nd5#"],
        trap_move="Nxe5",
        explanation="White sacrifices the queen. If Black takes it, Bxf7+ Ke7 Nd5# is checkmate. The bishop and knights create a perfect mating net.",
        refutation="Black should NOT take the queen. Play dxe5 instead.",
        victim_color="black",
        trap_for="white",
        difficulty="beginner",
        category="trap",
    ),
    "caro_kann_smothered_mate": VerifiedOpeningTrap(
        trap_id="caro_kann_smothered_mate",
        name="Caro-Kann Smothered Mate",
        opening_key="caro_kann",
        opening_name="Caro-Kann Defense",
        variation_name="Two Knights Attack",
        setup_moves=["e4", "c6", "Nc3", "d5", "Nf3", "dxe4", "Nxe4", "Nd7", "Qe2", "Ngf6"],
        full_line=["e4", "c6", "Nc3", "d5", "Nf3", "dxe4", "Nxe4", "Nd7", "Qe2", "Ngf6", "Nd6#"],
        trap_move="Nd6#",
        explanation="Checkmate! The knight on d6 delivers check and Black's own pieces block every escape square. A classic smothered mate.",
        refutation="Black should NOT play Ngf6. Play e6 or g6 first to prevent Nd6.",
        victim_color="black",
        trap_for="white",
        difficulty="beginner",
        category="trap",
    ),
    "philidor_legal_mate_pattern": VerifiedOpeningTrap(
        trap_id="philidor_legal_mate_pattern",
        name="Philidor Legal's Mate",
        opening_key="philidor_defense",
        opening_name="Philidor Defense",
        variation_name="Main Line",
        setup_moves=["e4", "e5", "Nf3", "d6", "Bc4", "Bg4", "Nc3", "h6"],
        full_line=["e4", "e5", "Nf3", "d6", "Bc4", "Bg4", "Nc3", "h6", "Nxe5", "Bxd1", "Bxf7+", "Ke7", "Nd5#"],
        trap_move="Nxe5",
        explanation="Same pattern as Legal's Mate. White sacrifices the queen, then Bxf7+ Ke7 Nd5# is checkmate. Works when Black's bishop takes the queen greedily.",
        refutation="Black should NOT take the queen. Play dxe5 to stay safe.",
        victim_color="black",
        trap_for="white",
        difficulty="beginner",
        category="trap",
    ),
    "blackburne_shilling_mate": VerifiedOpeningTrap(
        trap_id="blackburne_shilling_mate",
        name="Blackburne Shilling Gambit",
        opening_key="italian_game",
        opening_name="Italian Game",
        variation_name="Italian sideline",
        setup_moves=["e4", "e5", "Nf3", "Nc6", "Bc4", "Nd4", "Nxe5", "Qg5", "Nxf7"],
        full_line=["e4", "e5", "Nf3", "Nc6", "Bc4", "Nd4", "Nxe5", "Qg5", "Nxf7", "Qxg2", "Rf1", "Qxe4+", "Be2", "Nf3#"],
        trap_move="Qxg2",
        explanation="Black sacrifices material to open lines to White's king. After Qxg2 Rf1 Qxe4+ Be2 Nf3# is checkmate. White's greed costs the game.",
        refutation="White should NOT play Nxf7. Play d3 or O-O instead of grabbing pawns.",
        victim_color="white",
        trap_for="black",
        difficulty="intermediate",
        category="trap",
    ),
    "budapest_kieninger_mate": VerifiedOpeningTrap(
        trap_id="budapest_kieninger_mate",
        name="Kieninger Trap",
        opening_key="budapest_gambit",
        opening_name="Budapest Gambit",
        variation_name="Budapest Gambit",
        setup_moves=["d4", "Nf6", "c4", "e5", "dxe5", "Ng4", "Bf4", "Nc6", "Nf3", "Bb4+", "Nbd2", "Qe7", "a3", "Ngxe5", "Nxe5", "Nxe5", "e3"],
        full_line=["d4", "Nf6", "c4", "e5", "dxe5", "Ng4", "Bf4", "Nc6", "Nf3", "Bb4+", "Nbd2", "Qe7", "a3", "Ngxe5", "Nxe5", "Nxe5", "e3", "Bxd2+", "Qxd2", "Nd3#"],
        trap_move="Nd3#",
        explanation="Smothered checkmate! Black's knight lands on d3 with check and White's own pieces block all escape. One of the most beautiful traps in chess.",
        refutation="White should avoid the mechanical capture sequence. Be aware of the Nd3 mating square.",
        victim_color="white",
        trap_for="black",
        difficulty="intermediate",
        category="trap",
    ),

    # === MATERIAL-WINNING TRAPS (queen or rook) ===

    "fried_liver_attack": VerifiedOpeningTrap(
        trap_id="fried_liver_attack",
        name="Fried Liver Attack",
        opening_key="italian_game",
        opening_name="Italian Game",
        variation_name="Two Knights Defense",
        setup_moves=["e4", "e5", "Nf3", "Nc6", "Bc4", "Nf6", "Ng5", "d5", "exd5", "Nxd5"],
        full_line=["e4", "e5", "Nf3", "Nc6", "Bc4", "Nf6", "Ng5", "d5", "exd5", "Nxd5", "Nxf7", "Kxf7", "Qf3+", "Ke6", "Nc3"],
        trap_move="Nxf7",
        explanation="White sacrifices a knight on f7 to drag Black's king to e6. The king is completely exposed in the center with no safety. White has a devastating attack.",
        refutation="After Ng5, Black should play Na5 or d5 carefully. Accepting Nxf7 leads to a very dangerous position.",
        victim_color="black",
        trap_for="white",
        difficulty="beginner",
        category="trap",
    ),
    "petrov_fork_trap": VerifiedOpeningTrap(
        trap_id="petrov_fork_trap",
        name="Petrov Fork Trap",
        opening_key="petrov_defense",
        opening_name="Petrov Defense",
        variation_name="Classical Variation",
        setup_moves=["e4", "e5", "Nf3", "Nf6", "Nxe5", "Nxe4"],
        full_line=["e4", "e5", "Nf3", "Nf6", "Nxe5", "Nxe4", "Qe2", "Nf6", "Nc6+", "Be7", "Nxd8", "Kxd8"],
        trap_move="Qe2",
        explanation="White pins Black's knight with Qe2. After the knight retreats, Nc6+ forks king and queen. White wins Black's queen for a knight — devastating.",
        refutation="Black MUST play d6 first (not Nxe4). This is the #1 rule in the Petrov Defense.",
        victim_color="black",
        trap_for="white",
        difficulty="beginner",
        category="trap",
    ),
    "siberian_trap": VerifiedOpeningTrap(
        trap_id="siberian_trap",
        name="Siberian Trap",
        opening_key="sicilian_defense",
        opening_name="Sicilian Defense",
        variation_name="Kan Variation",
        setup_moves=["e4", "c5", "Nf3", "e6", "d4", "cxd4", "Nxd4", "a6", "Nc3", "Qc7"],
        full_line=["e4", "c5", "Nf3", "e6", "d4", "cxd4", "Nxd4", "a6", "Nc3", "Qc7", "Bd3", "Nf6", "O-O", "Bc5", "Nb3", "Ba7", "Kh1", "Ng4", "Qe1", "Qxh2#"],
        trap_move="Qxh2#",
        explanation="Black sacrifices nothing and delivers checkmate on h2. White's king is stuck on h1 with no escape. The bishop on a7 and knight on g4 control all the key squares.",
        refutation="White should not play Kh1 blindly. Watch for the Ng4-Qh2 pattern when the h-pawn has moved.",
        victim_color="white",
        trap_for="black",
        difficulty="intermediate",
        category="trap",
    ),
    "elephant_trap": VerifiedOpeningTrap(
        trap_id="elephant_trap",
        name="Elephant Trap",
        opening_key="queens_gambit",
        opening_name="Queen's Gambit",
        variation_name="Queen's Gambit Declined",
        setup_moves=["d4", "d5", "c4", "e6", "Nc3", "Nf6", "Bg5", "Nbd7", "cxd5", "exd5", "Nxd5"],
        full_line=["d4", "d5", "c4", "e6", "Nc3", "Nf6", "Bg5", "Nbd7", "cxd5", "exd5", "Nxd5", "Nxd5", "Bxd8", "Bb4+", "Qd2", "Bxd2+", "Kxd2", "Kxd8"],
        trap_move="Bb4+",
        explanation="White thinks they won the queen with Bxd8, but Bb4+ is an intermezzo check. After Qd2 Bxd2+ Kxd2, Black takes back the bishop on d8. White lost a knight for nothing.",
        refutation="White should NOT take the queen with Bxd8. It's a tactical illusion.",
        victim_color="white",
        trap_for="black",
        difficulty="beginner",
        category="trap",
    ),
}


# ─── OPENING WARNINGS (positional dangers, not material traps) ───

OPENING_WARNINGS: Dict[str, VerifiedOpeningTrap] = {
    "london_move_order": VerifiedOpeningTrap(
        trap_id="london_move_order",
        name="London Move Order Warning",
        opening_key="london_system",
        opening_name="London System",
        variation_name="London move order",
        setup_moves=["d4", "d5"],
        full_line=["d4", "d5", "e3", "Nf6", "Bd3", "c5", "c3", "Nc6", "Nd2"],
        trap_move="e3",
        explanation="Playing e3 before Bf4 traps the dark-squared bishop behind the pawn chain forever. This is the #1 London System mistake.",
        refutation="ALWAYS play Bf4 before e3. The bishop must get out first.",
        victim_color="white",
        trap_for="white",
        difficulty="beginner",
        category="warning",
    ),
    "french_milner_barry": VerifiedOpeningTrap(
        trap_id="french_milner_barry",
        name="Milner-Barry Gambit Warning",
        opening_key="french_defense",
        opening_name="French Defense",
        variation_name="Advance Variation",
        setup_moves=["e4", "e6", "d4", "d5", "e5", "c5", "c3", "Nc6", "Nf3", "Qb6"],
        full_line=["e4", "e6", "d4", "d5", "e5", "c5", "c3", "Nc6", "Nf3", "Qb6", "Bd3"],
        trap_move="Bd3",
        explanation="White gambits the b2 pawn. If Black takes Qxb2, White gets rapid development and a dangerous attack while Black's queen is stranded.",
        refutation="Black should NOT take b2. Develop with cxd4 instead.",
        victim_color="black",
        trap_for="white",
        difficulty="intermediate",
        category="warning",
    ),
    "ruy_lopez_noah_ark": VerifiedOpeningTrap(
        trap_id="ruy_lopez_noah_ark",
        name="Noah's Ark Trap Warning",
        opening_key="ruy_lopez",
        opening_name="Ruy Lopez",
        variation_name="Morphy Defense",
        setup_moves=["e4", "e5", "Nf3", "Nc6", "Bb5", "a6", "Ba4", "Nf6", "O-O", "d6", "d4", "b5", "Bb3"],
        full_line=["e4", "e5", "Nf3", "Nc6", "Bb5", "a6", "Ba4", "Nf6", "O-O", "d6", "d4", "b5", "Bb3", "Nxd4", "Nxd4", "exd4", "Qxd4", "c5", "Qd3", "c4", "Qxc4", "Be6"],
        trap_move="c5",
        explanation="Black plays c5 and c4 to trap White's bishop on b3. The bishop has no escape squares — a famous centuries-old trap pattern.",
        refutation="White must retreat the bishop early. Don't let the c-pawn net close around it.",
        victim_color="white",
        trap_for="black",
        difficulty="beginner",
        category="warning",
    ),
    "scandinavian_queen_danger": VerifiedOpeningTrap(
        trap_id="scandinavian_queen_danger",
        name="Scandinavian Queen Danger",
        opening_key="scandinavian_defense",
        opening_name="Scandinavian Defense",
        variation_name="Main Line",
        setup_moves=["e4", "d5", "exd5", "Qxd5", "Nc3", "Qa5", "d4", "Nf6", "Nf3", "Bf5"],
        full_line=["e4", "d5", "exd5", "Qxd5", "Nc3", "Qa5", "d4", "Nf6", "Nf3", "Bf5", "Bd2", "c6", "Nd5"],
        trap_move="Nd5",
        explanation="Nd5 attacks the queen and threatens Nxf6+ discovering an attack. Black's queen is overworked and must give up material.",
        refutation="Black should castle quickly and not leave the queen exposed on a5 for too long.",
        victim_color="black",
        trap_for="white",
        difficulty="intermediate",
        category="warning",
    ),
    "caro_kann_pin_warning": VerifiedOpeningTrap(
        trap_id="caro_kann_pin_warning",
        name="Caro-Kann Classical Pin",
        opening_key="caro_kann",
        opening_name="Caro-Kann Defense",
        variation_name="Classical Variation",
        setup_moves=["e4", "c6", "d4", "d5", "Nc3", "dxe4", "Nxe4", "Bf5", "Ng3", "Bg6", "h4", "h6", "Nf3", "Nd7"],
        full_line=["e4", "c6", "d4", "d5", "Nc3", "dxe4", "Nxe4", "Bf5", "Ng3", "Bg6", "h4", "h6", "Nf3", "Nd7", "h5", "Bh7", "Bd3", "Bxd3", "Qxd3"],
        trap_move="h5",
        explanation="White chases Black's bishop to h7 with h5, then trades it off with Bd3. Black loses the bishop pair and White gets a strong position.",
        refutation="Black should consider Bg4 instead of Bg6 to avoid the h4-h5 chase.",
        victim_color="black",
        trap_for="white",
        difficulty="intermediate",
        category="warning",
    ),
}


# ─── COMBINED REGISTRY ────────────────────────────────────────────

ALL_REGISTRY = {**VERIFIED_TRAP_REGISTRY, **OPENING_WARNINGS}


def get_verified_trap_registry() -> Dict[str, VerifiedOpeningTrap]:
    return VERIFIED_TRAP_REGISTRY


def get_all_traps_and_warnings() -> Dict[str, VerifiedOpeningTrap]:
    return ALL_REGISTRY


def get_verified_trap(trap_id: str) -> Optional[VerifiedOpeningTrap]:
    return ALL_REGISTRY.get(trap_id)


def get_verified_traps_for_opening(opening_key: str) -> List[VerifiedOpeningTrap]:
    return [trap for trap in VERIFIED_TRAP_REGISTRY.values() if trap.opening_key == opening_key]


def get_warnings_for_opening(opening_key: str) -> List[VerifiedOpeningTrap]:
    return [trap for trap in OPENING_WARNINGS.values() if trap.opening_key == opening_key]


def get_all_for_opening(opening_key: str) -> List[VerifiedOpeningTrap]:
    return [trap for trap in ALL_REGISTRY.values() if trap.opening_key == opening_key]


def get_verified_trap_by_name(opening_key: str, trap_name: str) -> Optional[VerifiedOpeningTrap]:
    normalized_name = (trap_name or "").strip().lower()
    for trap in get_all_for_opening(opening_key):
        if trap.name.lower() == normalized_name:
            return trap
    return None


def get_applicable_traps_for_moves(opening_key: str, moves: List[str]) -> List[VerifiedOpeningTrap]:
    clean_moves = [_normalize(move) for move in moves if move]
    applicable = []
    for trap in get_all_for_opening(opening_key):
        trap_setup = [_normalize(move) for move in trap.setup_moves]
        if len(clean_moves) > len(trap_setup):
            continue
        if trap_setup[: len(clean_moves)] == clean_moves:
            applicable.append(trap)
    return applicable


def select_preferred_trap(opening_key: str, moves: List[str]) -> Optional[VerifiedOpeningTrap]:
    applicable = get_applicable_traps_for_moves(opening_key, moves)
    if not applicable:
        return None
    # Prefer real traps over warnings
    traps_first = sorted(applicable, key=lambda t: (0 if t.category == "trap" else 1, -len(t.setup_moves)))
    return traps_first[0]


def validate_verified_trap_registry() -> List[str]:
    issues: List[str] = []
    seen_name_opening_pairs = set()

    for trap_id, trap in ALL_REGISTRY.items():
        pair = (trap.opening_key, trap.name.lower())
        if pair in seen_name_opening_pairs:
            issues.append(f"Duplicate trap name within opening: {trap.opening_key}:{trap.name}")
        seen_name_opening_pairs.add(pair)

        board = chess.Board()
        try:
            for move in trap.full_line:
                board.push_san(move)
        except Exception as exc:
            issues.append(f"Illegal trap line for {trap_id}: {exc}")
            continue

        setup_board = chess.Board()
        try:
            for move in trap.setup_moves:
                setup_board.push_san(move)
        except Exception as exc:
            issues.append(f"Illegal trap setup for {trap_id}: {exc}")
            continue

        suffix_moves = [_normalize(move) for move in trap.full_line[len(trap.setup_moves):]]
        if suffix_moves and _normalize(trap.trap_move) not in suffix_moves:
            issues.append(f"Trap move mismatch for {trap_id}")

    return issues
