"""Canonical, verified opening trap source-of-truth for coaching flows.

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
    setup_moves: List[str]
    full_line: List[str]
    trap_move: str
    explanation: str
    refutation: str
    victim_color: str
    trap_for: str
    difficulty: str


VERIFIED_TRAP_REGISTRY: Dict[str, VerifiedOpeningTrap] = {
    "fried_liver_attack": VerifiedOpeningTrap(
        trap_id="fried_liver_attack",
        name="Fried Liver Attack",
        opening_key="italian_game",
        opening_name="Italian Game",
        variation_name="Two Knights Defense",
        setup_moves=["e4", "e5", "Nf3", "Nc6", "Bc4", "Nf6", "Ng5", "d5", "exd5", "Nxd5"],
        full_line=["e4", "e5", "Nf3", "Nc6", "Bc4", "Nf6", "Ng5", "d5", "exd5", "Nxd5", "Nxf7"],
        trap_move="Nxf7",
        explanation="White sacrifices the knight on f7 to drag Black's king into the open. If Black accepts, checks and tempo moves follow immediately.",
        refutation="Black should know the defensive resources after Ng5 and be ready for sharp tactical play instead of drifting into the trap blindly.",
        victim_color="black",
        trap_for="white",
        difficulty="beginner",
    ),
    "legals_mate": VerifiedOpeningTrap(
        trap_id="legals_mate",
        name="Legal's Mate",
        opening_key="italian_game",
        opening_name="Italian Game",
        variation_name="Giuoco Piano",
        setup_moves=["e4", "e5", "Nf3", "Nc6", "Bc4", "d6", "Nc3", "Bg4", "h3", "Bh5"],
        full_line=["e4", "e5", "Nf3", "Nc6", "Bc4", "d6", "Nc3", "Bg4", "h3", "Bh5", "Nxe5"],
        trap_move="Nxe5",
        explanation="White sacrifices the queen only because the king and bishop coordination create a forced mating net. It works only if the tactical details are exact.",
        refutation="Black should avoid greed and choose a defensive move instead of automatically taking the queen.",
        victim_color="black",
        trap_for="white",
        difficulty="beginner",
    ),
    "blackburne_shilling_gambit": VerifiedOpeningTrap(
        trap_id="blackburne_shilling_gambit",
        name="Blackburne Shilling Gambit",
        opening_key="italian_game",
        opening_name="Italian Game",
        variation_name="Italian sideline",
        setup_moves=["e4", "e5", "Nf3", "Nc6", "Bc4", "Nd4"],
        full_line=["e4", "e5", "Nf3", "Nc6", "Bc4", "Nd4", "Nxe5"],
        trap_move="Nxe5",
        explanation="White grabs the e5 pawn too quickly and Black gets immediate tactical counterplay against the queen and f2.",
        refutation="White should not auto-grab on e5; developing or kicking the knight away is safer.",
        victim_color="white",
        trap_for="black",
        difficulty="beginner",
    ),
    "traxler_counterattack": VerifiedOpeningTrap(
        trap_id="traxler_counterattack",
        name="Traxler Counterattack",
        opening_key="italian_game",
        opening_name="Italian Game",
        variation_name="Two Knights Defense",
        setup_moves=["e4", "e5", "Nf3", "Nc6", "Bc4", "Nf6", "Ng5"],
        full_line=["e4", "e5", "Nf3", "Nc6", "Bc4", "Nf6", "Ng5", "Bc5", "Nxf7", "Bxf2+"],
        trap_move="Bxf2+",
        explanation="Black ignores the rook and counterattacks the king immediately. The point is activity and king exposure, not material count.",
        refutation="White should avoid blindly grabbing on f7 unless the full tactical line is known.",
        victim_color="white",
        trap_for="black",
        difficulty="advanced",
    ),
    "jerome_gambit": VerifiedOpeningTrap(
        trap_id="jerome_gambit",
        name="Jerome Gambit",
        opening_key="italian_game",
        opening_name="Italian Game",
        variation_name="Giuoco Piano",
        setup_moves=["e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5", "Bxf7+", "Kxf7"],
        full_line=["e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5", "Bxf7+", "Kxf7", "Nxe5+"],
        trap_move="Nxe5+",
        explanation="White throws both minor pieces at the king to force chaos. This is only a real weapon if the follow-up checks are accurate.",
        refutation="Black should stay calm and defend precisely rather than grabbing material without calculation.",
        victim_color="black",
        trap_for="white",
        difficulty="advanced",
    ),
    "siberian_trap": VerifiedOpeningTrap(
        trap_id="siberian_trap",
        name="Siberian Trap",
        opening_key="sicilian_defense",
        opening_name="Sicilian Defense",
        variation_name="Open Sicilian ...Bb4 line",
        setup_moves=["e4", "c5", "Nf3", "e6", "d4", "cxd4", "Nxd4", "Nf6", "Nc3", "Bb4"],
        full_line=["e4", "c5", "Nf3", "e6", "d4", "cxd4", "Nxd4", "Nf6", "Nc3", "Bb4", "e5", "Qa5", "exf6", "Bxc3+", "Bd2", "Bxd2+", "Qxd2", "Qxd2+"],
        trap_move="Qa5",
        explanation="After White overextends with e5 and then grabs on f6, Black's queen and bishop combine to win the queen by force. This is a queen win, not a casual queen trade.",
        refutation="White should avoid the loose move order with e5 and exf6; develop more carefully instead of drifting into the tactical sequence.",
        victim_color="white",
        trap_for="black",
        difficulty="intermediate",
    ),
    "magnus_smith_trap": VerifiedOpeningTrap(
        trap_id="magnus_smith_trap",
        name="Magnus Smith Trap",
        opening_key="sicilian_defense",
        opening_name="Sicilian Defense",
        variation_name="Dragon-style tactical line",
        setup_moves=["e4", "c5", "Nf3", "d6", "d4", "cxd4", "Nxd4", "Nf6", "Nc3", "g6", "Bc4", "Bg7"],
        full_line=["e4", "c5", "Nf3", "d6", "d4", "cxd4", "Nxd4", "Nf6", "Nc3", "g6", "Bc4", "Bg7", "Nxc6", "bxc6"],
        trap_move="bxc6",
        explanation="The tactical point is that Black's recapture allows White to attack before Black's king is coordinated. The danger is a kingside blow, not just a pawn structure issue.",
        refutation="Black should know the tactical risk before recapturing mechanically in Dragon-style positions.",
        victim_color="black",
        trap_for="white",
        difficulty="intermediate",
    ),
    "elephant_trap": VerifiedOpeningTrap(
        trap_id="elephant_trap",
        name="Elephant Trap",
        opening_key="queens_gambit",
        opening_name="Queen's Gambit",
        variation_name="Queen's Gambit Declined",
        setup_moves=["d4", "d5", "c4", "e6", "Nc3", "Nf6", "Bg5", "Nbd7", "cxd5", "exd5", "Nxd5", "Nxd5", "Bxd8"],
        full_line=["d4", "d5", "c4", "e6", "Nc3", "Nf6", "Bg5", "Nbd7", "cxd5", "exd5", "Nxd5", "Nxd5", "Bxd8", "Bb4+"],
        trap_move="Bb4+",
        explanation="Black uses the intermezzo check to recover more than enough material. White's apparent queen win is tactically false.",
        refutation="White should not auto-snatch the queen; complete development or recapture more carefully instead.",
        victim_color="white",
        trap_for="black",
        difficulty="beginner",
    ),
}


def get_verified_trap_registry() -> Dict[str, VerifiedOpeningTrap]:
    return VERIFIED_TRAP_REGISTRY


def get_verified_trap(trap_id: str) -> Optional[VerifiedOpeningTrap]:
    return VERIFIED_TRAP_REGISTRY.get(trap_id)


def get_verified_traps_for_opening(opening_key: str) -> List[VerifiedOpeningTrap]:
    return [trap for trap in VERIFIED_TRAP_REGISTRY.values() if trap.opening_key == opening_key]


def get_verified_trap_by_name(opening_key: str, trap_name: str) -> Optional[VerifiedOpeningTrap]:
    normalized_name = (trap_name or "").strip().lower()
    for trap in get_verified_traps_for_opening(opening_key):
        if trap.name.lower() == normalized_name:
            return trap
    return None


def get_applicable_traps_for_moves(opening_key: str, moves: List[str]) -> List[VerifiedOpeningTrap]:
    clean_moves = [_normalize(move) for move in moves if move]
    applicable = []
    for trap in get_verified_traps_for_opening(opening_key):
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
    return sorted(applicable, key=lambda trap: (len(trap.setup_moves), len(trap.full_line)), reverse=True)[0]


def validate_verified_trap_registry() -> List[str]:
    issues: List[str] = []
    seen_name_opening_pairs = set()

    for trap_id, trap in VERIFIED_TRAP_REGISTRY.items():
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