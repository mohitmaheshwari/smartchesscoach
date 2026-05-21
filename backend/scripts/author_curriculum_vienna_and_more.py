"""Add Vienna Game and Englund Gambit (decline) curriculum entries.

Vienna Game (1.e4 e5 2.Nc3) — appeared 25 times in the full
4753-game corpus, missing from curriculum.

Englund Gambit (1.d4 e5) — appeared ~7 times in 500-game sample.
Black's questionable gambit; we teach the white response.

Run once:
    docker exec chess-coach-backend python /app/backend/scripts/author_curriculum_vienna_and_more.py
"""
import json
import os
import sys


vienna_game_entry = {
    "name": "Vienna Game",
    "color": "white",
    "summary": "1.e4 e5 2.Nc3. Develop the queen's knight first, then choose: Vienna Gambit (3.f4) for sharp attacking play, Bc4 (Italian-style) for solid positional play, or g3 (fianchetto) for hypermodern setups. Often transposes to Italian or King's Gambit territory.",
    "difficulty": "intermediate",
    "setup_order": ["e4", "Nc3", "Bc4", "d3", "Nf3", "O-O"],
    "golden_rules": [
        "Nc3 first, then commit: f4 (Vienna Gambit, sharp) or Bc4 (Italian-style, quiet).",
        "The Vienna Gambit (3.f4) is sharp — only play it if you've studied the lines.",
        "Bc4 + d3 + Nf3 + O-O is the calm path, transposes to Italian.",
        "Don't play Bg5 too early — Black can chase the bishop with h6."
    ],
    "traps": [],
    "tree": {
        "e4": {
            "idea": "Take the center.",
            "next": "Nc3",
            "responses": {
                "e5": {
                    "name": "Open Game",
                    "idea_opponent": "Black mirrors.",
                    "next": "Nc3",
                    "hint": "Develop the queen's knight first — the Vienna Game.",
                    "right_feedback": "Nc3 — Vienna Game. Develops the queen's knight before the king's knight.",
                    "wrong_feedback": "In the Vienna Game, Nc3 is the defining move — queen's knight first. Nf3 transposes to Italian/Ruy/Scotch (all fine, just different openings). Bc4 leads to Bishop's Opening. For the Vienna, Nc3 first.",
                    "responses": {
                        "Nf6": {
                            "name": "Vienna — Main",
                            "idea_opponent": "Black develops, attacks e4.",
                            "next": "Bc4",
                            "hint": "Italian-style: aim the bishop at f7. Or play f4 (Vienna Gambit) for sharp attack.",
                            "right_feedback": "Bc4 — quiet Vienna. Now plan d3 + Nf3 + O-O. (f4 is the Vienna Gambit — sharper alternative.)",
                            "wrong_feedback": "Against 2...Nf6, you have a real choice: Bc4 (quiet, Italian-style) or f4 (Vienna Gambit — sharp, theoretically OK but requires study). g3 (Fianchetto) is also valid. Pick based on style. For 1200-1500 players, Bc4 is the safer choice.",
                            "responses": {}
                        },
                        "Nc6": {
                            "name": "Vienna — Knight Defense",
                            "idea_opponent": "Black develops naturally.",
                            "next": "Bc4",
                            "right_feedback": "Bc4 — Italian-style setup, transposes nicely.",
                            "responses": {}
                        }
                    }
                }
            }
        }
    },
    "middlegame_plans": {
        "when_equal": {
            "plan": "Develop calmly: d3 + Nf3 + O-O + Nbd2 + Re1. Vienna positions are slow positional games unless you commit to the Gambit.",
            "ideas": [
                "Don't push f4 unless you have a clear attacking plan.",
                "Trade the bishop on c4 for Black's knight only if you get something concrete.",
                "Build up slowly with f3 + g3 + h3 + Kg2 as the king cluster."
            ]
        },
        "when_ahead": {
            "plan": "Push f4-f5 to expand on the kingside. Vienna structures naturally lead to kingside attacks.",
            "ideas": ["Push f4 then f5 to open lines.", "Sacrifice pieces for the king attack if calculation works."]
        },
        "when_behind": {
            "plan": "Trade pieces, simplify. The Vienna is rarely lost from solid positions.",
            "ideas": ["Trade queens.", "Keep pawns flexible.", "Avoid weakening the kingside."]
        }
    },
    "endgame_tips": [
        "Vienna endings often resemble Italian — same pawn structures, same plans.",
        "Bishop pair is the key asset if you keep both."
    ]
}


englund_gambit_response_entry = {
    "name": "Englund Gambit Response",
    "color": "white",
    "summary": "After 1.d4 e5 (Englund Gambit by Black), the principled response is 2.dxe5 — accept the pawn. Black has dubious compensation; if they try the Englund Gambit Mate Trap (2...Nc6 3.Nf3 Qe7 4.Bf4?? Qb4+ winning the b2 pawn or worse), white must NOT play 4.Bf4. Develop normally with 3.Nf3 and 4.Nc3 or 4.Bf4-with-care.",
    "difficulty": "beginner",
    "setup_order": ["d4", "dxe5", "Nf3", "Nc3", "e3", "Bd2"],
    "golden_rules": [
        "Accept the gambit: 2.dxe5 — take the pawn.",
        "Watch for the Englund Mate Trap: after 2...Nc6 3.Nf3 Qe7, do NOT play 4.Bf4 (loses to Qb4+).",
        "Develop calmly with Nf3 + Nc3 + e3 — don't try to keep all the extra material.",
        "Black usually has minimal compensation for the pawn — convert the endgame patiently."
    ],
    "traps": [],
    "tree": {
        "d4": {
            "idea": "Take the center.",
            "next": "d4",
            "responses": {
                "e5": {
                    "name": "Englund Gambit",
                    "idea_opponent": "Black sacrifices the e-pawn for dubious initiative.",
                    "next": "dxe5",
                    "hint": "Take the pawn. Black's gambit is theoretically losing.",
                    "right_feedback": "dxe5 — accept the gambit. Black has minimal compensation.",
                    "wrong_feedback": "Against the Englund Gambit (1...e5), dxe5 is the principled response — take the pawn. The Englund is theoretically unsound; you should win a pawn cleanly. Refusing with c4 or Nf3 is OK but accepting is sharper.",
                    "responses": {
                        "Nc6": {
                            "name": "Englund — Main attempt",
                            "idea_opponent": "Black develops, eyes e5.",
                            "next": "Nf3",
                            "hint": "Defend e5 with the knight.",
                            "right_feedback": "Nf3 — supports e5, develops naturally.",
                            "responses": {
                                "Qe7": {
                                    "name": "Englund — Mate Trap attempt",
                                    "idea_opponent": "Black sets up the Englund Mate Trap (Qb4+ next).",
                                    "next": "Nc3",
                                    "hint": "Develop the queen's knight — and AVOID Bf4 which loses to Qb4+.",
                                    "right_feedback": "Nc3 — develop safely. NOT Bf4 (which would lose to Qb4+ winning b2 pawn or queen).",
                                    "wrong_feedback": "In the Englund Mate Trap, Nc3 is correct. Bf4?? is the famous trap — Black plays Qb4+ and you lose the b2 pawn (or worse, the queen if you block with Qd2 Qxb2 winning). Nc3 develops safely AND defends b4 indirectly.",
                                    "responses": {}
                                }
                            }
                        }
                    }
                }
            }
        }
    },
    "middlegame_plans": {
        "when_equal": {
            "plan": "Convert the extra pawn. Trade pieces, simplify, win the endgame.",
            "ideas": ["Trade queens early.", "Centralize knights.", "Don't get clever; technique wins."]
        },
        "when_ahead": {
            "plan": "You're up a pawn from the start. Push the queenside majority in the endgame.",
            "ideas": ["Push a4-a5 or b4 to create a passed pawn.", "Trade pieces to reach a winning endgame."]
        },
        "when_behind": {
            "plan": "Shouldn't happen if you avoided the Englund Mate Trap. If it does, defend solidly.",
            "ideas": ["Trade material.", "Block central pawns.", "Wait for opponent to err."]
        }
    },
    "endgame_tips": [
        "Up-a-pawn endings: trade pieces, push passed pawns.",
        "The Englund Gambit's pawn advantage typically persists into the endgame."
    ]
}


def main():
    path = os.path.join(os.path.dirname(__file__), '..', 'data', 'opening_curriculum.json')
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    data['vienna_game'] = vienna_game_entry
    data['englund_gambit_response'] = englund_gambit_response_entry
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f'Added vienna_game + englund_gambit_response. Total openings: {len(data)}')


if __name__ == '__main__':
    sys.exit(main())
