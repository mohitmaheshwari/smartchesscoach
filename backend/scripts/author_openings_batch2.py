"""Author Four Knights (White), Pirc/Classical (White), Alekhine (Black).

Same two-file, legality-validated pattern as author_opening_kings_gambit.py.
Color-aware tree validation:
  - white frame: root key = White's move; root.responses = Black replies.
  - black frame: root key = White's move; root.next = Black's reply;
    root.responses = White's 2nd moves.
Every non-root node: node['next'] = curriculum-side move, responses = opponent.
"""
import argparse, json, sys
import chess

CURRIC = "/app/backend/data/opening_curriculum.json"
SKILL = "/app/backend/data/coaching/skill_tree.json"

# ---------------------------------------------------------------- Four Knights
FOUR_KNIGHTS = {
    "name": "Four Knights Game",
    "color": "white",
    "summary": "1.e4 e5 2.Nf3 Nc6 3.Nc3 Nf6. Both sides bring both knights out — a calm, classical, very safe way to play 1.e4. Aim the bishop at b5 (Spanish-style), castle, and play a sound game with a tiny edge from the extra move.",
    "difficulty": "beginner",
    "setup_order": ["e4", "Nf3", "Nc3", "Bb5", "O-O"],
    "golden_rules": [
        "Knights before bishops: Nf3 and Nc3 first, then decide where the bishop goes.",
        "Bb5 copies the Ruy Lopez — it leans on the c6 knight that guards e5.",
        "Castle early and keep the position solid; the Four Knights rarely blows up.",
        "If Black pins your c3 knight with Bb4, you can mirror with Bb5 — symmetry is fine.",
    ],
    "traps": [],
    "tree": {
        "e4": {
            "idea": "Take the centre.",
            "next": "Nf3",
            "responses": {
                "e5": {
                    "name": "Open Game",
                    "idea_opponent": "Black mirrors in the centre.",
                    "next": "Nf3",
                    "hint": "Develop the king's knight and hit the e5 pawn.",
                    "right_feedback": "Nf3 — develop and attack e5, the natural start.",
                    "wrong_feedback": "Start with Nf3 — develop a piece and put a question to the e5 pawn. That's the backbone of every 1.e4 e5 opening.",
                    "responses": {
                        "Nc6": {
                            "name": "Two Knights territory",
                            "idea_opponent": "Black defends e5 and develops.",
                            "next": "Nc3",
                            "hint": "Bring the queen's knight out too — heading for the Four Knights.",
                            "right_feedback": "Nc3 — both knights out. This is the Four Knights, calm and solid.",
                            "wrong_feedback": "Nc3 develops your second knight and defends e4 — the Four Knights. (Bc4 is the Italian, also fine; Bb5 is the Ruy. For the Four Knights, Nc3.)",
                            "responses": {
                                "Nf6": {
                                    "name": "Four Knights — Main",
                                    "idea_opponent": "Black develops symmetrically and eyes e4.",
                                    "next": "Bb5",
                                    "right_feedback": "Bb5 — Spanish-style. You lean on the c6 knight that holds e5. Castle next.",
                                    "responses": {},
                                }
                            },
                        }
                    },
                }
            },
        }
    },
    "middlegame_plans": {
        "when_equal": {
            "plan": "Finish developing and castle: Bb5 + O-O + d3 + Bg5. The Four Knights is a slow build — small, safe edges, no early fireworks.",
            "ideas": [
                "Trade the b5 bishop for the c6 knight only when it wins something or wrecks Black's pawns.",
                "Use the d4 or Nd5 break in the centre when your pieces are ready.",
                "Keep the position symmetrical if you're happy with a small, safe edge.",
            ],
        },
        "when_ahead": {
            "plan": "Open the centre with d4 once you're developed and use the extra tempo to push.",
            "ideas": ["Play d4 to open lines.", "Jump a knight to d5 to pressure Black's position."],
        },
        "when_behind": {
            "plan": "Symmetry is your friend — trade pieces and steer toward an equal endgame.",
            "ideas": ["Trade queens.", "Keep your pawns sound."],
        },
    },
    "endgame_tips": [
        "Four Knights endings are usually balanced — the bishop pair is the asset to fight for.",
        "Doubled c-pawns (if you take on c6) can be a long-term target either way; know which side they help.",
    ],
}
FK_SKILL = ("opening_four_knights_white", {
    "kind": "opening", "label": "Four Knights (White)",
    "fixes": "not knowing what to play as White after 1.e4 e5",
    "content_ref": "four_knights_game", "prerequisites": ["coached_development"],
    "rating_min": 1000, "rating_max": 1499, "tier": 1,
})
FK_OPP = ["e5", "Nc6", "Nf6", "Be7"]  # for setup_order legality

# ---------------------------------------------------------------- Pirc (White)
PIRC = {
    "name": "Pirc Defense (Classical System)",
    "color": "white",
    "summary": "Black plays d6 and g6 and lets you build a big pawn centre, planning to chip at it later. The simplest reply is the Classical: take the centre with e4 + d4, develop Nc3 + Nf3 + Be2, castle, and hold your space. Don't overpush — let the extra space do the work.",
    "difficulty": "intermediate",
    "setup_order": ["e4", "d4", "Nc3", "Nf3", "Be2", "O-O"],
    "golden_rules": [
        "Take the whole centre — e4 and d4 — when Black plays the modest d6/g6 setup.",
        "Classical and calm: Nc3 + Nf3 + Be2 + O-O. You don't need a sharp attack to keep your edge.",
        "Defend e4 with Nc3 before Black's pressure builds.",
        "Hold your centre; don't lash out with early pawn pushes that create weaknesses.",
    ],
    "traps": [],
    "tree": {
        "e4": {
            "idea": "Take the centre.",
            "next": "d4",
            "responses": {
                "d6": {
                    "name": "Pirc / Modern setup",
                    "idea_opponent": "Black invites you to build a big centre, planning to hit it later with pieces and ...e5/...c5.",
                    "next": "d4",
                    "hint": "Grab the full centre while you can.",
                    "right_feedback": "d4 — take the big centre. The Pirc invites this; now develop and hold it.",
                    "wrong_feedback": "Take the centre with d4. Black's d6/g6 plan deliberately gives you space — accept it, then develop solidly.",
                    "responses": {
                        "Nf6": {
                            "name": "Pirc — attacking e4",
                            "idea_opponent": "Black develops and pokes your e4 pawn.",
                            "next": "Nc3",
                            "hint": "Defend e4 and develop the queen's knight.",
                            "right_feedback": "Nc3 — defends e4 and develops. Solid and natural.",
                            "responses": {
                                "g6": {
                                    "name": "Pirc — Main",
                                    "idea_opponent": "Black fianchettoes the bishop to g7, aiming at your centre.",
                                    "next": "Nf3",
                                    "hint": "Calm development — knight to f3, then bishop and castle (the Classical).",
                                    "right_feedback": "Nf3 — the Classical system. Be2 and O-O next; keep your big centre.",
                                    "responses": {
                                        "Bg7": {
                                            "name": "Pirc — Classical",
                                            "idea_opponent": "Black's bishop eyes your centre down the long diagonal.",
                                            "next": "Be2",
                                            "right_feedback": "Be2 — modest and solid. Castle next and sit on your space.",
                                            "responses": {},
                                        }
                                    },
                                }
                            },
                        }
                    },
                }
            },
        }
    },
    "middlegame_plans": {
        "when_equal": {
            "plan": "You have more space — develop everything, castle, and slowly improve. Re1, Bf4/Be3, Qd2. Don't rush; space wins slow games.",
            "ideas": [
                "Meet Black's ...e5 or ...c5 break by keeping the centre solid, not panicking.",
                "Trade Black's good g7 bishop with Be3 + Qd2 + Bh6 if you can.",
                "Use your space to manoeuvre; avoid trades that relieve Black's cramped position.",
            ],
        },
        "when_ahead": {
            "plan": "Expand with the extra space — push in the centre or on the kingside once you're fully developed.",
            "ideas": ["Consider a kingside pawn storm if Black has castled there.", "Open the centre when your pieces are better placed."],
        },
        "when_behind": {
            "plan": "Hold the centre and trade pieces; your space gives you a cushion even when worse.",
            "ideas": ["Trade attackers.", "Don't create pawn weaknesses around your king."],
        },
    },
    "endgame_tips": [
        "Your extra central space often means a freer endgame — keep rooks active on open files.",
        "Watch Black's ...c5/...e5 breaks; meeting them cleanly keeps your structure healthy into the ending.",
    ],
}
PIRC_SKILL = ("opening_pirc_white", {
    "kind": "opening", "label": "Pirc Defense (White, Classical)",
    "fixes": "not knowing how to meet Black's d6/g6 (Pirc/Modern) setups",
    "content_ref": "pirc_defense", "prerequisites": ["coached_development"],
    "rating_min": 1200, "rating_max": 1799, "tier": 2,
})
PIRC_OPP = ["d6", "Nf6", "g6", "Bg7", "O-O"]

# ------------------------------------------------------------- Alekhine (Black)
ALEKHINE = {
    "name": "Alekhine Defense",
    "color": "black",
    "summary": "1.e4 Nf6. You poke the e4 pawn straight away and invite White to push pawns forward and chase your knight. The plan: let White build a big centre, hop the knight to safety, then strike back at the overextended pawns with d6 and c5. Provocative but fun.",
    "difficulty": "intermediate",
    "setup_order": ["Nf6", "Nd5", "d6", "dxe5"],
    "golden_rules": [
        "1...Nf6 dares White to chase you — when the pawn comes to e5, hop to d5, not back home.",
        "After Nd5, strike at White's big centre with d6 — don't let those pawns settle.",
        "Trade off White's e5 spearhead pawn (dxe5) to free your pieces.",
        "Develop the light-square bishop actively (often Bg4 or Bf5) before locking it in.",
    ],
    "traps": [],
    "tree": {
        "e4": {
            "idea_opponent": "White takes the centre.",
            "next": "Nf6",
            "hint": "Which knight move attacks the e4 pawn at once and dares White to chase it?",
            "right_feedback": "Nf6 — the Alekhine. You poke e4 and invite White to overextend.",
            "responses": {
                "e5": {
                    "name": "Alekhine — the Chase",
                    "idea_opponent": "White kicks the knight and grabs space.",
                    "next": "Nd5",
                    "hint": "Where does the knight go to stay safe AND active — not back to where it came from?",
                    "right_feedback": "Nd5 — hop forward, out of the pawn's reach. Retreating to g8 would waste the whole idea.",
                    "wrong_feedback": "Jump to d5 — forward, not back. Ng8 undoes your first move; Nd5 keeps the knight active and central while White's pawns hang in the air.",
                    "responses": {
                        "d4": {
                            "name": "Alekhine — Modern",
                            "idea_opponent": "White builds a broad pawn centre and dares you to break it.",
                            "next": "d6",
                            "hint": "Strike at the centre before it rolls over you.",
                            "right_feedback": "d6 — hit White's centre right away, before those pawns get comfortable.",
                            "responses": {
                                "Nf3": {
                                    "name": "Alekhine — Modern Main",
                                    "idea_opponent": "White develops calmly, trying to keep the big centre.",
                                    "next": "dxe5",
                                    "right_feedback": "dxe5 — trade off White's spearhead pawn and free your game.",
                                    "responses": {},
                                }
                            },
                        }
                    },
                }
            },
        }
    },
    "middlegame_plans": {
        "when_equal": {
            "plan": "You traded space for targets — White's advanced pawns are weaknesses if you keep hitting them. Develop actively (Bg4/Bf5, e6, Be7, O-O) and pile on the centre with c5.",
            "ideas": [
                "Pressure White's d4/e5 pawns with pieces and the ...c5 break.",
                "Get your light-square bishop out BEFORE ...e6 locks it in.",
                "Castle and complete development; don't grab pawns while behind in pieces.",
            ],
        },
        "when_ahead": {
            "plan": "If White's centre has cracked, open lines and target the weak pawns directly.",
            "ideas": ["Open the position to exploit White's loose pawns.", "Trade into endings where the weak pawns fall."],
        },
        "when_behind": {
            "plan": "If White's space holds, stay solid and look for one clean break (...c5 or ...f6) to free yourself.",
            "ideas": ["Trade pieces to reduce White's space advantage.", "Avoid passive piece shuffles — find a pawn break."],
        },
    },
    "endgame_tips": [
        "If White's e5/d4 pawns survive into the endgame, blockade them with a knight on d5 or e6.",
        "Your queenside majority can become a passed pawn once the centre is traded off.",
    ],
}
ALE_SKILL = ("opening_alekhine_black", {
    "kind": "opening", "label": "Alekhine Defense (Black vs 1.e4)",
    "fixes": "not knowing what to play vs 1.e4",
    "content_ref": "alekhine_defense", "prerequisites": ["coached_development"],
    "rating_min": 1200, "rating_max": 1799, "tier": 2,
})
ALE_OPP = ["e4", "e5", "d4", "Nf3"]  # White's moves interleaving Black's setup

OPENINGS = [
    ("four_knights_game", FOUR_KNIGHTS, FK_SKILL, FK_OPP),
    ("pirc_defense", PIRC, PIRC_SKILL, PIRC_OPP),
    ("alekhine_defense", ALEKHINE, ALE_SKILL, ALE_OPP),
]


def walk(node, board, label, errors):
    responses = node.get("responses") or {}
    if not responses:
        return
    nxt = node.get("next")
    bc = board.copy()
    try:
        bc.push_san(nxt)
    except Exception as e:
        errors.append(f"{label}: illegal next '{nxt}' ({e})")
        return
    for opp_san, child in responses.items():
        b2 = bc.copy()
        try:
            b2.push_san(opp_san)
        except Exception as e:
            errors.append(f"{label}/{nxt} -> illegal reply '{opp_san}' ({e})")
            continue
        walk(child, b2, f"{label}/{nxt}/{opp_san}", errors)


def validate_tree(entry):
    errors = []
    color = entry["color"]
    for root_san, root in entry["tree"].items():
        b = chess.Board()
        try:
            b.push_san(root_san)  # White's first move (always e4 here)
        except Exception as e:
            errors.append(f"illegal root '{root_san}' ({e})")
            continue
        if color == "black":
            # curriculum side (black) plays root['next'] before opponent replies
            try:
                b.push_san(root["next"])
            except Exception as e:
                errors.append(f"root black reply '{root.get('next')}' illegal ({e})")
                continue
        for opp_san, child in (root.get("responses") or {}).items():
            b2 = b.copy()
            try:
                b2.push_san(opp_san)
            except Exception as e:
                errors.append(f"{root_san} -> illegal reply '{opp_san}' ({e})")
                continue
            walk(child, b2, f"{root_san}/{opp_san}", errors)
    return errors


def validate_setup(entry, opp_line):
    color = entry["color"]
    setup = entry["setup_order"]
    b = chess.Board()
    errs = []
    if color == "white":
        for i, san in enumerate(setup):
            if b.turn != chess.WHITE:
                errs.append(f"setup[{i}] '{san}': not White to move"); return errs
            try:
                b.push_san(san)
            except Exception as e:
                errs.append(f"setup[{i}] '{san}' illegal: {e}"); return errs
            if i < len(setup) - 1:
                try: b.push_san(opp_line[i])
                except Exception as e:
                    errs.append(f"setup opp '{opp_line[i]}' illegal: {e}"); return errs
    else:  # black: opp_line is White's moves, starting with e4
        try:
            b.push_san(opp_line[0])  # e4
        except Exception as e:
            errs.append(f"setup opp[0] illegal: {e}"); return errs
        for i, san in enumerate(setup):
            if b.turn != chess.BLACK:
                errs.append(f"setup[{i}] '{san}': not Black to move"); return errs
            try:
                b.push_san(san)
            except Exception as e:
                errs.append(f"setup[{i}] '{san}' illegal: {e}"); return errs
            if i < len(setup) - 1:
                try: b.push_san(opp_line[i + 1])
                except Exception as e:
                    errs.append(f"setup opp '{opp_line[i+1]}' illegal: {e}"); return errs
    return errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    any_err = False
    for key, entry, (sk_key, sk_node), opp in OPENINGS:
        terr = validate_tree(entry)
        serr = validate_setup(entry, opp)
        status = "OK" if not (terr or serr) else "FAIL"
        print(f"=== {entry['name']} ({entry['color']}) [{key}] : {status} ===")
        for e in terr + serr:
            print("  ✗", e); any_err = True
        if not (terr or serr):
            print("  ✓ tree legal | ✓ setup_order legal")
    if any_err:
        print("\nERRORS — not writing."); sys.exit(1)

    if not args.apply:
        print("\nVALIDATE-ONLY. Re-run with --apply to write.")
        return

    curric = json.load(open(CURRIC, encoding="utf-8"))
    skill = json.load(open(SKILL, encoding="utf-8"))
    for key, entry, (sk_key, sk_node), opp in OPENINGS:
        if key not in curric:
            curric[key] = entry; print(f"  + curriculum '{key}'")
        else:
            print(f"  ! curriculum '{key}' exists, skip")
        if sk_key not in skill["skills"]:
            skill["skills"][sk_key] = sk_node; print(f"  + skill '{sk_key}'")
        else:
            print(f"  ! skill '{sk_key}' exists, skip")
    json.dump(curric, open(CURRIC, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    json.dump(skill, open(SKILL, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print("\nApplied. Run opening_sync_check next.")


if __name__ == "__main__":
    main()
