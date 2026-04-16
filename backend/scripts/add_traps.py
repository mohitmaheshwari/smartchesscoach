"""Add 13 new traps to opening_theory_tree.json"""
import json
import os
import sys

tree_path = os.path.join(os.path.dirname(__file__), "..", "data", "coaching", "opening_theory_tree.json")

with open(tree_path, encoding="utf-8") as f:
    tree = json.load(f)

# Traps to add to EXISTING openings
new_traps = {
    "ruy_lopez": [
        {
            "trap_id": "fishing_pole",
            "name": "Fishing Pole Trap",
            "variation": "berlin",
            "setup_moves": ["e4","e5","Nf3","Nc6","Bb5","Nf6","O-O","Ng4","h3"],
            "full_line": ["e4","e5","Nf3","Nc6","Bb5","Nf6","O-O","Ng4","h3","h5","hxg4","hxg4"],
            "trap_move": "h5",
            "explanation": "The h-pawn sacrifice rips open the h-file. After hxg4 hxg4+, the king is exposed and mate threats follow on the h-file.",
            "refutation": "After Ng4, do NOT play h3. Play d4 instead.",
            "victim_color": "white",
            "trap_for": "black",
            "difficulty": "intermediate",
            "category": "trap"
        },
        {
            "trap_id": "noahs_ark",
            "name": "Noah's Ark Trap",
            "variation": "morphy_defense",
            "setup_moves": ["e4","e5","Nf3","Nc6","Bb5","a6","Ba4","d6","d4","b5","Bb3"],
            "full_line": ["e4","e5","Nf3","Nc6","Bb5","a6","Ba4","d6","d4","b5","Bb3","exd4","Nxd4","Nxd4","Qxd4","c5","Qd5","Be6","Qc6+","Bd7","Qd5","c4"],
            "trap_move": "c4",
            "explanation": "The pawns on a6-b5-c4 trap the bishop on b3. It has nowhere to go. One of the oldest traps in chess.",
            "refutation": "Do not play d4 early. Castle first or play c3.",
            "victim_color": "white",
            "trap_for": "black",
            "difficulty": "beginner",
            "category": "trap"
        },
        {
            "trap_id": "mortimer_trap",
            "name": "Mortimer Trap",
            "variation": "mortimer_defense",
            "setup_moves": ["e4","e5","Nf3","Nc6","Bb5","Nf6","d3","Ne7"],
            "full_line": ["e4","e5","Nf3","Nc6","Bb5","Nf6","d3","Ne7","Nxe5","c6","Ba4","Qa5+"],
            "trap_move": "Qa5+",
            "explanation": "Ne7 looks odd but opens the queen diagonal. After Nxe5, c6 kicks the bishop and Qa5+ forks king and knight.",
            "refutation": "After Ne7, do NOT take on e5. Castle or play Nc3.",
            "victim_color": "white",
            "trap_for": "black",
            "difficulty": "intermediate",
            "category": "trap"
        }
    ],
    "petrov_defense": [
        {
            "trap_id": "stafford_gambit",
            "name": "Stafford Gambit",
            "variation": None,
            "setup_moves": ["e4","e5","Nf3","Nf6","Nxe5","Nc6","Nxc6","dxc6","d3","Bc5"],
            "full_line": ["e4","e5","Nf3","Nf6","Nxe5","Nc6","Nxc6","dxc6","d3","Bc5","Be2","Ng4","Bxg4","Qh4"],
            "trap_move": "Ng4",
            "explanation": "After Ng4, if Bxg4 then Qh4 threatens Qxf2# and Bxg4. If O-O instead, Qxf2 is checkmate.",
            "refutation": "After Nc6, retreat the knight with Nf3 or play d3 followed by d4.",
            "victim_color": "white",
            "trap_for": "black",
            "difficulty": "intermediate",
            "category": "trap"
        }
    ],
    "budapest_gambit": [
        {
            "trap_id": "budapest_smothered_mate",
            "name": "Budapest Smothered Mate",
            "variation": None,
            "setup_moves": ["d4","Nf6","c4","e5","dxe5","Ng4","Bf4","Nc6","Nf3","Bb4+","Nbd2","Qe7","a3"],
            "full_line": ["d4","Nf6","c4","e5","dxe5","Ng4","Bf4","Nc6","Nf3","Bb4+","Nbd2","Qe7","a3","Ngxe5","Nxe5","Nxe5","axb4","Nd3#"],
            "trap_move": "Nd3#",
            "explanation": "Smothered checkmate! White thinks axb4 wins a bishop but Nd3# is mate. The king is trapped by its own pieces.",
            "refutation": "Play e3 or Nf3 on move 4, not Bf4. Do not allow the Bb4+ Qe7 sequence.",
            "victim_color": "white",
            "trap_for": "black",
            "difficulty": "intermediate",
            "category": "trap"
        }
    ],
    "qgd": [
        {
            "trap_id": "marshall_trap",
            "name": "Marshall Trap",
            "variation": None,
            "setup_moves": ["d4","d5","c4","e6","Nc3","Nf6","Bg5","Nbd7","cxd5","exd5"],
            "full_line": ["d4","d5","c4","e6","Nc3","Nf6","Bg5","Nbd7","cxd5","exd5","Nxd5","Nxd5","Bxd8","Bb4+","Qd2","Bxd2+","Kxd2","Kxd8"],
            "trap_move": "Bb4+",
            "explanation": "White takes the d5 pawn and thinks they win the queen with Bxd8. But Bb4+ is an in-between check that forces Qd2, and Bxd2+ wins White's queen.",
            "refutation": "Do NOT play Nxd5. The pawn is not free. Play e3 or Nf3.",
            "victim_color": "white",
            "trap_for": "black",
            "difficulty": "beginner",
            "category": "trap"
        },
        {
            "trap_id": "elephant_trap",
            "name": "Elephant Trap",
            "variation": None,
            "setup_moves": ["d4","d5","c4","e6","Nc3","Nf6","Bg5","Nbd7","Nf3","Be7","e3","O-O","Bd3","dxc4","Bxc4","b5","Bd3"],
            "full_line": ["d4","d5","c4","e6","Nc3","Nf6","Bg5","Nbd7","Nf3","Be7","e3","O-O","Bd3","dxc4","Bxc4","b5","Bd3","a6"],
            "trap_move": "Nxe4",
            "explanation": "After b5 and a6, Black plays Nxe4. If Bxe7 Qxe7 and then Bxe4, Bb7 hits the bishop on the long diagonal. White loses material.",
            "refutation": "After b5, do not retreat bishop to d3. Play Be2 or a4.",
            "victim_color": "white",
            "trap_for": "black",
            "difficulty": "beginner",
            "category": "trap"
        }
    ],
    "caro_kann": [
        {
            "trap_id": "caro_kann_smothered_mate",
            "name": "Caro-Kann Smothered Mate",
            "variation": None,
            "setup_moves": ["e4","c6","d4","d5","Nc3","dxe4","Nxe4","Nd7"],
            "full_line": ["e4","c6","d4","d5","Nc3","dxe4","Nxe4","Nd7","Qe2","Ngf6","Nd6#"],
            "trap_move": "Nd6#",
            "explanation": "Smothered mate! Ngf6 is the most natural move but the king is boxed in by its own pieces. Nd6 delivers checkmate.",
            "refutation": "Do NOT play Ngf6 after Qe2. Play e6 first to give the king an escape square.",
            "victim_color": "black",
            "trap_for": "white",
            "difficulty": "beginner",
            "category": "trap"
        }
    ],
    "sicilian_defense": [
        {
            "trap_id": "siberian_trap",
            "name": "Siberian Trap",
            "variation": "smith_morra",
            "setup_moves": ["e4","c5","d4","cxd4","c3","dxc3","Nxc3","Nc6","Nf3","e6","Bc4","d6","O-O","Be7","Qe2","a6","Rd1","Qc7","Bf4"],
            "full_line": ["e4","c5","d4","cxd4","c3","dxc3","Nxc3","Nc6","Nf3","e6","Bc4","d6","O-O","Be7","Qe2","a6","Rd1","Qc7","Bf4","e5","Bg5","Nd4"],
            "trap_move": "Nd4",
            "explanation": "The knight forks the queen on e2 and threatens Nxf3+. White cannot save both pieces.",
            "refutation": "After e5, play Bg3 not Bg5. Or avoid Bf4 entirely.",
            "victim_color": "white",
            "trap_for": "black",
            "difficulty": "intermediate",
            "category": "trap"
        }
    ]
}

# New openings
new_openings = {
    "four_knights": {
        "name": "Four Knights Game",
        "eco": "C47",
        "main_line": ["e4","e5","Nf3","Nc6","Nc3","Nf6"],
        "white_plan": "Develop all four knights, control the center, play d4",
        "black_plan": "Mirror development, keep the center balanced",
        "traps": [
            {
                "trap_id": "halloween_gambit",
                "name": "Halloween Gambit",
                "variation": None,
                "setup_moves": ["e4","e5","Nf3","Nc6","Nc3","Nf6"],
                "full_line": ["e4","e5","Nf3","Nc6","Nc3","Nf6","Nxe5","Nxe5","d4","Nc6","d5","Ne5","f4","Ng6","e5","Ng8","d6"],
                "trap_move": "Nxe5",
                "explanation": "White gives up a knight for one pawn but gets a huge pawn center with d4-d5-e5. Black's pieces get pushed all the way back to the starting squares.",
                "refutation": "After Nxe5, play Nc6 then Bb4 to pin the knight. Black keeps the extra piece.",
                "victim_color": "black",
                "trap_for": "white",
                "difficulty": "intermediate",
                "category": "trap"
            }
        ],
        "variations": {}
    },
    "englund_gambit": {
        "name": "Englund Gambit",
        "eco": "A40",
        "main_line": ["d4","e5"],
        "white_plan": "Accept the gambit, develop solidly",
        "black_plan": "Sacrifice a pawn for tricks",
        "traps": [
            {
                "trap_id": "englund_gambit_trap",
                "name": "Englund Gambit Trap",
                "variation": None,
                "setup_moves": ["d4","e5","dxe5","Nc6","Nf3","Qe7"],
                "full_line": ["d4","e5","dxe5","Nc6","Nf3","Qe7","Bf4","Qb4+","Bd2","Qxb2","Bc3","Bb4"],
                "trap_move": "Bb4",
                "explanation": "White thinks Bc3 traps the queen. But Bb4 pins the bishop to the king! After Bxb4 Qxa1, Black wins a rook.",
                "refutation": "Do NOT play Bf4. Play Qd5, e3, or Nc3 instead.",
                "victim_color": "white",
                "trap_for": "black",
                "difficulty": "beginner",
                "category": "trap"
            }
        ],
        "variations": {}
    },
    "albin_counter_gambit": {
        "name": "Albin Counter-Gambit",
        "eco": "D08",
        "main_line": ["d4","d5","c4","e5"],
        "white_plan": "Accept the gambit, hold the center",
        "black_plan": "Push d4, create complications",
        "traps": [
            {
                "trap_id": "lasker_trap",
                "name": "Lasker Trap",
                "variation": None,
                "setup_moves": ["d4","d5","c4","e5","dxe5","d4","e3","Bb4+","Bd2","dxe3"],
                "full_line": ["d4","d5","c4","e5","dxe5","d4","e3","Bb4+","Bd2","dxe3","Bxb4","exf2+","Ke2","fxg1=N+"],
                "trap_move": "fxg1=N+",
                "explanation": "The pawn promotes to a KNIGHT not a queen! The knight gives check and forks king and rook. One of the most beautiful underpromotions in chess.",
                "refutation": "Do NOT play e3. Play Nf3 instead. If e3, after dxe3 play fxe3 not Bxb4.",
                "victim_color": "white",
                "trap_for": "black",
                "difficulty": "intermediate",
                "category": "trap"
            }
        ],
        "variations": {}
    }
}

# Add traps to existing openings
for opening_key, traps in new_traps.items():
    if opening_key in tree:
        existing_ids = {t["trap_id"] for t in tree[opening_key].get("traps", [])}
        for trap in traps:
            if trap["trap_id"] not in existing_ids:
                tree[opening_key].setdefault("traps", []).append(trap)
                print(f"Added {trap['name']} to {opening_key}")

# Add new openings
for key, opening in new_openings.items():
    if key not in tree:
        tree[key] = opening
        print(f"Added new opening: {key} ({opening['name']})")
    else:
        existing_ids = {t["trap_id"] for t in tree[key].get("traps", [])}
        for trap in opening.get("traps", []):
            if trap["trap_id"] not in existing_ids:
                tree[key].setdefault("traps", []).append(trap)
                print(f"Added {trap['name']} to existing {key}")

# Save
with open(tree_path, "w", encoding="utf-8") as f:
    json.dump(tree, f, indent=2, ensure_ascii=False)

total = sum(len(v.get("traps", [])) for v in tree.values() if isinstance(v, dict))
print(f"\nTotal traps in system: {total}")
