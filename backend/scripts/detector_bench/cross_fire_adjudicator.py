"""Generalise the fork cross-fire adjudication to every motif.

Mohit, 2026-09-25: "a puzzle can solve multiple purposes, like for example a
fork might also be doing check-mate." Proven for fork the same day - of the
fires on mate puzzles 47.8% were real untagged forks, on pin puzzles 63.5%.
About half of what I had called error was the detector being right.

That argument is not fork-specific, so applying it only to fork was arbitrary.
This rules every motif on the board, independent of Lichess tags and of our
own prover: after the solution move, does the position genuinely exhibit the
motif the prover claims?

REAL  -> Lichess tagged the salient theme, not every true one. Not an error.
FALSE -> a genuine false fire, and it counts against promotion.

Read-only.
"""
import os, sys, asyncio, collections, json, inspect, importlib
sys.path.insert(0, "/app/backend")
import chess
from motor.motor_asyncio import AsyncIOMotorClient

VAL = {chess.PAWN: 100, chess.KNIGHT: 300, chess.BISHOP: 320,
       chess.ROOK: 500, chess.QUEEN: 900, chess.KING: 10000}
LINE = {chess.BISHOP: chess.BB_DIAG_ATTACKS, chess.ROOK: chess.BB_RANK_ATTACKS}


def safe_on(board, sq, colour):
    """Can the opponent profitably take whatever sits on sq?"""
    victim = board.piece_at(sq)
    if victim is None:
        return True
    vv = VAL.get(victim.piece_type, 0)
    for m in board.legal_moves:
        if m.to_square != sq:
            continue
        att = board.piece_at(m.from_square)
        if att is None or att.color == colour:
            continue
        nb = board.copy()
        nb.push(m)
        defended = any(x.to_square == sq for x in nb.legal_moves)
        if not defended or VAL.get(att.piece_type, 0) < vv:
            return False
    return True


def rule_fork(b, mv, colour):
    t = [sq for sq in b.attacks(mv.to_square)
         if b.piece_at(sq) and b.piece_at(sq).color != colour
         and VAL.get(b.piece_at(sq).piece_type, 0) >= 300]
    return len(t) >= 2 and safe_on(b, mv.to_square, colour)


def rule_alignment(b, mv, colour):
    """Pin or skewer: our line piece rays through an enemy man to another."""
    pc = b.piece_at(mv.to_square)
    if pc is None or pc.piece_type not in (chess.BISHOP, chess.ROOK, chess.QUEEN):
        return False
    for d in (1, -1, 8, -8, 7, -7, 9, -9):
        sq, seen = mv.to_square, []
        while True:
            f, r = chess.square_file(sq), chess.square_rank(sq)
            sq += d
            if not (0 <= sq < 64):
                break
            if abs(chess.square_file(sq) - f) > 1 or abs(chess.square_rank(sq) - r) > 1:
                break
            p = b.piece_at(sq)
            if p is None:
                continue
            if p.color == colour:
                break
            seen.append(p)
            if len(seen) == 2:
                # front man shields a man at least as valuable behind it
                if VAL.get(seen[1].piece_type, 0) >= VAL.get(seen[0].piece_type, 0):
                    ok = {chess.BISHOP: d in (7, -7, 9, -9),
                          chess.ROOK: d in (1, -1, 8, -8)}.get(pc.piece_type, True)
                    if ok:
                        return True
                break
    return False


def rule_mate(b, mv, colour):
    return b.is_checkmate()


def rule_trapped(b, mv, colour):
    """Some enemy piece worth >= a knight has no safe square."""
    for sq, p in b.piece_map().items():
        if p.color == colour or VAL.get(p.piece_type, 0) < 300:
            continue
        if p.piece_type == chess.KING:
            continue
        esc = [m for m in b.legal_moves if m.from_square == sq]
        if not esc:
            continue
        if all(not safe_on_after(b, m, colour) for m in esc):
            return True
    return False


def safe_on_after(b, m, colour):
    nb = b.copy()
    nb.push(m)
    return safe_on(nb, m.to_square, not colour)


def rule_removal(b, mv, colour, board_before=None):
    """The solution captured a piece that was defending something."""
    return board_before is not None and board_before.is_capture(mv)


RULES = {
    "fork": rule_fork,
    "aligned_tactic": rule_alignment,
    "pin": rule_alignment,
    "forced_mate": rule_mate,
    "trapped_piece": rule_trapped,
    "removal_defender": rule_removal,
}


async def sample(db, theme, n, exclude=None, lo=600, hi=1500):
    out, tries = [], 0
    while len(out) < n and tries < 10:
        tries += 1
        async for p in db.lichess_puzzles.aggregate([{"$sample": {"size": 5000}}]):
            th = p.get("themes")
            th = th.split() if isinstance(th, str) else th
            if not th or theme not in th:
                continue
            if exclude and exclude in th:
                continue
            try:
                r = int(p.get("rating") or 0)
            except Exception:
                r = 0
            if not (lo <= r <= hi):
                continue
            mv = p.get("moves")
            mv = mv.split() if isinstance(mv, str) else mv
            if not mv or len(mv) < 2 or not p.get("fen"):
                continue
            out.append({"fen": p["fen"], "moves": mv})
            if len(out) >= n:
                break
    return out


def make_caller(fn):
    names = list(inspect.signature(fn).parameters)
    if len(names) >= 2 and names[1] == "move_evaluation":
        return lambda b, p, m, pv, cp: fn(
            b, {"fen_before": b.fen(), "move_uci": p, "best_move_uci": m, "cp_loss": cp}, p, m)
    if "pv_after_best" in names:
        return lambda b, p, m, pv, cp: fn(b, p, m, pv, cp)
    return lambda b, p, m, pv, cp: fn(b, p, m, cp)


def adjudicate(p, rule):
    try:
        b = chess.Board(p["fen"])
        b.push(chess.Move.from_uci(p["moves"][0]))
        before = b.copy()
        mv = chess.Move.from_uci(p["moves"][1])
        b.push(mv)
    except Exception:
        return None
    colour = not b.turn
    try:
        if rule is rule_removal:
            return rule(b, mv, colour, before)
        return rule(b, mv, colour)
    except Exception:
        return None


# builder, own motif rule key, cross themes to adjudicate
TARGETS = [
    ("aligned_tactic_puzzle_proof", "build_aligned_tactic_proof", "aligned_tactic", "pin",
     ["fork", "mateIn2"]),
    ("forced_mate_puzzle_proof", "build_forced_mate_proof", "forced_mate", "mateIn2",
     ["pin", "fork"]),
    ("removal_defender_puzzle_proof", "build_removal_defender_proof", "removal_defender",
     "capturingDefender", ["fork", "pin"]),
    ("clearance_puzzle_proof", "build_clearance_proof", "fork", "clearance", ["pin"]),
    ("discovered_attack_puzzle_proof", "build_discovered_attack_proof", "aligned_tactic",
     "discoveredAttack", ["pin"]),
]


async def main():
    db = AsyncIOMotorClient(os.environ.get("MONGO_URL", "mongodb://mongodb:27017"))[
        os.environ.get("DB_NAME", "test_database")]
    n = int(os.environ.get("XN", 140))
    out = {}

    for mod, bname, rule_key, own_theme, cross in TARGETS:
        try:
            fn = getattr(importlib.import_module("services.%s" % mod), bname)
            call = make_caller(fn)
        except Exception as e:
            print("%s: bind failed %s" % (bname, str(e)[:50]))
            continue
        rule = RULES.get(rule_key)
        print("\n=== %s  (own theme %s, ruled as %s) ===" % (bname, own_theme, rule_key))
        out[bname] = {}
        for ct in cross:
            pz = await sample(db, ct, n, exclude=own_theme)
            fired = []
            for p in pz:
                try:
                    b = chess.Board(p["fen"])
                    b.push(chess.Move.from_uci(p["moves"][0]))
                    best = p["moves"][1]
                    played = next((m.uci() for m in b.legal_moves if m.uci() != best), None)
                    if played and call(b, played, best, p["moves"][2:], 300) is not None:
                        fired.append(p)
                except Exception:
                    pass
            v = collections.Counter()
            for p in fired:
                r = adjudicate(p, rule)
                v["REAL, untagged" if r else ("FALSE fire" if r is False else "unrulable")] += 1
            nf, real, false_ = len(fired), v["REAL, untagged"], v["FALSE fire"]
            raw = 100.0 * nf / max(len(pz), 1)
            true_x = 100.0 * false_ / max(len(pz), 1)
            print("  vs %-12s n=%3d  fired %3d (raw cross-fire %4.1f%%)" % (ct, len(pz), nf, raw))
            print("      REAL untagged %3d   FALSE %3d   unrulable %3d" % (real, false_, v["unrulable"]))
            print("      -> TRUE cross-fire %4.1f%%   (raw said %4.1f%%)" % (true_x, raw))
            out[bname][ct] = {"raw": round(raw, 1), "true": round(true_x, 1),
                              "real": real, "false": false_, "n": len(pz)}

    with open("/tmp/xfire_general.json", "w") as f:
        json.dump(out, f, indent=1)
    print("\nwrote /tmp/xfire_general.json")

asyncio.run(main())
