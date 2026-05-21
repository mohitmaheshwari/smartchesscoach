"""Phase 2 curriculum authoring (Mohit 2026-05-21): extend the 5
existing-but-shallow opening trees:
  - french_defense (depth 2 → deep)
  - queens_gambit (depth 3 → deep)
  - kings_indian_defense (empty → built from scratch)
  - slav_defense (empty → built from scratch)
  - english_opening (empty → built from scratch)

Each tree follows the v48 convention:
  - top-level key = the FIRST PLY (always white's move)
  - For white-curric (queens_gambit, english_opening):
      next = user (white) next move, responses = opp (black) variations
  - For black-curric (french_defense, kings_indian_defense, slav_defense):
      next = user (black) next move, responses = opp (white) variations
  - wrong_feedback ONLY at critical-lesson nodes (memory rule)

Run once:
    docker exec chess-coach-backend python /app/backend/scripts/author_curriculum_v49.py
"""
import json
import os
import sys


# ────────────────────────────────────────────────────────────────────
# French Defense (color=black) — 1.e4 e6
# Main: 2.d4 d5, then 3.Nc3 (Classical), 3.Nd2 (Tarrasch),
#       3.e5 (Advance), 3.exd5 (Exchange)
# We teach the Classical Nc3 line (most popular)
# ────────────────────────────────────────────────────────────────────
french_defense_tree = {
    "e4": {
        "idea_opponent": "White takes the center.",
        "next": "e6",
        "hint": "What move builds a solid wall, preparing d5?",
        "right_feedback": "e6 — the French Defense. You'll strike with d5 next, supported by the e-pawn.",
        "responses": {
            "d4": {
                "name": "French — Main",
                "idea_opponent": "White builds the big center.",
                "next": "d5",
                "right_feedback": "d5 — challenge the e-pawn. White must commit to a setup.",
                "responses": {
                    "Nc3": {
                        "name": "French — Classical Variation",
                        "idea_opponent": "White defends e4 with a developing move.",
                        "next": "Nf6",
                        "hint": "Develop, attack the e4 pawn.",
                        "right_feedback": "Nf6 — pressures e4, develops naturally.",
                        "wrong_feedback": "In the French Defense, after 3.Nc3, Nf6 is the main move — develop with tempo on e4. Bb4 is the Winawer (sharp, sound but different plan); dxe4 is the Rubinstein (passive, gives up the center). For the Classical French, Nf6 is the canonical choice.",
                        "responses": {
                            "e5": {
                                "name": "French — Steinitz Variation",
                                "idea_opponent": "White pushes past, gains space, kicks the knight.",
                                "next": "Nfd7",
                                "hint": "Where does the knight go to avoid blocking the c-pawn?",
                                "right_feedback": "Nfd7 — knight retreats but keeps c5 break available.",
                                "wrong_feedback": "In the French Steinitz, Nfd7 is correct — preserves c5 break. Ng8 wastes the entire opening's development; Ne4 is unsound (4.Nxe4 wins).",
                                "responses": {}
                            }
                        }
                    },
                    "e5": {
                        "name": "French — Advance Variation",
                        "idea_opponent": "White locks the center, gains space, hopes to attack the kingside.",
                        "next": "c5",
                        "hint": "Challenge the pawn chain at its base.",
                        "right_feedback": "c5 — the standard French break, hits the base of White's pawn chain.",
                        "wrong_feedback": "In the French Advance, c5 is THE move — challenge White's pawn chain at its base (d4). Without c5, you're left passive with no counterplay. Don't let the Advance Variation lock you in without striking c5.",
                        "responses": {}
                    },
                    "exd5": {
                        "name": "French — Exchange Variation",
                        "idea_opponent": "White trades and aims for a quiet game.",
                        "next": "exd5",
                        "right_feedback": "exd5 — symmetric structure. Develop carefully; the Exchange is dry but not equal.",
                        "responses": {}
                    }
                }
            }
        }
    }
}


# ────────────────────────────────────────────────────────────────────
# Queen's Gambit (color=white) — 1.d4 d5 2.c4
# Branches: 2...e6 (QGD), 2...c6 (Slav — separate entry),
#           2...dxc4 (QGA), 2...e5 (Albin), 2...Nc6 (Chigorin)
# We teach the QGD main: 1.d4 d5 2.c4 e6 3.Nc3 Nf6 4.Bg5 (or cxd5)
# ────────────────────────────────────────────────────────────────────
queens_gambit_tree = {
    # White curric: next = user (white) move, responses = opp (black) variations.
    "d4": {
        "idea": "Take the center.",
        "next": "c4",
        "responses": {
            "d5": {
                "name": "Closed Game",
                "idea_opponent": "Black meets pawn with pawn.",
                "next": "c4",
                "hint": "What's the gambit move that offers a pawn for development?",
                "right_feedback": "c4 — the Queen's Gambit. Offers the c-pawn to break Black's pawn on d5.",
                "wrong_feedback": "In the Queen's Gambit, c4 is the defining move — offer the c-pawn to break Black's pawn on d5. Without c4, you're playing a quiet Queen's Pawn Game, not the Queen's Gambit.",
                "responses": {
                    "e6": {
                        "name": "Queen's Gambit Declined (QGD)",
                        "idea_opponent": "Black declines, builds a solid wall.",
                        "next": "Nc3",
                        "right_feedback": "Nc3 — develops, attacks d5.",
                        "responses": {
                            "Nf6": {
                                "name": "QGD — Main Line",
                                "idea_opponent": "Black develops, supports d5.",
                                "next": "Bg5",
                                "hint": "Develop the bishop actively, pin the f6 knight.",
                                "right_feedback": "Bg5 — pins the knight, pressures Black's center.",
                                "wrong_feedback": "In the QGD, Bg5 is the main attacking move — pins the f6 knight, indirectly pressuring d5. Nf3 first (the Exchange Variation order) is also playable but less ambitious; Bf4 leads to the London-style setup, different plan. For classical QGD, Bg5 is canonical.",
                                "responses": {}
                            }
                        }
                    },
                    "dxc4": {
                        "name": "Queen's Gambit Accepted (QGA)",
                        "idea_opponent": "Black accepts the pawn, plans to give it back for development.",
                        "next": "Nf3",
                        "hint": "Develop first, regain the pawn later.",
                        "right_feedback": "Nf3 — develop. The c4 pawn isn't going anywhere safely; you'll get it back with e3+Bxc4.",
                        "wrong_feedback": "In the QGA, Nf3 first is the modern way — develop before grabbing the pawn. Trying to win c4 immediately with Qa4+ is theoretically OK but loses tempo and creates an exposed queen. Develop, castle, THEN reclaim c4.",
                        "responses": {}
                    },
                    "c6": {
                        "name": "Slav Defense",
                        "idea_opponent": "Black supports d5 with the c-pawn instead of e6.",
                        "next": "Nf3",
                        "right_feedback": "Nf3 — develop, prepare to handle the Slav structure.",
                        "responses": {}
                    }
                }
            }
        }
    }
}


# ────────────────────────────────────────────────────────────────────
# King's Indian Defense (color=black) — 1.d4 Nf6 2.c4 g6
# Main: 3.Nc3 Bg7 4.e4 d6 5.Nf3 O-O 6.Be2 e5 (Classical KID)
# Alt White setup: 4.g3 (Fianchetto), 5.f3 (Sämisch)
# ────────────────────────────────────────────────────────────────────
kings_indian_defense_tree = {
    "d4": {
        "idea_opponent": "White takes the center.",
        "next": "Nf6",
        "hint": "What's the universal knight move against d4?",
        "right_feedback": "Nf6 — flexible. Develops, attacks the e4 square.",
        "responses": {
            "c4": {
                "name": "KID setup begins",
                "idea_opponent": "White claims the big center.",
                "next": "g6",
                "hint": "Prepare the fianchetto — King's Indian Defense.",
                "right_feedback": "g6 — the King's Indian Defense. Fianchetto coming.",
                "wrong_feedback": "In the King's Indian Defense, g6 is the defining move — preparing the fianchetto bishop on g7. e6 here leads to the Nimzo-Indian or QGD (different opening, different plans). For the KID, g6 commits you to the hypermodern setup.",
                "responses": {
                    "Nc3": {
                        "name": "KID — Main Line",
                        "idea_opponent": "White develops, supports the center.",
                        "next": "Bg7",
                        "right_feedback": "Bg7 — completes the fianchetto, eyes the long diagonal.",
                        "responses": {
                            "e4": {
                                "name": "KID — Classical Main",
                                "idea_opponent": "White builds the maximum center.",
                                "next": "d6",
                                "hint": "Prepare the central counter-strike with e5 later.",
                                "right_feedback": "d6 — supports e5 break, the soul of the KID.",
                                "wrong_feedback": "In the King's Indian Defense, d6 is the principled preparation for the e5 break — the entire KID plan revolves around striking e5 against White's center. d5 here closes the center prematurely (you'd be playing a worse Grünfeld).",
                                "responses": {
                                    "Nf3": {
                                        "name": "KID — Classical Mainline",
                                        "idea_opponent": "White develops, prepares castling.",
                                        "next": "O-O",
                                        "right_feedback": "O-O — get the king safe before launching the kingside attack.",
                                        "responses": {
                                            "Be2": {
                                                "name": "KID — Classical Setup",
                                                "idea_opponent": "White's bishop goes to a quiet square; main line ahead.",
                                                "next": "e5",
                                                "hint": "Now strike at the center.",
                                                "right_feedback": "e5 — the KID break. White must decide: close with d5 (main) or trade.",
                                                "wrong_feedback": "In the KID Classical, e5 is the standard central strike — fights for d4, opens lines for the dark-square bishop on g7. Without e5, the KID is just a passive setup. After e5, plan Nbd7 + a5 + Nh5 — the kingside attack.",
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


# ────────────────────────────────────────────────────────────────────
# Slav Defense (color=black) — 1.d4 d5 2.c4 c6
# Main: 3.Nf3 Nf6 4.Nc3
# Branches: 4...dxc4 (Slav accepted), 4...e6 (Semi-Slav),
#           4...a6 (Chebanenko)
# We teach the main: 4...dxc4 5.a4 Bf5 (Classical Slav)
# ────────────────────────────────────────────────────────────────────
slav_defense_tree = {
    "d4": {
        "idea_opponent": "White takes the center.",
        "next": "d5",
        "right_feedback": "d5 — meet White's pawn with your own.",
        "responses": {
            "c4": {
                "name": "Queen's Gambit territory",
                "idea_opponent": "White offers the gambit.",
                "next": "c6",
                "hint": "Support d5 with the c-pawn instead of e6 (which would block your light-square bishop).",
                "right_feedback": "c6 — the Slav. Keeps the light-square bishop's diagonal free.",
                "wrong_feedback": "In the Slav Defense, c6 is the defining move — support d5 with the c-pawn so your light-square bishop can develop to f5 or g4 (unlike the QGD where e6 traps it). Playing e6 instead leads to the QGD, a completely different setup.",
                "responses": {
                    "Nf3": {
                        "name": "Slav — Main",
                        "idea_opponent": "White develops, prepares to deal with the Slav structure.",
                        "next": "Nf6",
                        "right_feedback": "Nf6 — develop, attack e4-ideas.",
                        "responses": {
                            "Nc3": {
                                "name": "Slav — Main with Nc3",
                                "idea_opponent": "White develops, presses on d5.",
                                "next": "dxc4",
                                "hint": "Take the pawn, plan to develop the light-square bishop to f5 next.",
                                "right_feedback": "dxc4 — accept the gambit. White will play a4 to stop ...b5, then you develop with Bf5.",
                                "wrong_feedback": "In the Slav Defense, dxc4 is the principled main line — the whole point of c6 was to enable this capture while keeping the light-square bishop free. After dxc4 a4 Bf5, your bishop is OUTSIDE the pawn chain — the Slav's biggest advantage over the QGD.",
                                "responses": {}
                            }
                        }
                    }
                }
            }
        }
    }
}


# ────────────────────────────────────────────────────────────────────
# English Opening (color=white) — 1.c4
# Main lines: 1...e5 (Reversed Sicilian), 1...c5 (Symmetrical),
#             1...Nf6 (Indian setup), 1...e6 / 1...c6 (transposing)
# We teach the Reversed Sicilian main: 1.c4 e5 2.Nc3 Nf6 3.g3 Bb4
# ────────────────────────────────────────────────────────────────────
english_opening_tree = {
    "c4": {
        "idea": "Take queenside space, fight for d5 from the flank.",
        "next": "Nc3",
        "hint": "Develop the knight, fight for d5.",
        "right_feedback": "Nc3 — develops, controls d5.",
        "responses": {
            "e5": {
                "name": "English — Reversed Sicilian",
                "idea_opponent": "Black plays in classical style — Sicilian Defense with colors reversed and a tempo more for you.",
                "next": "Nc3",
                "right_feedback": "Nc3 — develop, fight for d5.",
                "responses": {
                    "Nf6": {
                        "name": "English — Reversed Sicilian, main",
                        "idea_opponent": "Black develops, attacks e4 indirectly.",
                        "next": "g3",
                        "hint": "Fianchetto the bishop — the English's signature move.",
                        "right_feedback": "g3 — prepares Bg2, the long-diagonal pressure that defines the English.",
                        "wrong_feedback": "In the English Opening, g3 is the signature move — the fianchetto puts your bishop on g2 where it pressures d5 and e4 along the long diagonal. Playing Nf3 first is OK but the fianchetto is what makes the English distinct from the Reti or other 1.Nf3 systems.",
                        "responses": {
                            "Nc6": {
                                "name": "English — Reversed Sicilian developed",
                                "idea_opponent": "Black develops naturally.",
                                "next": "Bg2",
                                "right_feedback": "Bg2 — bishop on the long diagonal, eyes d5 and e4.",
                                "responses": {}
                            }
                        }
                    }
                }
            },
            "Nf6": {
                "name": "English — Indian setup",
                "idea_opponent": "Black flexible, eyes the center.",
                "next": "Nc3",
                "right_feedback": "Nc3 — develop, fight for d5.",
                "responses": {
                    "g6": {
                        "name": "English vs KID setup",
                        "idea_opponent": "Black plans the fianchetto setup.",
                        "next": "g3",
                        "right_feedback": "g3 — mirror the fianchetto. The English's symmetric setup is solid and flexible.",
                        "responses": {}
                    }
                }
            },
            "c5": {
                "name": "Symmetrical English",
                "idea_opponent": "Black mirrors — symmetrical, drawish but rich.",
                "next": "Nc3",
                "right_feedback": "Nc3 — develop. The Symmetrical English is positional; play patiently.",
                "responses": {}
            }
        }
    }
}


def main():
    path = os.path.join(os.path.dirname(__file__), '..', 'data', 'opening_curriculum.json')
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    updates = [
        ('french_defense', french_defense_tree),
        ('queens_gambit', queens_gambit_tree),
        ('kings_indian_defense', kings_indian_defense_tree),
        ('slav_defense', slav_defense_tree),
        ('english_opening', english_opening_tree),
    ]
    for key, tree in updates:
        print(f'Extending {key} tree...')
        data[key]['tree'] = tree

    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print()
    print(f'Total openings: {len(data)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
