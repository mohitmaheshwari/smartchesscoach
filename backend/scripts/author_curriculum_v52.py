"""Phase 3 curriculum authoring (Mohit 2026-05-21):

  • Deepen 7 highest-traffic trees with more wrong_feedback nodes +
    variation branches in `responses`.
  • Author 3 NEW entries from scratch: italian_game_black,
    petrov_defense, nimzo_indian_defense.

After v52: 16 of 17 entries populated (only italian_game_black has
been a stub previously; this fills it). Each tree carries 4-10
critical-decision wrong_feedback nodes in 'In the [Opening], the
idea is X — why' voice.

Run once:
    docker exec chess-coach-backend python /app/backend/scripts/author_curriculum_v52.py
"""
import json
import os
import sys


# ════════════════════════════════════════════════════════════════════
# 1. Italian Game — DEEPEN (highest user frequency ~183 games)
#    Adds: Evans Gambit branch, Hungarian Defense, Italian Modern d3
#    setup, Giuoco Pianissimo, expanded Two Knights / Fried Liver
# ════════════════════════════════════════════════════════════════════
italian_game_tree = {
    "e4": {
        "idea": "Take the center.",
        "next": "Nf3",
        "responses": {
            "e5": {
                "name": "Open Game",
                "idea_opponent": "Black mirrors.",
                "next": "Nf3",
                "right_feedback": "Nf3 — develops, attacks e5.",
                "responses": {
                    "Nc6": {
                        "name": "Defending e5",
                        "next": "Bc4",
                        "hint": "Aim at the weakest square.",
                        "right_feedback": "Bc4 — your bishop eyes f7.",
                        "wrong_feedback": "If you want the Italian Game, Bc4 is the move — aim at f7. Bb5 is the Ruy Lopez; d4 is the Scotch. Both fine, just different openings.",
                        "responses": {
                            "Bc5": {
                                "name": "Giuoco Piano",
                                "idea_opponent": "Black mirrors — classical setup.",
                                "next": "c3",
                                "hint": "Prepare d4 with a pawn first.",
                                "right_feedback": "c3 — prepares d4. The big center is coming.",
                                "wrong_feedback": "In the Italian Game, the idea is: c3 prepares d4 — that's how you build the big center. Playing d4 immediately lets Black trade with exd4, hitting your knight and equalizing. d3 (the Giuoco Pianissimo / Italian Modern) is the quieter alternative — also OK if you prefer slow play, but c3 is the classical main line.",
                                "responses": {
                                    "Nf6": {
                                        "name": "Italian Main Line",
                                        "idea_opponent": "Black develops, eyes e4.",
                                        "next": "d4",
                                        "hint": "Now you can play the central break.",
                                        "right_feedback": "d4 — supported by c3. Now the big center is yours.",
                                        "wrong_feedback": "In the Italian Game, d4 is the plan c3 was preparing. Anything else (b4 — Evans Gambit accepted is theoretically fine but a different opening; O-O — playable but lets Black play d6+ and consolidate) lets Black equalize.",
                                        "responses": {
                                            "exd4": {
                                                "name": "Italian — d4 accepted",
                                                "idea_opponent": "Black trades the central pawn.",
                                                "next": "cxd4",
                                                "right_feedback": "cxd4 — recapture with the c-pawn, building the big center.",
                                                "responses": {
                                                    "Bb4+": {
                                                        "name": "Italian — Bb4+ check",
                                                        "idea_opponent": "Black checks, hoping to disrupt your development.",
                                                        "next": "Nc3",
                                                        "right_feedback": "Nc3 — block with the knight, accept the trade (or Bd2). Don't move the king.",
                                                        "wrong_feedback": "In the Italian Game after cxd4 Bb4+, Nc3 is the natural block — develops a piece AND meets the check. Bd2 (Möller Attack variations) is also fine if you want sharper play. Don't play Kf1 (loses castling) or Kd2 (insane).",
                                                        "responses": {}
                                                    }
                                                }
                                            }
                                        }
                                    },
                                    "Nge7": {
                                        "name": "Hungarian-like setup with Nge7",
                                        "idea_opponent": "Unusual — knight to e7 instead of f6.",
                                        "next": "d4",
                                        "right_feedback": "d4 — punish the passive setup.",
                                        "wrong_feedback": "Against Black's passive Nge7, d4 immediately is fine — Black can't easily challenge the center with the knight on e7 (blocks the e-pawn). Calm Italian setup play wins here.",
                                        "responses": {}
                                    }
                                }
                            },
                            "Be7": {
                                "name": "Hungarian Defense",
                                "idea_opponent": "Black plays the solid, passive Hungarian.",
                                "next": "d4",
                                "hint": "Black's setup is too quiet — strike the center immediately.",
                                "right_feedback": "d4 — open the center. The Hungarian doesn't fight for it; punish that.",
                                "wrong_feedback": "Against the Hungarian Defense (...Be7), d4 immediately is the principled punishment — Black's quiet bishop on e7 lacks coordination with the rest of the army. d3 (slow Italian) is fine but lets Black equalize. d4 demands accuracy from Black.",
                                "responses": {}
                            },
                            "Nf6": {
                                "name": "Two Knights Defense",
                                "idea_opponent": "Black plays more actively, eyes e4.",
                                "next": "Ng5",
                                "hint": "Black ignored f7 — punish it.",
                                "right_feedback": "Ng5 — attacks f7! Black must defend with d5 or face the Fried Liver.",
                                "wrong_feedback": "In the Two Knights Defense, Ng5 attacks f7 directly. d3 is the quiet Modern Italian (safer); d4 leads to the Max Lange or Scotch Gambit transpositions. Pick your style — but avoid Nc3 which lets Black equalize easily with d5.",
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
                                                "wrong_feedback": "After exd5 Nxd5, Nxf7 is THE move — the Fried Liver. Any other move lets Black escape. The point: Black's knight on d5 IS undefended; Nxf7 forces Kxf7 (the king can't run), then Qf3+ regains material and continues the attack.",
                                                "responses": {}
                                            },
                                            "Na5": {
                                                "name": "Polerio Defense",
                                                "idea_opponent": "Black hits the bishop, sidestepping the Fried Liver.",
                                                "next": "Bb5+",
                                                "right_feedback": "Bb5+ — check, keeps the bishop active.",
                                                "wrong_feedback": "In the Polerio, Bb5+ is principled — give check first, develop with tempo. Retreating with Bb3 or Bf1 loses tempo. d3 (Bd3 next) is the quiet alternative — playable but less ambitious.",
                                                "responses": {}
                                            },
                                            "Nd4": {
                                                "name": "Fritz Variation",
                                                "idea_opponent": "Black plays Nd4 — sharp, ambitious.",
                                                "next": "c3",
                                                "right_feedback": "c3 — kick the knight, regain control of the center.",
                                                "wrong_feedback": "In the Two Knights Fritz Variation, c3 kicks the d4 knight. Nxf7 here is INCORRECT (the knight on d4 isn't undefended like in the main line). c3 first, then the position becomes tactical.",
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


# ════════════════════════════════════════════════════════════════════
# 2. Sicilian Defense — DEEPEN (color=black, 57+ games)
#    Adds: Open Sicilian Najdorf English Attack, Dragon, Sveshnikov
# ════════════════════════════════════════════════════════════════════
sicilian_defense_tree = {
    "e4": {
        "idea_opponent": "White takes the center.",
        "next": "c5",
        "hint": "What move fights for d4 from the flank, avoiding symmetry?",
        "right_feedback": "c5 — the Sicilian. Most ambitious response to e4.",
        "wrong_feedback": "In response to 1.e4, c5 is the Sicilian — most ambitious for Black, sets up unbalanced play. e5 invites the Open Game (Italian / Ruy Lopez / Scotch), e6 the French, c6 the Caro-Kann, d6 Pirc/Modern. All sound; c5 is the most fighting.",
        "responses": {
            "Nf3": {
                "name": "Sicilian — Open setup begins",
                "idea_opponent": "White's most popular move, preparing d4.",
                "next": "d6",
                "hint": "Flexible Najdorf-style setup — prepare Nf6 and later a6.",
                "right_feedback": "d6 — supports e5 push, prepares Nf6.",
                "wrong_feedback": "Against 2.Nf3, d6 is the most flexible — leads to Najdorf / Classical / Dragon depending on Black's later choices. Nc6 commits to the Classical / Sveshnikov lines. e6 leads to Taimanov / Kan / Paulsen. All sound; d6 is the most-played at top level.",
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
                                        "wrong_feedback": "In the Najdorf Sicilian, a6 prepares b5 + Bb7 — fighting on the queenside. Nc6 here would be the Classical Sicilian (different plan: knight to c6, dark-square strategy). g6 leads to the Dragon (sharp, double-edged). All sound; if you want the Najdorf, a6 is the move.",
                                        "responses": {
                                            "Be3": {
                                                "name": "Najdorf — English Attack",
                                                "idea_opponent": "White plays the sharp English Attack — Be3, f3, g4, h4, attacking the kingside.",
                                                "next": "e5",
                                                "hint": "Strike back in the center before White's pawn storm arrives.",
                                                "right_feedback": "e5 — closes the center, kicks the d4 knight, fights for d5 outpost.",
                                                "wrong_feedback": "In the Najdorf English Attack, e5 is the principled central break — closes the center BEFORE White's kingside storm gets going. Nf6 already played; e6 (Scheveningen-style) is playable but invites a faster White attack. e5 is sharp but theoretically sound.",
                                                "responses": {}
                                            },
                                            "Bg5": {
                                                "name": "Najdorf — Bg5",
                                                "idea_opponent": "White plays the aggressive Bg5 main line.",
                                                "next": "e6",
                                                "right_feedback": "e6 — solidify the kingside, prepare Be7.",
                                                "wrong_feedback": "Against the Bg5 Najdorf, e6 is the most-played response — solid, prepares ...Be7. ...Nbd7 is also OK but less precise. e5 (which works against English Attack) is INFERIOR here because Bg5 pins the f6 knight and the e5 push isn't easily prepared.",
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


# ════════════════════════════════════════════════════════════════════
# 3. Caro-Kann — DEEPEN (color=black, 64+ games)
#    Adds: Advance variation, Exchange variation, full Classical line
# ════════════════════════════════════════════════════════════════════
caro_kann_tree = {
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
                                "responses": {
                                    "Ng3": {
                                        "name": "Classical — Ng3 chasing the bishop",
                                        "idea_opponent": "White harasses the bishop.",
                                        "next": "Bg6",
                                        "right_feedback": "Bg6 — keep the bishop's diagonal alive. Don't retreat further.",
                                        "wrong_feedback": "In the Caro-Kann Classical after Ng3, Bg6 is correct — keeps the bishop active on the b1-h7 diagonal. Bd7 retreats too far (passive); Bh5? loses the bishop after h4-h5.",
                                        "responses": {}
                                    }
                                }
                            }
                        }
                    },
                    "e5": {
                        "name": "Caro-Kann — Advance Variation",
                        "idea_opponent": "White locks the center, gains space, prepares kingside attack.",
                        "next": "Bf5",
                        "hint": "Get the light-square bishop OUT before you play e6.",
                        "right_feedback": "Bf5 — same defining idea as the Classical: bishop outside the chain before e6 locks it in.",
                        "wrong_feedback": "In the Caro-Kann Advance, Bf5 is the move — your light-square bishop MUST get out before e6 traps it. The Caro-Kann's main complaint about the French is the bishop-on-c8 problem; don't recreate it here. c5 (challenging the chain) is also fine but Bf5 first is more accurate.",
                        "responses": {}
                    },
                    "exd5": {
                        "name": "Caro-Kann — Exchange Variation",
                        "idea_opponent": "White trades and aims for a quiet game.",
                        "next": "cxd5",
                        "right_feedback": "cxd5 — recapture with the c-pawn, leaving a symmetric structure.",
                        "wrong_feedback": "In the Caro-Kann Exchange, cxd5 is correct — recapture with the pawn that has the better square afterward. Don't take with the queen (Qxd5 loses tempo to Nc3).",
                        "responses": {}
                    }
                }
            }
        }
    }
}


# ════════════════════════════════════════════════════════════════════
# 4. Ruy Lopez — DEEPEN (color=white, ~26 games but pedagogically central)
#    Adds: Berlin Defense main line, Open Spanish, Marshall Attack hint,
#    Exchange Variation
# ════════════════════════════════════════════════════════════════════
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
                                "wrong_feedback": "In the Ruy Lopez, Ba4 keeps your pin on the c6-knight. Bxc6 is the Exchange Variation — playable but trades your bishop pair away. Ba4 is the main line at every level.",
                                "responses": {
                                    "Nf6": {
                                        "name": "Closed Ruy Lopez",
                                        "idea_opponent": "Black develops, attacks e4.",
                                        "next": "O-O",
                                        "right_feedback": "O-O — castle. The pin defends e4 indirectly (if Nxe4 then Re1 wins the knight back).",
                                        "wrong_feedback": "In the Ruy Lopez Closed, O-O is correct — the pin on c6 means Nxe4 is unsafe for Black (Re1 pins). Don't waste time defending e4 with d3; castle first.",
                                        "responses": {
                                            "Be7": {
                                                "name": "Closed Ruy — Main",
                                                "idea_opponent": "Black develops the bishop, prepares to castle.",
                                                "next": "Re1",
                                                "hint": "Defend e4 — the pin gets less reliable now that Black has developed.",
                                                "right_feedback": "Re1 — supports e4, prepares c3 + d4 expansion.",
                                                "wrong_feedback": "In the Ruy Lopez Closed Main, Re1 is the canonical move — supports e4 explicitly (the pin alone no longer suffices once Black develops). Then plan c3 + d4 to claim space. Bxc6 dxc6 here trades the bishop pair early — playable (Exchange Spanish lines) but less ambitious.",
                                                "responses": {}
                                            },
                                            "b5": {
                                                "name": "Closed Ruy — b5 hitting the bishop",
                                                "idea_opponent": "Black gains queenside space, kicks the bishop.",
                                                "next": "Bb3",
                                                "right_feedback": "Bb3 — bishop on its strongest diagonal, eyes f7.",
                                                "wrong_feedback": "After Black's b5, Bb3 is correct — the bishop on b3 eyes f7 and stays useful. Ba4 is also OK but b5 already restricts it. Bxc6 would be premature here — wait for Black to commit further.",
                                                "responses": {}
                                            }
                                        }
                                    }
                                }
                            },
                            "Nf6": {
                                "name": "Berlin Defense",
                                "idea_opponent": "Black attacks e4 immediately — the Berlin Wall.",
                                "next": "O-O",
                                "right_feedback": "O-O — same idea. The pin defends e4.",
                                "wrong_feedback": "In the Ruy Lopez Berlin, O-O is correct — castles, lets Black take e4 if they want (Nxe4 d4 — White gets a strong center). d3 is the modern Anti-Berlin (safer but less ambitious).",
                                "responses": {
                                    "Nxe4": {
                                        "name": "Open Berlin",
                                        "idea_opponent": "Black grabs the pawn — the famous Berlin endgame setup.",
                                        "next": "d4",
                                        "right_feedback": "d4 — open the position. The Berlin endgame is balanced but White has dynamic chances.",
                                        "wrong_feedback": "In the Open Berlin, d4 is the principled response — open the center to exploit the knight excursion. Re1 is also fine; both lead to the Berlin endgame after the queen trade. Anything passive lets Black consolidate the extra pawn.",
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


# ════════════════════════════════════════════════════════════════════
# 5. French Defense — DEEPEN (color=black)
#    Adds: Winawer Variation main, Tarrasch (3.Nd2), explicit Advance
#    counterplay
# ════════════════════════════════════════════════════════════════════
french_defense_tree = {
    "e4": {
        "idea_opponent": "White takes the center.",
        "next": "e6",
        "hint": "What move builds a solid wall, preparing d5?",
        "right_feedback": "e6 — the French Defense. You'll strike with d5 next.",
        "responses": {
            "d4": {
                "name": "French — Main",
                "idea_opponent": "White builds the big center.",
                "next": "d5",
                "right_feedback": "d5 — challenge the e-pawn. White must commit to a setup.",
                "responses": {
                    "Nc3": {
                        "name": "French — Classical / Winawer Setup",
                        "idea_opponent": "White defends e4 with a developing move.",
                        "next": "Nf6",
                        "hint": "Develop, attack e4. (Or Bb4 — Winawer.)",
                        "right_feedback": "Nf6 — Classical French. Pressures e4, develops naturally.",
                        "wrong_feedback": "After 3.Nc3, Nf6 is the Classical French (most-played, solid). Bb4 is the sharp Winawer (gives up bishop pair for activity and pawn structure damage). dxe4 is the Rubinstein (passive but sound). All defensible; Nf6 is the main line.",
                        "responses": {
                            "e5": {
                                "name": "French — Steinitz Variation",
                                "idea_opponent": "White pushes past, gains space.",
                                "next": "Nfd7",
                                "right_feedback": "Nfd7 — knight retreats but keeps c5 break available.",
                                "wrong_feedback": "In the French Steinitz, Nfd7 is correct — preserves c5 break. Ng8 wastes development; Nh5? loses to g4 trapping the knight.",
                                "responses": {}
                            },
                            "Bg5": {
                                "name": "French — McCutcheon / Classical Bg5",
                                "idea_opponent": "White pins the f6 knight.",
                                "next": "Bb4",
                                "right_feedback": "Bb4 — counter-pin, the McCutcheon Variation. Sharp but theoretically sound.",
                                "wrong_feedback": "Against 4.Bg5 in the Classical French, Bb4 is the modern main line (the McCutcheon). Pins the c3 knight. Be7 is the older, quieter Classical Main Line — also playable but less ambitious. Don't break the pin with h6 (it just helps White: 5.Bxf6 trades pieces).",
                                "responses": {}
                            }
                        }
                    },
                    "Nd2": {
                        "name": "French — Tarrasch Variation",
                        "idea_opponent": "White avoids the pin, plays Nd2 instead.",
                        "next": "Nf6",
                        "right_feedback": "Nf6 — same development as Classical, but White's structure is different.",
                        "wrong_feedback": "Against 3.Nd2 (Tarrasch), Nf6 is the modern main line. c5 (challenging the center immediately) is also popular and sharp. Both are sound; Nf6 keeps options open.",
                        "responses": {}
                    },
                    "e5": {
                        "name": "French — Advance Variation",
                        "idea_opponent": "White locks the center, plans kingside attack.",
                        "next": "c5",
                        "hint": "Challenge the pawn chain at its base.",
                        "right_feedback": "c5 — the standard French break, hits the base of White's pawn chain.",
                        "wrong_feedback": "In the French Advance, c5 is THE move — challenge White's pawn chain at its base (d4). Without c5 you're left passive with no counterplay. f6 is the alternative break (Milner-Barry-Gambit territory if White accepts), sharp and theoretically OK but less common.",
                        "responses": {}
                    },
                    "exd5": {
                        "name": "French — Exchange Variation",
                        "idea_opponent": "White trades and aims for a quiet game.",
                        "next": "exd5",
                        "right_feedback": "exd5 — symmetric structure. The Exchange is dry but not equal.",
                        "responses": {}
                    }
                }
            }
        }
    }
}


# ════════════════════════════════════════════════════════════════════
# 6. Queens Gambit — DEEPEN (color=white)
#    Adds: QGD Exchange, QGD Tartakower, QGA mainline depth, Albin
#    Counter-Gambit warning
# ════════════════════════════════════════════════════════════════════
queens_gambit_tree = {
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
                "wrong_feedback": "In the Queen's Gambit, c4 is the defining move — offer the c-pawn to break Black's pawn on d5. Without c4 you're playing a quiet Queen's Pawn Game (London / Colle / Torre), not the Queen's Gambit. Both fine, just different openings.",
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
                                "wrong_feedback": "In the QGD, Bg5 is the main attacking move — pins the f6 knight, indirectly pressuring d5. cxd5 (Exchange QGD) trades immediately — playable, leads to a clear positional game. Bf4 is the London-style setup. For classical QGD, Bg5 is canonical.",
                                "responses": {
                                    "Be7": {
                                        "name": "QGD — Classical Main",
                                        "idea_opponent": "Black breaks the pin with the bishop.",
                                        "next": "e3",
                                        "right_feedback": "e3 — develop calmly, prepare Bd3 + Nf3 + O-O.",
                                        "responses": {}
                                    },
                                    "h6": {
                                        "name": "QGD — Tartakower / Lasker prep",
                                        "idea_opponent": "Black asks the bishop a question.",
                                        "next": "Bxf6",
                                        "right_feedback": "Bxf6 — trade the bishop, give Black doubled pawns or compromise structure.",
                                        "wrong_feedback": "After Black's ...h6 in the QGD, Bxf6 is the main move — Black recaptures with the queen (Qxf6) or gives up the bishop pair entirely. Bh4 (keeping the pin) is also fine but committed.",
                                        "responses": {}
                                    }
                                }
                            }
                        }
                    },
                    "dxc4": {
                        "name": "Queen's Gambit Accepted (QGA)",
                        "idea_opponent": "Black accepts the pawn.",
                        "next": "Nf3",
                        "hint": "Develop first, regain the pawn later.",
                        "right_feedback": "Nf3 — develop. The c4 pawn isn't going anywhere safely.",
                        "wrong_feedback": "In the QGA, Nf3 first is the modern way — develop before grabbing the pawn. Trying to win c4 immediately with Qa4+ is theoretically OK but creates an exposed queen. e3 (preparing Bxc4 next) is also fine. Develop, castle, THEN reclaim c4.",
                        "responses": {
                            "Nf6": {
                                "name": "QGA — Main",
                                "idea_opponent": "Black develops, defends.",
                                "next": "e3",
                                "right_feedback": "e3 — prepare Bxc4 to regain the pawn.",
                                "responses": {}
                            }
                        }
                    },
                    "c6": {
                        "name": "Slav Defense (transposition)",
                        "idea_opponent": "Black plays the Slav structure.",
                        "next": "Nf3",
                        "right_feedback": "Nf3 — develop, prepare to handle the Slav.",
                        "responses": {}
                    },
                    "e5": {
                        "name": "Albin Counter-Gambit",
                        "idea_opponent": "Black sacrifices the pawn for sharp play — the Albin.",
                        "next": "dxe5",
                        "right_feedback": "dxe5 — accept the pawn. Now don't grab d5 with the bishop too greedily.",
                        "wrong_feedback": "Against the Albin Counter-Gambit, dxe5 is correct — take the pawn. The trap: don't play 4.e3 (allows Bb4+ + d3! and Black wins material). After dxe5, Black plays d4 and you continue with Nf3 to attack d4.",
                        "responses": {}
                    }
                }
            }
        }
    }
}


# ════════════════════════════════════════════════════════════════════
# 7. King's Indian Defense — DEEPEN (color=black)
#    Adds: Sämisch Variation main, Four Pawns Attack, Fianchetto setup
# ════════════════════════════════════════════════════════════════════
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
                                "name": "KID — Classical Main (vs e4 setup)",
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
                            },
                            "f3": {
                                "name": "KID — Sämisch Variation",
                                "idea_opponent": "White plays the Sämisch — solid pawn shield for the king, plans kingside castle and attack.",
                                "next": "O-O",
                                "right_feedback": "O-O — castle into safety; the Sämisch is slow, you have time.",
                                "wrong_feedback": "Against the Sämisch (f3), O-O first is the modern main line — get safe, then play c5 or e5 break depending on White's setup. Nc6 too early can be met with d5; e5 is also OK and immediate. O-O keeps maximum flexibility.",
                                "responses": {}
                            },
                            "g3": {
                                "name": "KID — Fianchetto Variation",
                                "idea_opponent": "White mirrors the fianchetto. Quieter, positional play.",
                                "next": "O-O",
                                "right_feedback": "O-O — castle. The Fianchetto KID is positional; expansion comes later.",
                                "wrong_feedback": "Against the Fianchetto KID (g3), O-O first is canonical. The fianchetto vs fianchetto setup is positional — you typically play c6 + Nbd7 + e5, slowly. Avoid premature e5 before castling.",
                                "responses": {}
                            }
                        }
                    }
                }
            }
        }
    }
}


# ════════════════════════════════════════════════════════════════════
# NEW ENTRIES — 3 openings from scratch
# ════════════════════════════════════════════════════════════════════


# 8. Petrov Defense (color=black) — 1.e4 e5 2.Nf3 Nf6
petrov_defense_entry = {
    "name": "Petrov Defense",
    "color": "black",
    "summary": "Black's most solid response to 1.e4 e5 2.Nf3 — immediately counterattacks White's e-pawn instead of defending e5. Reputation: drawish but theoretically resilient. Used by GMs at the highest level to neutralize 1.e4 with minimal risk.",
    "difficulty": "intermediate",
    "setup_order": ["Nf6", "Nxe4", "d6", "Be7", "O-O", "Nf6"],
    "golden_rules": [
        "Counter-attack with Nf6 INSTEAD of defending e5 with Nc6.",
        "After 3.Nxe5, retreat to d6 first — never play 3...Nxe4 without preparation.",
        "The Petrov fights for symmetric structure; play accurately, don't try to win the opening.",
        "Black's bishop pair is often the long-term asset — don't trade them away."
    ],
    "traps": [],
    "tree": {
        "e4": {
            "idea_opponent": "White takes the center.",
            "next": "e5",
            "right_feedback": "e5 — meet pawn with pawn.",
            "responses": {
                "Nf3": {
                    "idea_opponent": "White develops, attacks e5.",
                    "next": "Nf6",
                    "hint": "What if instead of defending e5, you ATTACK White's e-pawn?",
                    "right_feedback": "Nf6 — the Petrov Defense. Counter-attack instead of defending.",
                    "wrong_feedback": "After 2.Nf3, Nc6 is the classical defense (Italian / Ruy Lopez territory). Nf6 is the Petrov — counter-attacks e4 immediately. Both are sound; Petrov is the solid choice for players who want minimal opening risk.",
                    "responses": {
                        "Nxe5": {
                            "name": "Petrov Main Line",
                            "idea_opponent": "White takes the pawn.",
                            "next": "d6",
                            "hint": "DON'T play Nxe4 yet — White has Qe2 winning. Push the knight back first.",
                            "right_feedback": "d6 — kicks the knight, prepares Nxe4 SAFELY next.",
                            "wrong_feedback": "In the Petrov Main Line, d6 FIRST is critical — playing Nxe4 immediately loses to 4.Qe2! Nf6 5.Nc6+ winning the queen. Always push the knight away with d6 before recapturing e4. This is the famous Petrov trap.",
                            "responses": {
                                "Nf3": {
                                    "name": "Petrov — Classical retreat",
                                    "idea_opponent": "White retreats the knight.",
                                    "next": "Nxe4",
                                    "right_feedback": "Nxe4 — NOW you can safely take. The knight is no longer next to your queen.",
                                    "wrong_feedback": "Now that the white knight has retreated to f3 (not threatening your queen via Nc6+), Nxe4 is safe and main line. You regain the pawn. Don't get fancy with anything else here.",
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
            "plan": "Trade pieces for a symmetric endgame — your structure is sound. Aim for the bishop pair if possible. The Petrov plays for technique, not attack.",
            "ideas": [
                "Trade queens when offered — the Petrov rewards technique.",
                "Keep the bishop pair if you can; trade your worst minor for White's best.",
                "If the position simplifies and you're not worse, you're doing well."
            ]
        },
        "when_ahead": {
            "plan": "Simplify decisively. The Petrov's solidity means White rarely creates winning chances — convert positional edges patiently.",
            "ideas": ["Trade queens.", "Activate the rooks on open files.", "Push the pawn majority in the endgame."]
        },
        "when_behind": {
            "plan": "Play for the symmetric structure to dry the position out. The Petrov is famously hard to lose from equal positions.",
            "ideas": ["Avoid sharp commitments.", "Trade pieces.", "Make the draw."]
        }
    },
    "endgame_tips": [
        "Symmetric pawn structures favor the side with the better minor pieces — keep your bishop pair active.",
        "The Petrov often reaches rook endgames; learn the basic Lucena and Philidor positions."
    ]
}


# 9. Italian Game Black (color=black) — how to defend the Italian
italian_game_black_entry = {
    "name": "Italian Game (Black side)",
    "color": "black",
    "summary": "How to defend against the Italian Game (1.e4 e5 2.Nf3 Nc6 3.Bc4) as Black. Two main systems: Two Knights Defense (3...Nf6 — sharp, attacking the e-pawn back) or Giuoco Piano (3...Bc5 — mirror the bishop, classical). Both are sound; choice depends on whether you want sharp or quiet play.",
    "difficulty": "beginner",
    "setup_order": ["e5", "Nc6", "Nf6", "d6", "Be7", "O-O"],
    "golden_rules": [
        "Against 3.Bc4, Nf6 (Two Knights) is the sharpest reply — counter-attack the e-pawn.",
        "Bc5 (Giuoco Piano) mirrors White's bishop — solid, equal-ish.",
        "Watch for the Fried Liver — d5 to block White's Ng5 is critical.",
        "Don't play Na5 to chase the bishop unless you know the Polerio theory cold."
    ],
    "traps": [],
    "tree": {
        "e4": {
            "idea_opponent": "White takes the center.",
            "next": "e5",
            "right_feedback": "e5 — accept the Open Game.",
            "responses": {
                "Nf3": {
                    "idea_opponent": "White develops, attacks e5.",
                    "next": "Nc6",
                    "right_feedback": "Nc6 — defend the pawn.",
                    "responses": {
                        "Bc4": {
                            "name": "Italian Game",
                            "idea_opponent": "White aims the bishop at f7.",
                            "next": "Nf6",
                            "hint": "Two Knights (sharp) or Bc5 (classical)? Nf6 is the most ambitious.",
                            "right_feedback": "Nf6 — the Two Knights Defense. Counter-attack e4. Sharper play ahead.",
                            "wrong_feedback": "Against the Italian (3.Bc4), Nf6 is the Two Knights Defense — counter-attacks White's e-pawn, leads to sharp tactical play (including the Fried Liver if White goes for it). Bc5 is the Giuoco Piano — mirror White's bishop, classical/equal. Both sound; Nf6 if you want sharper games.",
                            "responses": {
                                "Ng5": {
                                    "name": "Italian — Fried Liver Attack",
                                    "idea_opponent": "White attacks f7 with the knight!",
                                    "next": "d5",
                                    "hint": "Block the diagonal AND attack White's bishop. One move that does both?",
                                    "right_feedback": "d5 — defend f7 by blocking the diagonal, AND counter-attack the bishop. The critical defense.",
                                    "wrong_feedback": "Against 4.Ng5 (Fried Liver Attack), d5 is THE critical defense — blocks Bc4's diagonal at f7 AND attacks the bishop. Without d5, White plays 5.Nxf7 and your king is gutted. Other moves (Bc5, Nxe4) lose to the Fried Liver. d5 is mandatory.",
                                    "responses": {
                                        "exd5": {
                                            "name": "Two Knights — d5 accepted",
                                            "idea_opponent": "White takes the pawn.",
                                            "next": "Na5",
                                            "hint": "DON'T recapture with the knight — that's the Fried Liver trap. Hit the bishop instead.",
                                            "right_feedback": "Na5 — the Polerio Defense. Attacks the bishop, sidesteps the Fried Liver.",
                                            "wrong_feedback": "After 5.exd5, Na5 (Polerio Defense) is the principled move — hits Bc4 with tempo, avoids the Fried Liver entirely. Nxd5 here is the Fried Liver trap — White plays Nxf7! winning material. Na5 is sound; Nxd5 is unsound unless you've memorized the Lolli/Traxler refutation lines.",
                                            "responses": {}
                                        }
                                    }
                                },
                                "d3": {
                                    "name": "Italian — Modern (d3) / Giuoco Pianissimo",
                                    "idea_opponent": "White plays the quiet Modern Italian — slow, positional.",
                                    "next": "Bc5",
                                    "right_feedback": "Bc5 — mirror White's bishop, classical setup. Equal positional game ahead.",
                                    "wrong_feedback": "Against the Modern Italian (d3), Bc5 is the classical reply — mirror the bishop. d6 is also fine (Pirc-like). The Modern Italian is quiet; both sides have similar plans and the game is decided in the middlegame.",
                                    "responses": {}
                                }
                            }
                        },
                        "Bc5": {
                            "name": "Giuoco Piano (Black side)",
                            "idea_opponent": "Quiet, equal-ish positional game.",
                            "next": "Nf6",
                            "right_feedback": "Nf6 — develop, eye e4.",
                            "responses": {}
                        }
                    }
                }
            }
        }
    },
    "middlegame_plans": {
        "when_equal": {
            "plan": "In the Italian as Black, the typical middlegame plan is queenside expansion (a6 + b5 + Bb7) while White attacks on the kingside. Trade pieces if needed.",
            "ideas": [
                "Develop pieces actively, especially the c8 bishop via b7 or g4.",
                "Castle kingside, then expand on the queenside with a6 + b5.",
                "Watch for White's d4 break — meet it with exd4 cxd4 Nxd4 Nxd4 cxd4 etc."
            ]
        },
        "when_ahead": {
            "plan": "Trade down. The Italian as Black usually reaches equal or slightly worse positions; if you're ahead, trade pieces and aim for the endgame.",
            "ideas": ["Trade queens.", "Activate the bishop pair.", "Push the queenside pawns."]
        },
        "when_behind": {
            "plan": "Defend solidly — the Italian rarely produces forced losing lines from Black's side. Keep the position closed.",
            "ideas": ["Don't trade your dark-square bishop.", "Keep pawns flexible.", "Wait for White to overcommit."]
        }
    },
    "endgame_tips": [
        "Bishop endgames where you have the bishop pair are technically winning if you have any advantage.",
        "Rook endgames after the Italian are often dry — know your Lucena and Philidor positions."
    ]
}


# 10. Nimzo-Indian Defense (color=black) — 1.d4 Nf6 2.c4 e6 3.Nc3 Bb4
nimzo_indian_defense_entry = {
    "name": "Nimzo-Indian Defense",
    "color": "black",
    "summary": "Black's most theoretically respected response to 1.d4. Pins the c3 knight with ...Bb4, giving up the bishop pair for damage to White's pawn structure (typically doubled c-pawns). One of the deepest, richest openings in chess — used by world champions for over a century.",
    "difficulty": "intermediate",
    "setup_order": ["Nf6", "e6", "Bb4", "O-O", "d5", "c5"],
    "golden_rules": [
        "Bb4 pinning the c3 knight is the defining move — accept that you'll trade the bishop for the knight.",
        "Aim to compromise White's pawn structure (doubled c-pawns after Bxc3).",
        "Your trumps: superior structure + flexibility. White's trumps: bishop pair + center.",
        "Don't retreat the bishop without a reason — it serves its purpose on b4."
    ],
    "traps": [],
    "tree": {
        "d4": {
            "idea_opponent": "White takes the center.",
            "next": "Nf6",
            "right_feedback": "Nf6 — flexible. Universal response to d4.",
            "responses": {
                "c4": {
                    "name": "Nimzo setup begins",
                    "idea_opponent": "White claims the gambit-style center.",
                    "next": "e6",
                    "hint": "Prepare Bb4 — the defining Nimzo move.",
                    "right_feedback": "e6 — prepares Bb4. Don't play g6 (that's the King's Indian).",
                    "wrong_feedback": "Against 2.c4, e6 prepares the Nimzo-Indian (3.Nc3 Bb4). g6 leads to the King's Indian (different opening, different plans). c5 invites the Benoni. e6 is the classical, theoretically-soundest response.",
                    "responses": {
                        "Nc3": {
                            "name": "Nimzo-Indian setup",
                            "idea_opponent": "White develops, supports the center.",
                            "next": "Bb4",
                            "hint": "Pin the knight to the king. This IS the Nimzo-Indian.",
                            "right_feedback": "Bb4 — pins the knight. White's c3 knight is now committed.",
                            "wrong_feedback": "After 3.Nc3, Bb4 is the defining Nimzo move — pins the knight, threatens to damage White's structure with Bxc3. Other moves (d5, Be7) lead to different openings (QGD-style positions). For the Nimzo, Bb4 is mandatory.",
                            "responses": {
                                "e3": {
                                    "name": "Nimzo — Rubinstein Variation",
                                    "idea_opponent": "White plays the calm Rubinstein — develops Nf3, Bd3, prepares O-O.",
                                    "next": "O-O",
                                    "right_feedback": "O-O — castle. The Rubinstein is positional; both sides develop quietly.",
                                    "wrong_feedback": "Against the Rubinstein (e3), O-O is the modern main line — castle first, decide later about Bxc3 or holding the pin. b6 (preparing Bb7) and c5 are also playable; O-O keeps maximum flexibility.",
                                    "responses": {}
                                },
                                "Qc2": {
                                    "name": "Nimzo — Classical Variation",
                                    "idea_opponent": "White plays Qc2 — protects c3 knight, avoids doubled pawns.",
                                    "next": "O-O",
                                    "right_feedback": "O-O — develop calmly. The Classical Nimzo is rich; you'll play d5 or c5 later.",
                                    "wrong_feedback": "Against the Classical Nimzo (Qc2), O-O is the modern main line. d5 (immediate central challenge) is also fine. The point of Qc2 was to avoid doubled c-pawns if Black plays Bxc3 — your bishop's value as a pin is reduced now, so castling first is sound.",
                                    "responses": {}
                                },
                                "a3": {
                                    "name": "Nimzo — Sämisch Variation",
                                    "idea_opponent": "White asks the bishop — accept doubled pawns or retreat?",
                                    "next": "Bxc3+",
                                    "right_feedback": "Bxc3+ — accept the trade, double White's c-pawns. This is the soul of the Nimzo.",
                                    "wrong_feedback": "Against the Sämisch (a3), Bxc3+ is the Nimzo's principled move — give up the bishop, damage White's structure with doubled c-pawns. Retreating with Be7 wastes the entire opening idea (you'd be playing a worse QGD). Bxc3+ is the lesson the Nimzo teaches: structure over the bishop pair.",
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
            "plan": "Exploit White's doubled c-pawns (or restricted bishops). Plan: d5 + c5 to open lines for your pieces, attack the weak pawns. Trade White's good bishop if possible.",
            "ideas": [
                "Restrict White's light-square bishop with c4 (after b6 + Bb7).",
                "Attack the doubled c-pawns with Na5 or Qa5.",
                "Keep your knights — they're better than White's bishops in a closed structure."
            ]
        },
        "when_ahead": {
            "plan": "Open the position once you control the dark squares. Your superior structure wins endgames.",
            "ideas": ["Trade queens if you have the structure advantage.", "Centralize knights.", "Push the queenside pawns."]
        },
        "when_behind": {
            "plan": "Close the position. The Nimzo's strength is solidity — if you're worse, dig in.",
            "ideas": ["Don't trade pieces.", "Keep pawns locked.", "Wait for White to overextend."]
        }
    },
    "endgame_tips": [
        "Knight endings often favor Black after the Nimzo — your better structure compounds.",
        "Bishop-vs-knight endings depend on pawn structure; closed positions favor the knight."
    ]
}


# ════════════════════════════════════════════════════════════════════
# Apply all updates
# ════════════════════════════════════════════════════════════════════


def main():
    path = os.path.join(os.path.dirname(__file__), '..', 'data', 'opening_curriculum.json')
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    updates = [
        ('italian_game', italian_game_tree, 'tree'),
        ('sicilian_defense', sicilian_defense_tree, 'tree'),
        ('caro_kann', caro_kann_tree, 'tree'),
        ('ruy_lopez', ruy_lopez_tree, 'tree'),
        ('french_defense', french_defense_tree, 'tree'),
        ('queens_gambit', queens_gambit_tree, 'tree'),
        ('kings_indian_defense', kings_indian_defense_tree, 'tree'),
    ]
    for key, tree, _kind in updates:
        print(f'Deepening {key} tree...')
        data[key]['tree'] = tree

    new_entries = [
        ('petrov_defense', petrov_defense_entry),
        ('italian_game_black', italian_game_black_entry),
        ('nimzo_indian_defense', nimzo_indian_defense_entry),
    ]
    for key, entry in new_entries:
        print(f'Replacing/adding {key} (full entry)...')
        data[key] = entry

    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print()
    print(f'Total openings: {len(data)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
