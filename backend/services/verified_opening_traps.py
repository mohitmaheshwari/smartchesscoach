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

    # ─── FRENCH DEFENSE TRAPS ─────────────────────────────────

    "french_winawer_poisoned_pawn": VerifiedOpeningTrap(
        trap_id="french_winawer_poisoned_pawn",
        name="Winawer Poisoned Pawn",
        opening_key="french_defense",
        opening_name="French Defense",
        variation_name="Winawer Variation",
        setup_moves=["e4", "e6", "d4", "d5", "Nc3", "Bb4", "e5", "c5", "a3", "Bxc3+", "bxc3", "Ne7"],
        full_line=["e4", "e6", "d4", "d5", "Nc3", "Bb4", "e5", "c5", "a3", "Bxc3+", "bxc3", "Ne7", "Qg4", "Qc7"],
        trap_move="Qg4",
        explanation="White attacks g7 with the queen. If Black defends with Kf8, White has strong initiative. The position is sharp and tactical.",
        refutation="Black should play Qc7 to attack the e5 pawn and avoid weakening the kingside. The g7 pawn is poisoned for White.",
        victim_color="black",
        trap_for="white",
        difficulty="intermediate",
    ),
    "french_advance_milner_barry": VerifiedOpeningTrap(
        trap_id="french_advance_milner_barry",
        name="Milner-Barry Gambit Trap",
        opening_key="french_defense",
        opening_name="French Defense",
        variation_name="Advance Variation",
        setup_moves=["e4", "e6", "d4", "d5", "e5", "c5", "c3", "Nc6", "Nf3", "Qb6"],
        full_line=["e4", "e6", "d4", "d5", "e5", "c5", "c3", "Nc6", "Nf3", "Qb6", "Bd3"],
        trap_move="Bd3",
        explanation="White gambits the b2 pawn. If Black takes Qxb2, White plays Nbd2 with rapid development and a dangerous attack. Black's queen is out of play.",
        refutation="Black should not take b2. Develop instead with cxd4 or Nh6.",
        victim_color="black",
        trap_for="white",
        difficulty="intermediate",
    ),

    # ─── CARO-KANN TRAPS ─────────────────────────────────────

    "caro_kann_smothered_mate": VerifiedOpeningTrap(
        trap_id="caro_kann_smothered_mate",
        name="Caro-Kann Smothered Mate",
        opening_key="caro_kann",
        opening_name="Caro-Kann Defense",
        variation_name="Two Knights Attack",
        setup_moves=["e4", "c6", "Nc3", "d5", "Nf3", "dxe4", "Nxe4", "Nd7", "Qe2", "Ngf6"],
        full_line=["e4", "c6", "Nc3", "d5", "Nf3", "dxe4", "Nxe4", "Nd7", "Qe2", "Ngf6", "Nd6#"],
        trap_move="Nd6#",
        explanation="White plays Nd6 checkmate. The knight is protected by the queen and Black's own pieces block all escape squares. A classic smothered mate pattern.",
        refutation="Black should develop differently — Ngf6 allows the smothered mate. Play e6 or g6 first.",
        victim_color="black",
        trap_for="white",
        difficulty="beginner",
    ),
    "caro_kann_classical_pin": VerifiedOpeningTrap(
        trap_id="caro_kann_classical_pin",
        name="Classical Variation Pin Trap",
        opening_key="caro_kann",
        opening_name="Caro-Kann Defense",
        variation_name="Classical Variation",
        setup_moves=["e4", "c6", "d4", "d5", "Nc3", "dxe4", "Nxe4", "Bf5", "Ng3", "Bg6", "h4", "h6", "Nf3", "Nd7"],
        full_line=["e4", "c6", "d4", "d5", "Nc3", "dxe4", "Nxe4", "Bf5", "Ng3", "Bg6", "h4", "h6", "Nf3", "Nd7", "h5", "Bh7", "Bd3", "Bxd3", "Qxd3"],
        trap_move="h5",
        explanation="White chases the bishop to h7 then trades it off with Bd3. Black loses the bishop pair and White gets a strong center with open lines.",
        refutation="Black should avoid the passive Bg6 line. Consider Bg4 instead to pin the knight.",
        victim_color="black",
        trap_for="white",
        difficulty="intermediate",
    ),

    # ─── RUY LOPEZ TRAPS ─────────────────────────────────────

    "ruy_lopez_noah_ark": VerifiedOpeningTrap(
        trap_id="ruy_lopez_noah_ark",
        name="Noah's Ark Trap",
        opening_key="ruy_lopez",
        opening_name="Ruy Lopez",
        variation_name="Morphy Defense",
        setup_moves=["e4", "e5", "Nf3", "Nc6", "Bb5", "a6", "Ba4", "Nf6", "O-O", "d6", "d4", "b5", "Bb3", "Nxd4", "Nxd4", "exd4"],
        full_line=["e4", "e5", "Nf3", "Nc6", "Bb5", "a6", "Ba4", "Nf6", "O-O", "d6", "d4", "b5", "Bb3", "Nxd4", "Nxd4", "exd4", "Qxd4", "c5"],
        trap_move="c5",
        explanation="Black plays c5 chasing the queen, followed by c4 trapping White's bishop on b3. The bishop has no escape — a centuries-old trap.",
        refutation="White should be careful with the bishop placement. Retreat with Bd5 before the pawn net closes.",
        victim_color="white",
        trap_for="black",
        difficulty="beginner",
    ),
    "ruy_lopez_fishing_pole": VerifiedOpeningTrap(
        trap_id="ruy_lopez_fishing_pole",
        name="Fishing Pole Trap",
        opening_key="ruy_lopez",
        opening_name="Ruy Lopez",
        variation_name="Berlin Defense",
        setup_moves=["e4", "e5", "Nf3", "Nc6", "Bb5", "Nf6", "O-O", "Ng4", "h3", "h5"],
        full_line=["e4", "e5", "Nf3", "Nc6", "Bb5", "Nf6", "O-O", "Ng4", "h3", "h5"],
        trap_move="h5",
        explanation="Black sacrifices the knight for a devastating attack. If White takes hxg4 hxg4, the h-file opens and Black's rook crashes through to White's king.",
        refutation="White should not take the knight with hxg4. Play d4 instead to open the center and ignore the knight.",
        victim_color="white",
        trap_for="black",
        difficulty="intermediate",
    ),

    # ─── SCOTCH GAME TRAPS ────────────────────────────────────

    "scotch_kopec_trap": VerifiedOpeningTrap(
        trap_id="scotch_kopec_trap",
        name="Scotch Gambit Knight Trap",
        opening_key="scotch_game",
        opening_name="Scotch Game",
        variation_name="Scotch Gambit",
        setup_moves=["e4", "e5", "Nf3", "Nc6", "d4", "exd4", "Bc4", "Nf6", "e5", "d5"],
        full_line=["e4", "e5", "Nf3", "Nc6", "d4", "exd4", "Bc4", "Nf6", "e5", "d5", "Bb5", "Ne4"],
        trap_move="Bb5",
        explanation="White pins the knight on c6 and attacks d5. Black's center collapses and the knight on f6 must retreat. White gets a powerful initiative.",
        refutation="Black should play d5 before Nf6 to challenge the center immediately.",
        victim_color="black",
        trap_for="white",
        difficulty="intermediate",
    ),

    # ─── LONDON SYSTEM TRAPS ─────────────────────────────────

    "london_oh_no_queen": VerifiedOpeningTrap(
        trap_id="london_oh_no_queen",
        name="London Queen Trap",
        opening_key="london_system",
        opening_name="London System",
        variation_name="London sideline",
        setup_moves=["d4", "d5", "Bf4", "Nf6", "e3", "c5", "c3", "Qb6", "Qb3"],
        full_line=["d4", "d5", "Bf4", "Nf6", "e3", "c5", "c3", "Qb6", "Qb3", "c4", "Qc2"],
        trap_move="c4",
        explanation="Black pushes c4 attacking White's queen. If White plays Qc2, Black has gained space and tempo. But the real trap is if White tries Qxb6 axb6 — Black gets the open a-file and active play.",
        refutation="White should not exchange queens. Play Qc2 and regroup, but Black already has good play.",
        victim_color="white",
        trap_for="black",
        difficulty="beginner",
    ),
    "london_e3_before_bf4": VerifiedOpeningTrap(
        trap_id="london_e3_before_bf4",
        name="London Move Order Trap",
        opening_key="london_system",
        opening_name="London System",
        variation_name="London move order",
        setup_moves=["d4", "d5", "e3", "Nf6", "Bd3", "c5", "c3"],
        full_line=["d4", "d5", "e3", "Nf6", "Bd3", "c5", "c3", "Nc6", "Nd2"],
        trap_move="Nd2",
        explanation="If White plays e3 before Bf4, the dark-squared bishop gets trapped behind the pawn chain forever. This is the most common London mistake — always play Bf4 BEFORE e3.",
        refutation="Always develop Bf4 before playing e3. The correct move order is d4, Bf4, then e3.",
        victim_color="white",
        trap_for="white",
        difficulty="beginner",
    ),

    # ─── KING'S INDIAN TRAPS ─────────────────────────────────

    "kings_indian_bayonet_trap": VerifiedOpeningTrap(
        trap_id="kings_indian_bayonet_trap",
        name="Bayonet Attack Pawn Trap",
        opening_key="kings_indian_defense",
        opening_name="King's Indian Defense",
        variation_name="Classical Variation",
        setup_moves=["d4", "Nf6", "c4", "g6", "Nc3", "Bg7", "e4", "d6", "Nf3", "O-O", "Be2", "e5", "d5", "Nh5"],
        full_line=["d4", "Nf6", "c4", "g6", "Nc3", "Bg7", "e4", "d6", "Nf3", "O-O", "Be2", "e5", "d5", "Nh5", "g3"],
        trap_move="g3",
        explanation="White plays g3 to stop Nf4. But this weakens the dark squares around the king. Black can exploit with f5-f4 and a kingside attack.",
        refutation="Black should continue with f5 and f4 to blast open the kingside. White's weakened dark squares are the target.",
        victim_color="white",
        trap_for="black",
        difficulty="advanced",
    ),

    # ─── PETROV DEFENSE TRAPS ─────────────────────────────────

    "petrov_nxe4_trap": VerifiedOpeningTrap(
        trap_id="petrov_nxe4_trap",
        name="Petrov Nxe4 Trap",
        opening_key="petrov_defense",
        opening_name="Petrov Defense",
        variation_name="Classical Variation",
        setup_moves=["e4", "e5", "Nf3", "Nf6", "Nxe5", "Nxe4"],
        full_line=["e4", "e5", "Nf3", "Nf6", "Nxe5", "Nxe4", "Qe2", "Nf6", "Nc6+"],
        trap_move="Qe2",
        explanation="If Black takes e4 immediately instead of playing d6 first, White plays Qe2 pinning the knight. After Nf6, Nc6+ forks the king and queen.",
        refutation="Black MUST play d6 first before taking on e4. This is the most important rule in the Petrov.",
        victim_color="black",
        trap_for="white",
        difficulty="beginner",
    ),

    # ─── SCANDINAVIAN TRAPS ──────────────────────────────────

    "scandinavian_qh5_trap": VerifiedOpeningTrap(
        trap_id="scandinavian_qh5_trap",
        name="Scandinavian Queen Trap",
        opening_key="scandinavian_defense",
        opening_name="Scandinavian Defense",
        variation_name="Main Line",
        setup_moves=["e4", "d5", "exd5", "Qxd5", "Nc3", "Qa5", "d4", "Nf6", "Nf3", "Bf5"],
        full_line=["e4", "d5", "exd5", "Qxd5", "Nc3", "Qa5", "d4", "Nf6", "Nf3", "Bf5", "Bd2", "c6", "Nd5"],
        trap_move="Nd5",
        explanation="White plays Nd5 attacking Black's queen and threatening Nxf6+ with a discovered attack on the queen. Black loses material.",
        refutation="Black should not leave the queen on a5 for too long. Castle quickly or play e6 to block Nd5.",
        victim_color="black",
        trap_for="white",
        difficulty="intermediate",
    ),

    # ─── PHILIDOR DEFENSE TRAPS ──────────────────────────────

    "philidor_legal_mate_pattern": VerifiedOpeningTrap(
        trap_id="philidor_legal_mate_pattern",
        name="Philidor Legal's Mate Pattern",
        opening_key="philidor_defense",
        opening_name="Philidor Defense",
        variation_name="Main Line",
        setup_moves=["e4", "e5", "Nf3", "d6", "Bc4", "Bg4", "Nc3", "h6"],
        full_line=["e4", "e5", "Nf3", "d6", "Bc4", "Bg4", "Nc3", "h6", "Nxe5", "Bxd1", "Bxf7+", "Ke7", "Nd5#"],
        trap_move="Nxe5",
        explanation="White sacrifices the queen with Nxe5. If Black takes Bxd1, then Bxf7+ Ke7 Nd5# is checkmate. The bishop and knights coordinate perfectly.",
        refutation="Black should NOT take the queen. Play dxe5 instead to avoid the mating pattern.",
        victim_color="black",
        trap_for="white",
        difficulty="beginner",
    ),

    # ─── VIENNA GAME TRAPS ───────────────────────────────────

    "vienna_frankenstein_dracula": VerifiedOpeningTrap(
        trap_id="vienna_frankenstein_dracula",
        name="Frankenstein-Dracula Variation",
        opening_key="vienna_game",
        opening_name="Vienna Game",
        variation_name="Vienna Gambit",
        setup_moves=["e4", "e5", "Nc3", "Nf6", "Bc4", "Nxe4"],
        full_line=["e4", "e5", "Nc3", "Nf6", "Bc4", "Nxe4", "Qh5", "Nd6", "Bb3", "Nc6", "Nb5"],
        trap_move="Qh5",
        explanation="White attacks f7 with Qh5. Black must find precise moves or lose immediately. Nd6 is forced, then the position becomes extremely sharp.",
        refutation="Black must play Nd6 (not d6 or Be7). Then Nc6 defends and the position is playable but sharp.",
        victim_color="black",
        trap_for="white",
        difficulty="advanced",
    ),

    # ─── QUEEN'S GAMBIT TRAPS ────────────────────────────────

    "qgd_lasker_trap": VerifiedOpeningTrap(
        trap_id="qgd_lasker_trap",
        name="Lasker Trap",
        opening_key="queens_gambit",
        opening_name="Queen's Gambit",
        variation_name="Queen's Gambit Accepted",
        setup_moves=["d4", "d5", "c4", "dxc4", "e3", "b5", "a4", "c6", "axb5", "cxb5"],
        full_line=["d4", "d5", "c4", "dxc4", "e3", "b5", "a4", "c6", "axb5", "cxb5", "Qf3"],
        trap_move="Qf3",
        explanation="White attacks the rook on a8 with Qf3. Black's b5 pawn is overextended and the queenside collapses.",
        refutation="Black should not try to hold the c4 pawn with b5. Return the pawn and develop instead.",
        victim_color="black",
        trap_for="white",
        difficulty="beginner",
    ),

    # ─── SICILIAN NAJDORF TRAPS ──────────────────────────────

    "najdorf_poisoned_pawn": VerifiedOpeningTrap(
        trap_id="najdorf_poisoned_pawn",
        name="Najdorf Poisoned Pawn",
        opening_key="sicilian_najdorf",
        opening_name="Sicilian Najdorf",
        variation_name="Poisoned Pawn Variation",
        setup_moves=["e4", "c5", "Nf3", "d6", "d4", "cxd4", "Nxd4", "Nf6", "Nc3", "a6", "Bg5", "e6", "f4", "Qb6"],
        full_line=["e4", "c5", "Nf3", "d6", "d4", "cxd4", "Nxd4", "Nf6", "Nc3", "a6", "Bg5", "e6", "f4", "Qb6", "Qd2", "Qxb2"],
        trap_move="Qxb2",
        explanation="Black grabs the poisoned b2 pawn. This is one of the most famous lines in chess — extremely sharp. White gets a lead in development and attacking chances.",
        refutation="Both sides need precise knowledge. The pawn is not truly free — White gets compensation through piece activity and king safety advantages.",
        victim_color="black",
        trap_for="white",
        difficulty="advanced",
    ),

    # ─── SLAV DEFENSE TRAPS ──────────────────────────────────

    "slav_geller_gambit": VerifiedOpeningTrap(
        trap_id="slav_geller_gambit",
        name="Slav Geller Gambit Trap",
        opening_key="slav_defense",
        opening_name="Slav Defense",
        variation_name="Exchange Variation",
        setup_moves=["d4", "d5", "c4", "c6", "Nf3", "Nf6", "Nc3", "dxc4", "a4", "Bf5", "e3", "e6"],
        full_line=["d4", "d5", "c4", "c6", "Nf3", "Nf6", "Nc3", "dxc4", "a4", "Bf5", "e3", "e6", "Bxc4", "Bb4", "O-O", "O-O", "Qe2"],
        trap_move="Bxc4",
        explanation="White recaptures the pawn and develops rapidly. The position looks calm but White has more space and better piece coordination. Black's bishop on f5 can become a target.",
        refutation="Black should be careful not to lose time. Complete development quickly and maintain the bishop pair.",
        victim_color="black",
        trap_for="white",
        difficulty="intermediate",
    ),

    # ─── DUTCH DEFENSE TRAPS ─────────────────────────────────

    "dutch_staunton_gambit": VerifiedOpeningTrap(
        trap_id="dutch_staunton_gambit",
        name="Staunton Gambit Trap",
        opening_key="dutch_defense",
        opening_name="Dutch Defense",
        variation_name="Staunton Gambit",
        setup_moves=["d4", "f5", "e4", "fxe4", "Nc3", "Nf6"],
        full_line=["d4", "f5", "e4", "fxe4", "Nc3", "Nf6", "Bg5", "e6", "Nxe4"],
        trap_move="Bg5",
        explanation="White pins the knight to the queen. If Black is not careful, White recovers the pawn with a better position. The pin creates immediate pressure.",
        refutation="Black should play d5 or g6 to develop naturally and not get caught in the pin.",
        victim_color="black",
        trap_for="white",
        difficulty="beginner",
    ),

    # ─── GRUNFELD TRAPS ──────────────────────────────────────

    "grunfeld_exchange_trap": VerifiedOpeningTrap(
        trap_id="grunfeld_exchange_trap",
        name="Grunfeld Exchange Center Trap",
        opening_key="grunfeld_defense",
        opening_name="Grunfeld Defense",
        variation_name="Exchange Variation",
        setup_moves=["d4", "Nf6", "c4", "g6", "Nc3", "d5", "cxd5", "Nxd5", "e4", "Nxc3", "bxc3", "Bg7"],
        full_line=["d4", "Nf6", "c4", "g6", "Nc3", "d5", "cxd5", "Nxd5", "e4", "Nxc3", "bxc3", "Bg7", "Bc4", "O-O", "Ne2", "c5"],
        trap_move="Bc4",
        explanation="White builds a massive center with e4 and Bc4. It looks overwhelming but this is exactly what the Grunfeld wants — Black will attack and destroy the center with c5 and Bg7 pressure.",
        refutation="Black should not panic. Castle, play c5, and the center will collapse. The Grunfeld bishop on g7 is a monster.",
        victim_color="white",
        trap_for="black",
        difficulty="intermediate",
    ),

    # ─── BENONI DEFENSE TRAPS ────────────────────────────────

    "benoni_taimanov_attack": VerifiedOpeningTrap(
        trap_id="benoni_taimanov_attack",
        name="Taimanov Attack Trap",
        opening_key="benoni_defense",
        opening_name="Benoni Defense",
        variation_name="Modern Benoni",
        setup_moves=["d4", "Nf6", "c4", "c5", "d5", "e6", "Nc3", "exd5", "cxd5", "d6", "e4", "g6", "f4"],
        full_line=["d4", "Nf6", "c4", "c5", "d5", "e6", "Nc3", "exd5", "cxd5", "d6", "e4", "g6", "f4", "Bg7", "e5"],
        trap_move="e5",
        explanation="White's f4-e5 push blows open the center. If Black is not prepared, the pawn avalanche creates overwhelming pressure. The d6 pawn becomes a target.",
        refutation="Black must be ready for e5. Play Nfd7 to support d6 and prepare counterplay on the queenside with b5.",
        victim_color="black",
        trap_for="white",
        difficulty="advanced",
    ),

    # ─── NIMZO-INDIAN TRAPS ──────────────────────────────────

    "nimzo_hubner_trap": VerifiedOpeningTrap(
        trap_id="nimzo_hubner_trap",
        name="Nimzo-Indian Pin Trap",
        opening_key="nimzo_indian",
        opening_name="Nimzo-Indian Defense",
        variation_name="Classical Variation",
        setup_moves=["d4", "Nf6", "c4", "e6", "Nc3", "Bb4", "Qc2", "d5", "cxd5", "exd5"],
        full_line=["d4", "Nf6", "c4", "e6", "Nc3", "Bb4", "Qc2", "d5", "cxd5", "exd5", "Bg5", "c5"],
        trap_move="Bg5",
        explanation="White pins the knight to the queen. Combined with the pressure on d5, Black must be careful not to lose a pawn. The position requires precise play.",
        refutation="Black should play c5 immediately to counter in the center and challenge White's pin with h6 if needed.",
        victim_color="black",
        trap_for="white",
        difficulty="intermediate",
    ),

    # ─── BUDAPEST GAMBIT TRAPS ───────────────────────────────

    "budapest_kieninger_trap": VerifiedOpeningTrap(
        trap_id="budapest_kieninger_trap",
        name="Kieninger Trap",
        opening_key="budapest_gambit",
        opening_name="Budapest Gambit",
        variation_name="Budapest Gambit",
        setup_moves=["d4", "Nf6", "c4", "e5", "dxe5", "Ng4", "Bf4", "Nc6", "Nf3", "Bb4+", "Nbd2", "Qe7", "a3", "Ngxe5"],
        full_line=["d4", "Nf6", "c4", "e5", "dxe5", "Ng4", "Bf4", "Nc6", "Nf3", "Bb4+", "Nbd2", "Qe7", "a3", "Ngxe5", "Nxe5", "Nxe5", "e3", "Bxd2+", "Qxd2", "Nd3#"],
        trap_move="Nd3#",
        explanation="Black sacrifices pieces to reach a smothered mate with Nd3#. The queen, king, and knight coordination create a deadly mating pattern. One of the most beautiful traps in chess.",
        refutation="White should not play mechanically. Be aware of the Nd3 square and avoid the tactical sequence.",
        victim_color="white",
        trap_for="black",
        difficulty="intermediate",
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