"""Deepen two existing black-framed opening trees with the variations the
600-1500 audience actually faces (from the analysed-games variation audit):

  Sicilian: add the anti-Sicilians the tree skipped — Alapin (2.c3),
            Smith-Morra (2.d4 ... 3.c3, declined safely), Bowdler (2.Bc4).
  Caro-Kann: deepen the Advance (3.e5 Bf5) which was a one-move stub — add
             the Short System (4.Nf3 e6 5.Be2 c5) and the 4.c3 line.

Validates EVERY path in each modified tree for chess legality (black frame)
before writing. Idempotent: skips a branch if its key already exists.
"""
import argparse, json, sys
import chess

CURRIC = "/app/backend/data/opening_curriculum.json"

# ----- Sicilian: new root.responses siblings (White's 2nd move) --------------
SICILIAN_ANTILINES = {
    "c3": {
        "name": "Alapin (2.c3)",
        "idea_opponent": "White props the centre with c3, planning d4 — dodging the Open Sicilian.",
        "next": "d5",
        "hint": "Strike the centre at once, before White gets in d4.",
        "right_feedback": "d5 — hit back immediately. With the pawn on c3, White can't develop the knight to c3, so your queen won't get chased after the trade.",
        "wrong_feedback": "Against the Alapin, d5 is the most reliable — strike the centre while White's c3 pawn blocks the natural Nc3 development. Nf6 (inviting 3.e5) is the other main try, but d5 is the simplest equaliser.",
        "responses": {
            "exd5": {
                "name": "Alapin — Main",
                "idea_opponent": "White takes the pawn.",
                "next": "Qxd5",
                "right_feedback": "Qxd5 — and here it's safe: White has no Nc3 (the pawn's on c3), so your queen sits comfortably. Develop next.",
                "responses": {},
            }
        },
    },
    "d4": {
        "name": "Smith-Morra Gambit",
        "idea_opponent": "White offers a pawn (2.d4 cxd4 3.c3) for fast development and open lines.",
        "next": "cxd4",
        "hint": "Take the pawn — but you don't have to keep grabbing.",
        "right_feedback": "cxd4 — take it. If White then plays c3 (the Morra), you can decline the second pawn and just develop.",
        "responses": {
            "c3": {
                "name": "Smith-Morra — declined",
                "idea_opponent": "White offers a second pawn for a big lead in development.",
                "next": "Nf6",
                "hint": "Develop and hit e4 instead of getting greedy.",
                "right_feedback": "Nf6 — decline cleanly. Develop and put a question to e4 rather than grabbing dxc3, which hands White exactly the fast, open game the gambit wants.",
                "wrong_feedback": "Grabbing the second pawn with dxc3 is greedy and walks straight into the Smith-Morra: open c- and d-files, quick development, a real attack. Nf6 declines and keeps you solid.",
                "responses": {},
            }
        },
    },
    "Bc4": {
        "name": "Bowdler Attack (2.Bc4)",
        "idea_opponent": "White aims the bishop at f7 early, skipping the Open Sicilian.",
        "next": "e6",
        "hint": "Prepare to challenge that bishop with d5.",
        "right_feedback": "e6 — prepares d5, which both hits the c4 bishop and grabs the centre. Simple and strong.",
        "wrong_feedback": "Against the early Bc4, e6 is clean — it prepares d5, kicking the bishop and taking the centre. Don't rush ...e5 or leave f7 loose while the bishop stares at it.",
        "responses": {},
    },
}

# ----- Caro-Kann: deepen the Advance node (under e4>c6>d4>d5>e5) --------------
CK_ADVANCE_RESPONSES = {
    "Nf3": {
        "name": "Advance — Short System",
        "idea_opponent": "White develops calmly (the Short System), squeezing with space.",
        "next": "e6",
        "hint": "Your bishop's already outside the chain, so this is safe now.",
        "right_feedback": "e6 — safe here because the light-square bishop is already on f5, not buried. Next build with Nd7, Ne7 and the c5 break.",
        "responses": {
            "Be2": {
                "name": "Advance — Main",
                "idea_opponent": "White develops the bishop and castles.",
                "next": "c5",
                "right_feedback": "c5 — hit the base of White's pawn chain (d4). This is Black's main freeing break in the Advance.",
                "responses": {},
            }
        },
    },
    "c3": {
        "name": "Advance — c3 line",
        "idea_opponent": "White supports d4 with c3 before developing.",
        "next": "e6",
        "right_feedback": "e6 — solidify with the bishop already out, then strike with c5 or bring the knight to e7.",
        "responses": {},
    },
}


# --------------------------- legality (black frame) --------------------------
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


def validate_black_tree(tree):
    errors = []
    for root_san, root in tree.items():
        b = chess.Board()
        try:
            b.push_san(root_san)          # White e4
            b.push_san(root["next"])      # Black's reply (c5 / c6)
        except Exception as e:
            errors.append(f"root '{root_san}'/'{root.get('next')}' illegal ({e})")
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    curric = json.load(open(CURRIC, encoding="utf-8"))

    # Splice (in-memory) onto copies so we validate the FULL modified trees.
    import copy
    sic = copy.deepcopy(curric["sicilian_defense"])
    ck = copy.deepcopy(curric["caro_kann"])

    sic_root = sic["tree"]["e4"]["responses"]
    added_sic = []
    for k, v in SICILIAN_ANTILINES.items():
        if k in sic_root:
            print(f"  ! sicilian root already has '{k}', skip")
        else:
            sic_root[k] = v; added_sic.append(k)

    ck_adv = ck["tree"]["e4"]["responses"]["d4"]["responses"]["e5"]["responses"]
    added_ck = []
    for k, v in CK_ADVANCE_RESPONSES.items():
        if k in ck_adv:
            print(f"  ! caro-kann advance already has '{k}', skip")
        else:
            ck_adv[k] = v; added_ck.append(k)

    print(f"Sicilian new branches: {added_sic}")
    print(f"Caro-Kann Advance new branches: {added_ck}")

    errs = validate_black_tree(sic["tree"]) + validate_black_tree(ck["tree"])
    if errs:
        print("\nLEGALITY ERRORS — not writing:")
        for e in errs:
            print("  ✗", e)
        sys.exit(1)
    print("\n  ✓ all Sicilian paths legal")
    print("  ✓ all Caro-Kann paths legal")

    if not args.apply:
        print("\nVALIDATE-ONLY. Re-run with --apply to write.")
        return

    curric["sicilian_defense"] = sic
    curric["caro_kann"] = ck
    json.dump(curric, open(CURRIC, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print("\nApplied to curriculum. Run opening_sync_check next.")


if __name__ == "__main__":
    main()
