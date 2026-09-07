"""Two questions the histogram alone does not answer:

  1. UNION coverage - what share of the 455 unexplained moves does the whole
     positional set catch, not each shape separately?
  2. Are the rest actually positional at all? If the opponent has a
     material-winning capture right after the played move, the mistake is
     TACTICAL and the existing eight detectors should have caught it - which
     would make this a routing bug, not a missing-detector problem.
"""
import json, io, sys, collections
sys.stdout.reconfigure(encoding="utf-8")
import chess

B = r"C:/Users/MIISCO/AppData/Local/Temp/claude/c--Users-MIISCO-smartchesscoach/a63fa859-0292-4069-9726-e9550047fea8/scratchpad/"
rows = json.load(io.open(B + "worst_paths.json", encoding="utf-8"))
VAL = {chess.PAWN: 100, chess.KNIGHT: 300, chess.BISHOP: 320,
       chess.ROOK: 500, chess.QUEEN: 900, chess.KING: 0}


def mobility(board, sq):
    pc = board.piece_at(sq)
    if not pc:
        return 0
    return chess.popcount(board.attacks_mask(sq) & ~board.occupied_co[pc.color])


def positional_shape(b_before, mv, me):
    """Same measures as positional_shapes.py, collapsed to a yes/no."""
    frm, to = mv.from_square, mv.to_square
    moved = b_before.piece_at(frm)
    if moved is None:
        return False
    bp = mobility(b_before, frm)
    bt = sum(mobility(b_before, s) for s in chess.SQUARES
             if b_before.piece_at(s) and b_before.piece_at(s).color == me)
    b2 = b_before.copy()
    b2.push(mv)
    ap = mobility(b2, to)
    at = sum(mobility(b2, s) for s in chess.SQUARES
             if b2.piece_at(s) and b2.piece_at(s).color == me)
    if moved.piece_type != chess.PAWN and (
            (ap <= 1 and bp >= 4) or (bp - ap >= 4)):
        return True
    if at - bt <= -6:
        return True
    return False


def opponent_wins_material(b_after):
    """Does the side to move have a capture that wins material by static
    exchange? That is the shape failure_allows_capture already renders."""
    best = 0
    for mv in b_after.legal_moves:
        if not b_after.is_capture(mv):
            continue
        victim = b_after.piece_at(mv.to_square)
        if victim is None:
            continue  # en passant, ignore
        gain = VAL.get(victim.piece_type, 0)
        # crude SEE: is the target defended by the loser?
        b3 = b_after.copy()
        b3.push(mv)
        attacker = b_after.piece_at(mv.from_square)
        if b3.attackers(not b_after.turn, mv.to_square):
            gain -= VAL.get(attacker.piece_type, 0)
        best = max(best, gain)
    return best


pos_hit = tac_hit = both = neither = 0
tac_sizes = collections.Counter()
analysed = 0
neither_ex = []

for r in rows:
    fen, san = r.get("fen_before"), r.get("move_san")
    if not fen or not san:
        continue
    try:
        b = chess.Board(fen)
        mv = b.parse_san(san)
    except Exception:
        continue
    analysed += 1
    me = b.turn
    p = positional_shape(b, mv, me)
    b2 = b.copy()
    b2.push(mv)
    gain = opponent_wins_material(b2)
    t = gain >= 100
    if t:
        tac_sizes["%d+" % (100 * (min(gain, 500) // 100))] += 1
    if p and t:
        both += 1
    elif p:
        pos_hit += 1
    elif t:
        tac_hit += 1
    else:
        neither += 1
        if len(neither_ex) < 5:
            neither_ex.append("%s cp=%s  %s" % (san, r.get("cp_loss"),
                                                (r.get("caption") or "")[:60]))

print("unexplained moves analysed: %d\n" % analysed)
print("%-42s %6s %7s" % ("bucket", "count", "share"))
for label, n in (("positional shape only", pos_hit),
                 ("opponent wins material (TACTICAL) only", tac_hit),
                 ("both", both),
                 ("neither", neither)):
    print("%-42s %6d  %5.1f%%" % (label, n, 100.0 * n / analysed))
print("\npositional set covers (incl. overlap): %.1f%%" % (100.0 * (pos_hit + both) / analysed))
print("tactical shape available            : %.1f%%" % (100.0 * (tac_hit + both) / analysed))
print("\nmaterial at stake in the tactical ones:", dict(tac_sizes.most_common()))
print("\nexamples of 'neither':")
for e in neither_ex:
    print("   %s" % e)
