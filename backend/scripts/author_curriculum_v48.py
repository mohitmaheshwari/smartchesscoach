"""One-shot script: author opening_curriculum.json trees for the 7
priority openings identified by user-data frequency analysis
(Mohit-flagged 2026-05-21).

Each tree follows the existing schema:
  - top-level key = the FIRST PLY (always white's move)
  - 'responses' = opp variations (white curric) or user variations (black curric)
  - 'next' = the user's expected next move (white curric) or opp's (black curric)
  - 'wrong_feedback' = hand-authored teaching in "In the [Opening], ..." voice
    ONLY at critical-lesson nodes per memory rule

Run once:
    docker exec chess-coach-backend python /app/backend/scripts/author_curriculum_v48.py
"""
import json
import os
import sys


italian_game_tree = {
    "e4": {
        "idea": "Take the center.",
        "next": "Nf3",
        "responses": {
            "e5": {
                "name": "Open Game",
                "idea_opponent": "Black mirrors — takes their share of the center.",
                "next": "Nf3",
                "right_feedback": "Nf3 — develops, attacks e5.",
                "responses": {
                    "Nc6": {
                        "name": "Defending e5",
                        "idea_opponent": "Black defends.",
                        "next": "Bc4",
                        "hint": "Aim at the weakest square.",
                        "right_feedback": "Bc4 — your bishop eyes f7.",
                        "wrong_feedback": "If you want the Italian Game, Bc4 is the move — aim at f7. Bb5 leads to the Ruy Lopez; d4 to the Scotch. Both fine, just different openings.",
                        "responses": {
                            "Bc5": {
                                "name": "Giuoco Piano",
                                "idea_opponent": "Black mirrors — classical setup.",
                                "next": "c3",
                                "hint": "Prepare d4 with a pawn first.",
                                "right_feedback": "c3 — prepares d4. The big center is coming.",
                                "wrong_feedback": "In the Italian Game, the idea is: c3 prepares d4 — that's how you build the big center. Playing d4 immediately lets Black trade with exd4, hitting your knight and equalizing.",
                                "responses": {
                                    "Nf6": {
                                        "name": "Italian Main Line",
                                        "idea_opponent": "Black develops, eyes e4.",
                                        "next": "d4",
                                        "right_feedback": "d4 — now you have the big center.",
                                        "responses": {}
                                    }
                                }
                            },
                            "Nf6": {
                                "name": "Two Knights Defense",
                                "idea_opponent": "Black plays more actively, eyes e4.",
                                "next": "Ng5",
                                "hint": "Black ignored f7 — punish it.",
                                "right_feedback": "Ng5 — attacks f7! Black must defend with d5 or face the Fried Liver.",
                                "wrong_feedback": "In the Two Knights Defense, Ng5 attacks f7 directly. d3 is the quiet Modern Italian (safer). Both work — but avoid Nc3 which lets Black equalize easily.",
                                "responses": {
                                    "d5": {
                                        "name": "Two Knights — d5",
                                        "idea_opponent": "Black blocks the diagonal, counter-attacks the bishop.",
                                        "next": "exd5",
                                        "right_feedback": "exd5 — wins a pawn.",
                                        "responses": {
                                            "Nxd5": {
                                                "name": "Fried Liver setup",
                                                "idea_opponent": "Black recaptures with the knight — walks into the Fried Liver.",
                                                "next": "Nxf7",
                                                "right_feedback": "Nxf7! — the Fried Liver Attack. Black's king is exposed.",
                                                "wrong_feedback": "After exd5 Nxd5, Nxf7 is THE move — the Fried Liver. Any other move lets Black escape.",
                                                "responses": {}
                                            },
                                            "Na5": {
                                                "name": "Polerio Defense",
                                                "idea_opponent": "Black hits the bishop, sidestepping the Fried Liver.",
                                                "next": "Bb5+",
                                                "right_feedback": "Bb5+ — check, keeps the bishop active.",
                                                "wrong_feedback": "In the Polerio, Bb5+ is principled — give check first. Retreating with Bb3 or Bf1 loses tempo.",
                                                "responses": {}
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}


scotch_game_tree = {
    "e4": {
        "idea": "Take the center.",
        "next": "Nf3",
        "responses": {
            "e5": {
                "next": "Nf3",
                "right_feedback": "Nf3 — develops, attacks e5.",
                "responses": {
                    "Nc6": {
                        "next": "d4",
                        "hint": "Open the center with a pawn break.",
                        "right_feedback": "d4 — the Scotch Game. Strikes the center immediately.",
                        "wrong_feedback": "In the Scotch Game, d4 is the defining move — open the center before Black gets organized. Bc4 leads to the Italian, Bb5 to the Ruy Lopez. Choose d4 for the Scotch.",
                        "responses": {
                            "exd4": {
                                "name": "Scotch — Main Line",
                                "next": "Nxd4",
                                "right_feedback": "Nxd4 — strong central knight.",
                                "wrong_feedback": "In the Scotch, Nxd4 is the right recapture — the knight on d4 is excellent. Don't take with the queen (Qxd4) which lets Black gain tempo with Nc6 hitting your queen.",
                                "responses": {
                                    "Nf6": {
                                        "name": "Scotch — Nf6 Main",
                                        "idea_opponent": "Black attacks e4.",
                                        "next": "Nc3",
                                        "right_feedback": "Nc3 — defends e4, develops.",
                                        "responses": {}
                                    },
                                    "Bc5": {
                                        "name": "Scotch Classical",
                                        "idea_opponent": "Black eyes the knight and f2.",
                                        "next": "Be3",
                                        "right_feedback": "Be3 — defends the knight, blocks Black's bishop.",
                                        "wrong_feedback": "In the Scotch Classical, Be3 is the right defensive idea — supports d4 and blocks Black's bishop diagonal. Nxc6 just damages your own structure unnecessarily.",
                                        "responses": {}
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}


philidor_defense_entry = {
    "name": "Philidor Defense",
    "color": "white",
    "summary": "How to handle Black's Philidor Defense (1.e4 e5 2.Nf3 d6). Black plays passively, supporting e5 with the d-pawn. Punish this by opening the center immediately with 3.d4 — your space advantage often persists into the middlegame and endgame.",
    "difficulty": "beginner",
    "setup_order": ["e4", "Nf3", "d4", "Nxd4", "Nc3", "Bc4"],
    "golden_rules": [
        "Open the center with 3.d4 — Black's setup is passive, exploit the space.",
        "After 3...exd4, recapture with the knight (4.Nxd4), keeping pieces active.",
        "Bc4 aims at f7 — even more effective here since Black's king has less support.",
        "Don't trade pieces — Black wants simplification, you want activity."
    ],
    "traps": [],
    "tree": {
        "e4": {
            "next": "Nf3",
            "responses": {
                "e5": {
                    "next": "Nf3",
                    "right_feedback": "Nf3 — develops, attacks e5.",
                    "responses": {
                        "d6": {
                            "name": "Philidor Defense",
                            "idea_opponent": "Black defends e5 passively — cramped but solid.",
                            "next": "d4",
                            "hint": "Black's setup is passive. How do you punish it?",
                            "right_feedback": "d4 — opens the center against Black's cramped position.",
                            "wrong_feedback": "In the Philidor Defense, the idea is: open the center with d4 — Black has chosen a passive setup, exploit the space they gave up. Bc4 or Nc3 first let Black consolidate; d4 immediately is the punishment.",
                            "responses": {
                                "exd4": {
                                    "name": "Philidor — Main Line",
                                    "idea_opponent": "Black trades to relieve pressure.",
                                    "next": "Nxd4",
                                    "right_feedback": "Nxd4 — strong central knight, more space than Black.",
                                    "wrong_feedback": "In the Philidor, Nxd4 is right. Qxd4 lets Black gain a tempo with Nc6 hitting your queen.",
                                    "responses": {
                                        "Nf6": {
                                            "name": "Philidor — Classical",
                                            "idea_opponent": "Black develops, attacks e4.",
                                            "next": "Nc3",
                                            "right_feedback": "Nc3 — defends e4, develops naturally.",
                                            "responses": {}
                                        }
                                    }
                                },
                                "Nf6": {
                                    "name": "Philidor — Hanham",
                                    "idea_opponent": "Black holds the center, planning Nbd7 + Be7.",
                                    "next": "Nc3",
                                    "right_feedback": "Nc3 — develops, supports e4. Plan Bc4 + O-O next.",
                                    "wrong_feedback": "In the Philidor Hanham, Nc3 is natural development. Don't push d5 yet — closing the center helps Black who has less space. Develop first.",
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
            "plan": "Develop calmly with Bc4 + Nc3 + O-O + h3. Black has less space — patient play wins.",
            "ideas": [
                "Don't trade pieces — Black wants simplification.",
                "Black's Be7 / Bd6 bishop is passive; trade your worst piece for it if convenient."
            ]
        },
        "when_ahead": {
            "plan": "Open lines on the kingside — Black's king is the weakest spot in their cramped position.",
            "ideas": ["Pawn storm on the kingside if Black castled there.", "Trade queens only when the endgame is clearly winning."]
        },
        "when_behind": {
            "plan": "Simplify and aim for a draw — Black's positional advantages are usually minimal.",
            "ideas": ["Trade pieces.", "Avoid weak squares around the king."]
        }
    },
    "endgame_tips": [
        "Your space advantage often persists — keep pieces active.",
        "Black's bishops often end up on bad squares (e7, d7) — exploit this in piece endings."
    ]
}


caro_kann_tree = {
    # Black curric: tree.next is USER (black) move; tree.responses keys are OPP (white) variations.
    "e4": {
        "idea_opponent": "White takes the center.",
        "next": "c6",
        "hint": "What move builds a wall and prepares d5 with pawn support?",
        "right_feedback": "c6 — the Caro-Kann. You'll play d5 with the c-pawn backing it up.",
        "responses": {
            "d4": {
                "name": "Caro-Kann main",
                "idea_opponent": "White builds the big center.",
                "next": "d5",
                "right_feedback": "d5 — challenge the center with pawn support from c6.",
                "responses": {
                    "Nc3": {
                        "name": "Caro-Kann — Classical setup",
                        "idea_opponent": "White attacks the d-pawn.",
                        "next": "dxe4",
                        "right_feedback": "dxe4 — take the e-pawn, open lines for your light-square bishop.",
                        "responses": {
                            "Nxe4": {
                                "name": "Caro-Kann — Classical Main Line",
                                "idea_opponent": "White recaptures, knight centralized.",
                                "next": "Bf5",
                                "hint": "Now develop the light-square bishop — but where, before you lock in e6?",
                                "right_feedback": "Bf5 — your bishop goes OUTSIDE the pawn chain, the defining Caro-Kann idea.",
                                "wrong_feedback": "In the Caro-Kann Classical, Bf5 is the defining move — get your light-square bishop OUTSIDE the c6-d5-e6 pawn chain BEFORE you lock it in with e6. Playing Nd7 or Nf6 first traps the bishop inside the chain — the classic Caro-Kann mistake.",
                                "responses": {}
                            }
                        }
                    }
                }
            }
        }
    }
}


ruy_lopez_tree = {
    "e4": {
        "next": "Nf3",
        "responses": {
            "e5": {
                "next": "Nf3",
                "right_feedback": "Nf3 — develops, attacks e5.",
                "responses": {
                    "Nc6": {
                        "next": "Bb5",
                        "hint": "Pin the defender of e5.",
                        "right_feedback": "Bb5 — the Spanish Bishop. Pressures the knight that defends e5.",
                        "wrong_feedback": "In the Ruy Lopez, Bb5 is the defining move — attack the defender of e5 directly. Bc4 leads to the Italian; here the idea is to pressure the knight that holds Black's center together.",
                        "responses": {
                            "a6": {
                                "name": "Morphy Defense",
                                "idea_opponent": "Black asks the bishop a question.",
                                "next": "Ba4",
                                "right_feedback": "Ba4 — keeps the pin. Black plays Nf6, you castle.",
                                "wrong_feedback": "In the Ruy Lopez, Ba4 keeps your pin on the c6-knight. Bxc6 is the Exchange Variation — playable but trades your bishop pair away. Ba4 is the main line.",
                                "responses": {
                                    "Nf6": {
                                        "name": "Closed Ruy Lopez",
                                        "idea_opponent": "Black develops, attacks e4.",
                                        "next": "O-O",
                                        "right_feedback": "O-O — castle. The pin defends e4 indirectly (if Nxe4 then Re1 wins the knight back).",
                                        "wrong_feedback": "In the Ruy Lopez Closed, O-O is correct — the pin on c6 means Nxe4 is unsafe for Black (Re1 pins). Don't waste time defending e4 with d3; castle first.",
                                        "responses": {}
                                    }
                                }
                            },
                            "Nf6": {
                                "name": "Berlin Defense",
                                "idea_opponent": "Black attacks e4 immediately — the Berlin Wall.",
                                "next": "O-O",
                                "right_feedback": "O-O — same idea. The pin defends e4.",
                                "responses": {}
                            }
                        }
                    }
                }
            }
        }
    }
}


sicilian_defense_tree = {
    # Black curric: next = user (black) move; responses keys = opp (white) variations.
    "e4": {
        "idea_opponent": "White takes the center.",
        "next": "c5",
        "hint": "What move fights for d4 from the flank, avoiding symmetry?",
        "right_feedback": "c5 — the Sicilian. Most ambitious response to e4.",
        "responses": {
            "Nf3": {
                "name": "Sicilian — Open setup begins",
                "idea_opponent": "White's most popular Sicilian move, preparing d4.",
                "next": "d6",
                "hint": "Flexible Najdorf-style setup — prepare Nf6 and later a6.",
                "right_feedback": "d6 — supports e5 push, prepares Nf6.",
                "responses": {
                    "d4": {
                        "name": "Open Sicilian",
                        "idea_opponent": "White's pawn break.",
                        "next": "cxd4",
                        "right_feedback": "cxd4 — trade pawns, open the c-file for queenside play.",
                        "responses": {
                            "Nxd4": {
                                "name": "Open Sicilian — Main",
                                "idea_opponent": "White's knight is centralized.",
                                "next": "Nf6",
                                "right_feedback": "Nf6 — develop, attack the e-pawn.",
                                "responses": {
                                    "Nc3": {
                                        "name": "Open Sicilian — Nc3",
                                        "idea_opponent": "White defends e4 and develops.",
                                        "next": "a6",
                                        "hint": "Najdorf or Classical? a6 commits you to one of the most-studied openings in chess.",
                                        "right_feedback": "a6 — the Najdorf. Prepare b5 + Bb7, fight on the queenside.",
                                        "wrong_feedback": "In the Najdorf Sicilian, a6 prepares b5 + Bb7 — fighting on the queenside. Nc6 here would be the Classical Sicilian (different plan: knight to c6, dark-square strategy). Both are sound; if you want the Najdorf, a6 is the move.",
                                        "responses": {}
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}


scandinavian_defense_tree = {
    # Black curric: next = user (black) move; responses keys = opp (white) variations.
    "e4": {
        "idea_opponent": "White takes the center.",
        "next": "d5",
        "hint": "What move challenges the e-pawn immediately?",
        "right_feedback": "d5 — the Scandinavian. Accept a tempo loss to rid the board of White's e-pawn.",
        "responses": {
            "exd5": {
                "name": "Scandinavian — Main",
                "idea_opponent": "White takes the pawn.",
                "next": "Qxd5",
                "hint": "Recapture immediately with the queen (main line).",
                "right_feedback": "Qxd5 — accept the tempo loss for clear development.",
                "responses": {
                    "Nc3": {
                        "name": "Scandinavian — Nc3 attacking the queen",
                        "idea_opponent": "White develops with tempo, attacking your queen.",
                        "next": "Qa5",
                        "hint": "Where does the queen go — safely active, not blocking your own pieces?",
                        "right_feedback": "Qa5 — keeps the queen active, doesn't block the d-file for your rook.",
                        "wrong_feedback": "In the Scandinavian, after 1.e4 d5 2.exd5 Qxd5 3.Nc3, Qa5 is the main retreat — keeps the queen active and out of trouble. Qd8 wastes the whole opening (gives back the tempo you bought with the queen excursion); Qd6 is playable but blocks the d-file for your rook.",
                        "responses": {}
                    }
                }
            }
        }
    }
}


def main():
    path = os.path.join(os.path.dirname(__file__), '..', 'data', 'opening_curriculum.json')
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print('Extending italian_game tree...')
    data['italian_game']['tree'] = italian_game_tree

    print('Extending scotch_game tree...')
    data['scotch_game']['tree'] = scotch_game_tree

    print('Adding philidor_defense (new entry)...')
    data['philidor_defense'] = philidor_defense_entry

    print('Extending caro_kann tree...')
    data['caro_kann']['tree'] = caro_kann_tree

    print('Extending ruy_lopez tree...')
    data['ruy_lopez']['tree'] = ruy_lopez_tree

    print('Extending sicilian_defense tree...')
    data['sicilian_defense']['tree'] = sicilian_defense_tree

    print('Extending scandinavian_defense tree...')
    data['scandinavian_defense']['tree'] = scandinavian_defense_tree

    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print()
    print(f'Total openings now: {len(data)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
