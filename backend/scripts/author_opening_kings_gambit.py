"""Author the King's Gambit into the opening curriculum + skill tree.

Two-file edit (opening_sync_check requires both to agree):
  1. data/opening_curriculum.json     — full teaching entry (key: kings_gambit)
  2. data/coaching/skill_tree.json     — skill node (content_ref: kings_gambit)

Validates every move path in the tree + setup_order for chess legality with
python-chess BEFORE writing. Idempotent: skips if the key already exists.
Run with --apply to write (default is validate-only).
"""
import argparse, json, os, sys
import chess

CURRIC = "/app/backend/data/opening_curriculum.json"
SKILL = "/app/backend/data/coaching/skill_tree.json"
KEY = "kings_gambit"

ENTRY = {
    "name": "King's Gambit",
    "color": "white",
    "summary": "1.e4 e5 2.f4. You offer the f-pawn to tear open the centre and the f-file for a fast attack on Black's king. Sharp and fun — strongest when you know the first few moves. After 2...exf4, play 3.Nf3 (it stops the queen check on h4), aim the bishop at f7 with Bc4, castle, and attack.",
    "difficulty": "intermediate",
    "setup_order": ["e4", "f4", "Nf3", "Bc4", "O-O"],
    "golden_rules": [
        "After Black takes on f4, play Nf3 at once — it stops the queen check on h4.",
        "Aim the light bishop at f7 (Bc4) and castle quickly; the open f-file is your attacking lane.",
        "Don't chase the pawn back on f4 — finish developing and open lines instead.",
        "If Black hits back with 2...d5, take with exd5 and keep developing — don't panic.",
    ],
    "traps": [],
    "tree": {
        "e4": {
            "idea": "Take the centre.",
            "next": "f4",
            "responses": {
                "e5": {
                    "name": "Open Game",
                    "idea_opponent": "Black claims their share of the centre.",
                    "next": "f4",
                    "hint": "Offer the f-pawn — 2.f4, the King's Gambit.",
                    "right_feedback": "f4 — the King's Gambit. You give up a pawn to rip open the centre and aim at f7.",
                    "wrong_feedback": "For the King's Gambit the move is f4 — offering the pawn to blast the centre open. Nf3 is the calm Italian/Ruy path instead (also fine, just not the gambit).",
                    "responses": {
                        "exf4": {
                            "name": "King's Gambit Accepted",
                            "idea_opponent": "Black grabs the pawn on f4.",
                            "next": "Nf3",
                            "hint": "Play Nf3 — it stops Black's queen from checking on h4.",
                            "right_feedback": "Nf3 — the key move. It covers h4 (no more queen check) and develops toward the kingside.",
                            "wrong_feedback": "Develop with Nf3 first. Skip it and Black plays Qh4+, dragging your king out before you're ready. Nf3 covers h4 and brings a piece out.",
                            "responses": {
                                "g5": {"name": "Classical Defence", "idea_opponent": "Black props up the extra pawn with g5.", "next": "h4", "right_feedback": "h4 — challenge the g5 pawn before Black builds a wall of pawns.", "responses": {}},
                                "d5": {"name": "Modern Defence", "idea_opponent": "Black hits the centre back instead of holding the pawn.", "next": "exd5", "right_feedback": "exd5 — open the centre while you're ahead in development.", "responses": {}},
                                "Nf6": {"name": "Schallopp Defence", "idea_opponent": "Black develops and eyes the e4 pawn.", "next": "e5", "right_feedback": "e5 — push the pawn, grab space and kick the knight.", "responses": {}},
                            },
                        },
                        "Bc5": {
                            "name": "Classical Declined",
                            "idea_opponent": "Black declines and points the bishop at g1, making your castling awkward.",
                            "next": "Nf3",
                            "hint": "Just develop with Nf3 — don't grab on e5.",
                            "right_feedback": "Nf3 — develop. Taking fxe5 here opens lines for Black's queen with Qh4+ ideas.",
                            "wrong_feedback": "Develop with Nf3. Grabbing fxe5 lets Black play Qh4+ and chase your king. Keep it solid and bring pieces out.",
                            "responses": {},
                        },
                        "d5": {
                            "name": "Falkbeer Counter-Gambit",
                            "idea_opponent": "Black counter-attacks the centre instead of taking on f4.",
                            "next": "exd5",
                            "hint": "Take the pawn — exd5 — then develop calmly.",
                            "right_feedback": "exd5 — take it, then finish your development. Don't cling to the pawn; get your pieces out.",
                            "wrong_feedback": "Take with exd5. Against the Falkbeer, grabbing the pawn and developing is simplest — fxe5 instead lets Black's pieces flood out with the lead.",
                            "responses": {},
                        },
                    },
                }
            },
        }
    },
    "middlegame_plans": {
        "when_equal": {
            "plan": "Finish developing toward the king: Nf3 + Bc4 + O-O, then aim down the open f-file at f7. The half-open f-file is the whole point of the gambit.",
            "ideas": [
                "Double rooks on the f-file once the king is castled.",
                "Use the d4 pawn break to open the centre when your king is safer than Black's.",
                "Win the f4 pawn back later if it's free, but never at the cost of development.",
            ],
        },
        "when_ahead": {
            "plan": "Open lines and attack — push d4 and bring everything at the king. A development lead in the King's Gambit is meant to be cashed in fast.",
            "ideas": [
                "Sacrifice the gambit pawn (or another) to open the f-file and the centre.",
                "Bring the rook to f1 and the knight to g5/e5 toward f7.",
            ],
        },
        "when_behind": {
            "plan": "If the attack fizzles and you're just down the pawn, trade pieces and head for an endgame where the extra pawn matters least.",
            "ideas": [
                "Trade queens to kill Black's attacking chances.",
                "Keep your pawns connected; avoid more weaknesses around the king.",
            ],
        },
    },
    "endgame_tips": [
        "If you never won the f4 pawn back, you may be a pawn down — trade into rook endings where one pawn is hardest to convert.",
        "Open f-file rooks stay strong into the endgame; keep at least one rook active.",
    ],
}

SKILL_NODE = {
    "kind": "opening",
    "label": "King's Gambit (White)",
    "fixes": "not knowing how to attack as White after 1.e4 e5",
    "content_ref": KEY,
    "prerequisites": ["coached_development"],
    "rating_min": 1200,
    "rating_max": 1799,
    "tier": 2,
}
SKILL_KEY = "opening_kings_gambit_white"


def validate_tree(tree):
    """Walk every path. Node semantics (mirrors existing entries):
      - root key  = curriculum side's FIRST move (already the move, not a reply)
      - root.responses = opponent replies to that first move
      - a child node's own move is its 'next'; its 'responses' are opponent
        replies AFTER that 'next' is played.
    """
    errors = []

    def walk(node, board, label):
        # board: position with the curriculum side to move; node['next'] is it.
        nxt = node.get("next")
        responses = node.get("responses") or {}
        if not responses:
            return  # leaf — 'next' is advisory text, nothing deeper to verify
        b_after = board.copy()
        try:
            b_after.push_san(nxt)
        except Exception as e:
            errors.append(f"{label}: illegal next '{nxt}' ({e})")
            return
        for opp_san, child in responses.items():
            b2 = b_after.copy()
            try:
                b2.push_san(opp_san)
            except Exception as e:
                errors.append(f"{label}/{nxt} -> illegal reply '{opp_san}' ({e})")
                continue
            walk(child, b2, f"{label}/{nxt}/{opp_san}")

    for root_san, root in tree.items():
        b = chess.Board()
        try:
            b.push_san(root_san)
        except Exception as e:
            errors.append(f"illegal root move '{root_san}' ({e})")
            continue
        for opp_san, child in (root.get("responses") or {}).items():
            b2 = b.copy()
            try:
                b2.push_san(opp_san)
            except Exception as e:
                errors.append(f"{root_san} -> illegal reply '{opp_san}' ({e})")
                continue
            walk(child, b2, f"{root_san}/{opp_san}")
    return errors


# A concrete, quiet main line to confirm setup_order is fully legal for White.
_SETUP_BLACK_LINE = ["e5", "exf4", "d6", "Be7"]


def validate_setup(setup):
    b = chess.Board()
    errs = []
    for i, san in enumerate(setup):
        if b.turn != chess.WHITE:
            errs.append(f"setup_order[{i}] '{san}': not White to move")
            return errs
        try:
            b.push_san(san)
        except Exception as e:
            errs.append(f"setup_order[{i}] '{san}' illegal: {e}")
            return errs
        if i < len(setup) - 1:
            try:
                b.push_san(_SETUP_BLACK_LINE[i])
            except Exception as e:
                errs.append(f"setup check: black reply '{_SETUP_BLACK_LINE[i]}' illegal: {e}")
                return errs
    return errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    print("=== Validate King's Gambit entry ===")
    terr = validate_tree(ENTRY["tree"])
    serr = validate_setup(ENTRY["setup_order"])
    if terr or serr:
        print("LEGALITY ERRORS:")
        for e in terr + serr:
            print("  ✗", e)
        sys.exit(1)
    print("  ✓ all tree move-paths legal")
    print("  ✓ setup_order legal for White")

    curric = json.load(open(CURRIC, encoding="utf-8"))
    skill = json.load(open(SKILL, encoding="utf-8"))
    if KEY in curric:
        print(f"  ! '{KEY}' already in curriculum — skipping curriculum write")
    if SKILL_KEY in skill.get("skills", {}):
        print(f"  ! '{SKILL_KEY}' already in skill_tree — skipping skill write")

    if not args.apply:
        print("\nVALIDATE-ONLY. Re-run with --apply to write both files.")
        return

    if KEY not in curric:
        curric[KEY] = ENTRY
        json.dump(curric, open(CURRIC, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
        print(f"  + wrote curriculum entry '{KEY}'")
    if SKILL_KEY not in skill["skills"]:
        skill["skills"][SKILL_KEY] = SKILL_NODE
        json.dump(skill, open(SKILL, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
        print(f"  + wrote skill node '{SKILL_KEY}'")
    print("\nApplied. Run opening_sync_check next.")


if __name__ == "__main__":
    main()
