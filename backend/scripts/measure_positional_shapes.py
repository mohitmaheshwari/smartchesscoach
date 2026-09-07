"""Which POSITIONAL shapes actually recur in the mistakes our captions can't explain?

Runs over the moves that fall to R16_board_state_fallback / HELD_FLOOR with no
played-move why. Every measure here is board arithmetic computed BEFORE and
AFTER the played move, so any caption built on it is verifiable per-FEN — the
requirement that keeps a claim from being dumped to the floor.

Differential, not descriptive: the existing fallback already says true things
about the POSITION ("the f-file is open and opponent's rook controls it"). What
it never says is what THIS MOVE changed. These measures are all deltas.
"""
import json, io, sys, collections
sys.stdout.reconfigure(encoding="utf-8")
import chess

B = r"C:/Users/MIISCO/AppData/Local/Temp/claude/c--Users-MIISCO-smartchesscoach/a63fa859-0292-4069-9726-e9550047fea8/scratchpad/"
rows = json.load(io.open(B + "worst_paths.json", encoding="utf-8"))

PIECE_NAME = {chess.PAWN: "pawn", chess.KNIGHT: "knight", chess.BISHOP: "bishop",
              chess.ROOK: "rook", chess.QUEEN: "queen", chess.KING: "king"}


def mobility(board, sq):
    """Squares this piece can move to (attack set minus own pieces). Turn-free,
    so it is comparable across a move."""
    pc = board.piece_at(sq)
    if not pc:
        return 0
    own = board.occupied_co[pc.color]
    return chess.popcount(board.attacks_mask(sq) & ~own)


def pawns_on_colour(board, colour, light):
    n = 0
    for sq in board.pieces(chess.PAWN, colour):
        is_light = (chess.square_rank(sq) + chess.square_file(sq)) % 2 == 1
        if is_light == light:
            n += 1
    return n


def doubled_files(board, colour):
    c = collections.Counter(chess.square_file(s) for s in board.pieces(chess.PAWN, colour))
    return {f for f, n in c.items() if n > 1}


def isolated_files(board, colour):
    files = {chess.square_file(s) for s in board.pieces(chess.PAWN, colour)}
    return {f for f in files if (f - 1) not in files and (f + 1) not in files}


def king_shelter(board, colour):
    k = board.king(colour)
    if k is None:
        return 0
    n = 0
    for s in board.pieces(chess.PAWN, colour):
        if abs(chess.square_file(s) - chess.square_file(k)) <= 1:
            d = chess.square_rank(s) - chess.square_rank(k)
            if (colour == chess.WHITE and 0 < d <= 2) or (colour == chess.BLACK and -2 <= d < 0):
                n += 1
    return n


def rook_open_files(board, colour):
    own_pawn_files = {chess.square_file(s) for s in board.pieces(chess.PAWN, colour)}
    return sum(1 for r in board.pieces(chess.ROOK, colour)
               if chess.square_file(r) not in own_pawn_files)


hits = collections.Counter()
examples = collections.defaultdict(list)
analysed = skipped = 0

for r in rows:
    fen = r.get("fen_before")
    san = r.get("move_san")
    if not fen or not san:
        skipped += 1
        continue
    try:
        b = chess.Board(fen)
        mv = b.parse_san(san)
    except Exception:
        skipped += 1
        continue
    me = b.turn
    frm, to = mv.from_square, mv.to_square
    moved = b.piece_at(frm)
    if moved is None:
        skipped += 1
        continue
    analysed += 1

    before_piece_mob = mobility(b, frm)
    before_total = sum(mobility(b, s) for s in chess.SQUARES
                       if b.piece_at(s) and b.piece_at(s).color == me)
    before_doubled = doubled_files(b, me)
    before_isolated = isolated_files(b, me)
    before_shelter = king_shelter(b, me)
    before_rookopen = rook_open_files(b, me)
    before_badbishop = {}
    for bs in b.pieces(chess.BISHOP, me):
        light = (chess.square_rank(bs) + chess.square_file(bs)) % 2 == 1
        before_badbishop[bs] = pawns_on_colour(b, me, light)

    b.push(mv)

    after_piece_mob = mobility(b, to)
    after_total = sum(mobility(b, s) for s in chess.SQUARES
                      if b.piece_at(s) and b.piece_at(s).color == me)
    after_doubled = doubled_files(b, me)
    after_isolated = isolated_files(b, me)
    after_shelter = king_shelter(b, me)
    after_rookopen = rook_open_files(b, me)

    name = PIECE_NAME[moved.piece_type]
    ex = "%s %s (cp%s)" % (san, chess.square_name(to), r.get("cp_loss"))

    # 1. the moved piece is now nearly stuck
    if moved.piece_type != chess.PAWN and after_piece_mob <= 1 and before_piece_mob >= 4:
        hits["trapped_moved_piece"] += 1
        examples["trapped_moved_piece"].append(
            "%s: %s had %d squares, now %d" % (ex, name, before_piece_mob, after_piece_mob))
    # 2. the moved piece got materially more passive
    elif moved.piece_type != chess.PAWN and before_piece_mob - after_piece_mob >= 4:
        hits["piece_went_passive"] += 1
        examples["piece_went_passive"].append(
            "%s: %s %d -> %d squares" % (ex, name, before_piece_mob, after_piece_mob))

    # 3. the move shut in the player's OWN pieces
    if after_total - before_total <= -6:
        hits["self_blocking"] += 1
        examples["self_blocking"].append(
            "%s: own mobility %d -> %d" % (ex, before_total, after_total))

    # 4. pawn structure damage this move created
    if after_doubled - before_doubled:
        hits["created_doubled_pawn"] += 1
        examples["created_doubled_pawn"].append(
            "%s: doubled on file %s" % (ex, sorted(after_doubled - before_doubled)))
    if after_isolated - before_isolated:
        hits["created_isolated_pawn"] += 1
        examples["created_isolated_pawn"].append(
            "%s: isolated on file %s" % (ex, sorted(after_isolated - before_isolated)))

    # 5. king cover given up by this move
    if before_shelter - after_shelter >= 1 and moved.piece_type == chess.PAWN:
        hits["gave_up_king_shelter"] += 1
        examples["gave_up_king_shelter"].append(
            "%s: shelter pawns %d -> %d" % (ex, before_shelter, after_shelter))

    # 6. rook left / lost its open file
    if before_rookopen - after_rookopen >= 1:
        hits["rook_lost_open_file"] += 1
        examples["rook_lost_open_file"].append(
            "%s: rooks on open files %d -> %d" % (ex, before_rookopen, after_rookopen))

    # 7. bishop shut behind its own pawns
    if moved.piece_type == chess.PAWN:
        for bs, before_n in before_badbishop.items():
            if b.piece_at(bs) is None:
                continue
            light = (chess.square_rank(bs) + chess.square_file(bs)) % 2 == 1
            after_n = pawns_on_colour(b, me, light)
            if after_n > before_n and after_n >= 4:
                hits["pawn_blocks_own_bishop"] += 1
                examples["pawn_blocks_own_bishop"].append(
                    "%s: pawns on bishop's colour %d -> %d" % (ex, before_n, after_n))
                break

print("analysed %d of %d rows (%d unparseable)\n" % (analysed, len(rows), skipped))
print("%-26s %6s  %s" % ("positional shape", "count", "share of analysed"))
covered = set()
for k, n in hits.most_common():
    print("%-26s %6d  %5.1f%%" % (k, n, 100.0 * n / max(analysed, 1)))
print("\n--- examples ---")
for k, _ in hits.most_common(6):
    print("\n%s:" % k)
    for e in examples[k][:3]:
        print("   %s" % e)
json.dump({k: examples[k] for k in hits}, io.open(B + "positional_examples.json", "w",
                                                  encoding="utf-8"), ensure_ascii=False)
