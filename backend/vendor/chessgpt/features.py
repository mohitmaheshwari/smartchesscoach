"""ExplainEval: decompose a position into human chess concepts.

Every feature is computed independently for both colors and returned from
White's perspective (positive = good for White).  Nothing here depends on
whose turn it is, so a feature value is a property of the position alone.

Raw units differ per feature on purpose.  Cross-feature comparison happens
only after `calibration.py` converts each diff into centipawns.
"""

from dataclasses import dataclass, field

import chess

PIECE_VALUE = {
    chess.PAWN: 1.0,
    chess.KNIGHT: 3.0,
    chess.BISHOP: 3.2,
    chess.ROOK: 5.0,
    chess.QUEEN: 9.0,
    chess.KING: 0.0,
}

# A defended piece only has to move if the exchange actually loses material.
# Bishops are scored at 3.2 and knights at 3.0, so a bare "cheaper attacker"
# test made a knight hitting a defended bishop a tempo on a 0.2 margin that
# means nothing on a board — the two pieces trade evenly and nobody moves.
TEMPO_MIN_LOSS = 1.0

# how much each attacker type threatens the enemy king zone
KING_ATTACK_WEIGHT = {
    chess.PAWN: 0.5,
    chess.KNIGHT: 2.0,
    chess.BISHOP: 2.0,
    chess.ROOK: 3.0,
    chess.QUEEN: 5.0,
}


@dataclass
class FeatureValue:
    name: str
    value: float
    evidence: list = field(default_factory=list)

    def __repr__(self):
        return f"{self.name}={self.value:+.2f}"


def _sq(square: int) -> str:
    return chess.square_name(square)


def _piece_at(board: chess.Board, square: int) -> str:
    """A piece and where it stands -- "king on g1", not "Kg1".

    "Kg1" is notation for the king *moving* to g1, and it was being used for a
    king already standing there. The reader gets a move that was never played,
    and so does the language model, which repeated the field verbatim. It is
    also a real move in many positions, so the chat linkified it and offered a
    jump to a position nobody had asked about.
    """
    piece = board.piece_at(square)
    if not piece:
        return _sq(square)
    return f"{chess.piece_name(piece.piece_type)} on {_sq(square)}"


def _pawn_attack_mask(board: chess.Board, color: bool) -> chess.SquareSet:
    """All squares attacked by `color`'s pawns."""
    mask = chess.SquareSet()
    for square in board.pieces(chess.PAWN, color):
        mask |= chess.SquareSet(chess.BB_PAWN_ATTACKS[color][square])
    return mask


def _king_zone(board: chess.Board, color: bool) -> chess.SquareSet:
    """King square, its neighbours, and one rank further out in front."""
    king = board.king(color)
    if king is None:
        return chess.SquareSet()
    zone = chess.SquareSet(chess.BB_KING_ATTACKS[king]) | chess.SquareSet.from_square(king)
    forward = 1 if color == chess.WHITE else -1
    for square in list(zone):
        rank = chess.square_rank(square) + forward
        if 0 <= rank <= 7:
            zone.add(chess.square(chess.square_file(square), rank))
    return zone


# --------------------------------------------------------------------------
# 0. material
# --------------------------------------------------------------------------

def material(board: chess.Board) -> FeatureValue:
    """Plain material count.  Lines that win a pawn need to be able to say so."""
    counts = {chess.WHITE: 0.0, chess.BLACK: 0.0}
    detail = {"white": {}, "black": {}}
    for color in (chess.WHITE, chess.BLACK):
        key = "white" if color else "black"
        for piece_type in (chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN):
            count = len(board.pieces(piece_type, color))
            if count:
                detail[key][chess.piece_name(piece_type)] = count
            counts[color] += count * PIECE_VALUE[piece_type]
    balance = counts[chess.WHITE] - counts[chess.BLACK]
    return FeatureValue(
        "material",
        balance,
        [{"kind": "material_balance", "balance": round(balance, 2), **detail}],
    )


# --------------------------------------------------------------------------
# 1. hanging pieces
# --------------------------------------------------------------------------

def _exposed_material(board: chess.Board):
    """Material each side has left attacked and not adequately defended.

    Cheap static detector: attacked-and-undefended, or attacked by something
    worth less.  It over-fires by design.
    """
    loss = {chess.WHITE: 0.0, chess.BLACK: 0.0}
    evidence = {chess.WHITE: [], chess.BLACK: []}

    for color in (chess.WHITE, chess.BLACK):
        for square in chess.SquareSet(board.occupied_co[color]):
            piece = board.piece_at(square)
            if piece.piece_type == chess.KING:
                continue
            attackers = board.attackers(not color, square)
            if not attackers:
                continue
            defenders = board.attackers(color, square)
            value = PIECE_VALUE[piece.piece_type]
            # Undefended only. A *defended* piece attacked by something cheaper
            # is not material anyone can win — it is a piece that has to move,
            # which is `tempo`. Counting it here made the two features measure
            # the same event twice, and worse: this evidence feeds the quiet
            # filter, so every position where a knight hit a queen was
            # classified as "tactics pending" and dropped before the walk could
            # measure the tempo it was gaining. Tempo fired in 90 sampled
            # positions and only 20 survived to be fitted on.
            if defenders:
                continue
            exposure = value
            kind = "undefended"
            loss[color] += exposure
            evidence[color].append(
                {
                    "kind": kind,
                    "piece": _piece_at(board, square),
                    "color": "white" if color else "black",
                    "value": round(exposure, 2),
                    "attackers": sorted(_piece_at(board, a) for a in attackers),
                }
            )
    return loss, evidence


def threats(board: chess.Board) -> FeatureValue:
    """Enemy material left undefended under attack — what can actually be won.

    Split from `loose_pieces` because a move that creates a threat and a move
    that covers a weakness are different moves to a human even when the
    arithmetic happens to agree.  Merged, both arrive under one name and the
    explanation can only report one of them.

    Disjoint from `tempo` by construction: this is material that can be taken,
    that is a piece that must move.
    """
    loss, evidence = _exposed_material(board)
    return FeatureValue("threats", loss[chess.BLACK] - 0.0, evidence[chess.BLACK])


def loose_pieces(board: chess.Board) -> FeatureValue:
    """Own material left hanging.  Negative from White's point of view."""
    loss, evidence = _exposed_material(board)
    return FeatureValue("loose_pieces", -loss[chess.WHITE], evidence[chess.WHITE])


def _forcing_for(board: chess.Board, color: bool):
    """Replies the opponent is compelled to make, counted in tempi.

    A tempo is gained by moving a piece somewhere useful while creating a threat
    the opponent has to stop what they were doing to answer. The measurable half
    of that is the forced reply; whether the move was also useful shows up in
    the activity and development features of the same comparison.

    `threats` measures how much material is winnable, this measures how many
    moves the opponent must spend. They overlap on a loose piece, which is
    genuinely both, and they are different quantities of it.
    """
    evidence = []
    count = 0.0
    for square in chess.SquareSet(board.occupied_co[not color]):
        piece = board.piece_at(square)
        # Pawns are excluded on purpose. A pawn is worth less than the initiative
        # spent saving it, so a pawn threat is routinely ignored — nobody calls
        # attacking a loose pawn "gaining a tempo".
        if piece.piece_type in (chess.KING, chess.PAWN):
            continue
        value = PIECE_VALUE[piece.piece_type]
        attackers = list(board.attackers(color, square))
        if not attackers:
            continue
        defended = bool(board.attackers(not color, square))
        cheapest = min(PIECE_VALUE[board.piece_at(a).piece_type] for a in attackers)
        # The test is whether the defender is *forced to answer*, which is what
        # the definition of a tempo actually turns on. Two ways that happens:
        # the piece is undefended and simply drops, or it is defended but the
        # attacker is cheaper so the exchange loses material.
        #
        # The earlier version tested only for a cheaper attacker, which missed
        # the commonest case of all — a rook or queen hitting a loose minor
        # piece, where nothing about the attacker is cheap and the defender must
        # still respond.
        if defended and value - cheapest < TEMPO_MIN_LOSS:
            continue
        count += 1.0
        evidence.append(
            {
                "kind": "forced_reply",
                "color": "white" if color else "black",
                "target": _piece_at(board, square),
                "why": "undefended" if not defended else "attacked_by_cheaper",
                "attackers": sorted(_piece_at(board, a) for a in attackers),
            }
        )
    return count, evidence


def tempo(board: chess.Board) -> FeatureValue:
    white, white_ev = _forcing_for(board, chess.WHITE)
    black, black_ev = _forcing_for(board, chess.BLACK)
    return FeatureValue("tempo", white - black, white_ev + black_ev)


# --------------------------------------------------------------------------
# 2. king safety
# --------------------------------------------------------------------------

def _king_shelter_for(board: chess.Board, color: bool):
    """How well `color`'s own king is covered by its pawns."""
    king = board.king(color)
    if king is None:
        return 0.0, []

    evidence = []
    king_file = chess.square_file(king)
    king_rank = chess.square_rank(king)
    forward = 1 if color == chess.WHITE else -1

    shield = 0.0
    for file in range(max(0, king_file - 1), min(7, king_file + 1) + 1):
        found = None
        for step in (1, 2, 3):
            rank = king_rank + forward * step
            if not 0 <= rank <= 7:
                break
            square = chess.square(file, rank)
            piece = board.piece_at(square)
            if piece and piece.piece_type == chess.PAWN and piece.color == color:
                found = step
                break
        if found == 1:
            shield += 1.0
        elif found == 2:
            shield += 0.5
        elif found is None:
            shield -= 0.5
            evidence.append(
                {
                    "kind": "missing_pawn_shield",
                    "file": chess.FILE_NAMES[file],
                    "king": _sq(king),
                }
            )

    return shield, evidence


def king_shelter(board: chess.Board) -> FeatureValue:
    """Own-king cover only.

    Kept apart from the attacking features because the two move independently:
    a move that attacks the enemy king and a move that tucks your own king away
    are both good, and summing them into one number lets them cancel to zero.
    """
    white, white_ev = _king_shelter_for(board, chess.WHITE)
    black, black_ev = _king_shelter_for(board, chess.BLACK)
    for item in white_ev:
        item["defender"] = "white"
    for item in black_ev:
        item["defender"] = "black"
    return FeatureValue("king_shelter", white - black, white_ev + black_ev)


def _weak_king_squares_of(board: chess.Board, color: bool):
    """Squares near `color`'s king that the enemy hits and only the king guards.

    This is the f7 concept.  A square the enemy attacks and a rook defends is
    covered; a square only the king defends is the one an attack is built on.
    """
    king = board.king(color)
    if king is None:
        return 0.0, []

    evidence = []
    score = 0.0
    # The king ring only.  The wider king zone reaches squares the king cannot
    # step to, where "defended only by the king" describes nothing, and counting
    # those washed the signal out entirely.
    for square in chess.SquareSet(chess.BB_KING_ATTACKS[king]):
        attackers = board.attackers(not color, square)
        if not attackers:
            continue
        defenders = board.attackers(color, square) - chess.SquareSet.from_square(king)
        if defenders:
            continue
        # Deliberately not weighted by how many pieces attack the square:
        # `king_pressure` already counts those pieces, and counting them twice
        # made the two features collinear.  Each one measures a different thing
        # — this one the squares, that one the pieces.
        score += 1.0
        evidence.append(
            {
                "kind": "weak_king_square",
                "square": _sq(square),
                "king": _sq(king),
                "attackers": sorted(_piece_at(board, a) for a in attackers),
            }
        )
    return score, evidence


def king_weak_squares(board: chess.Board) -> FeatureValue:
    on_white, white_ev = _weak_king_squares_of(board, chess.WHITE)
    on_black, black_ev = _weak_king_squares_of(board, chess.BLACK)
    for item in white_ev:
        item["defender"] = "white"
    for item in black_ev:
        item["defender"] = "black"
    return FeatureValue("king_weak_squares", on_black - on_white, white_ev + black_ev)


def _secure_attackers_of(board: chess.Board, color: bool):
    """Enemy pieces hitting `color`'s king zone that no pawn can drive off."""
    king = board.king(color)
    if king is None:
        return 0.0, []

    evidence = []
    score = 0.0
    zone = _king_zone(board, color)
    for square in chess.SquareSet(board.occupied_co[not color]):
        piece = board.piece_at(square)
        if piece.piece_type in (chess.KING, chess.PAWN):
            continue
        hit = chess.SquareSet(board.attacks_mask(square)) & zone
        if not hit or not _pawn_safe(board, square, not color):
            continue
        # And it has to survive where it stands. A piece that is hanging is not
        # an attacker, it is a piece about to be taken: the knight on d1 in
        # Carlsen-Lazavik sits inside White's king zone, hits e3 and f2, and is
        # lost to Kxd1 next move. Counted as an attacker it cancelled the bishop
        # that was actually attacking Black's king, and the feature read zero in
        # a position whose whole point is the attack. `threats` already reports
        # that knight as material about to change hands, so it was being counted
        # twice, in opposite directions.
        if not _safe_square(board, piece.piece_type, square, square, not color):
            continue
        score += 1.0
        evidence.append(
            {
                "kind": "entrenched_attacker",
                "piece": _piece_at(board, square),
                "king": _sq(king),
                "hits": sorted(_sq(s) for s in hit),
            }
        )
    return score, evidence


def _exposure_of(board: chess.Board, color: bool):
    """Squares of `color`'s king zone the enemy attacks, and who is holding it up.

    Squares, not pieces. Counting attacking *pieces* cannot tell one bishop
    raking four squares of the zone from three pieces piled onto one, and it
    forces a decision about who qualifies as an attacker -- pawns or not, safe
    from pawns or not, hanging or not. Every one of those thresholds was tried
    and every one of them broke the measure, because the attacking side was held
    to two safety tests and the defending side to none, so the subtraction was
    between two differently-filtered populations.

    A defender is then whatever *makes it worse when removed*, which needs no
    threshold at all and picks up the piece nobody was counting: one blocking a
    line from outside the zone entirely. `defense_gap` counts the men too far
    away to help; this counts the ones already holding a square, including from
    a distance.
    """
    zone = _king_zone(board, color)
    if not zone:
        return 0, [], []

    def attacked(position):
        hit = chess.SquareSet()
        for square in chess.SquareSet(position.occupied_co[not color]):
            hit |= chess.SquareSet(position.attacks_mask(square)) & zone
        return hit

    exposed = attacked(board)
    holding = []
    for square in chess.SquareSet(board.occupied_co[color]):
        if board.piece_at(square).piece_type == chess.KING:
            continue
        probe = board.copy()
        probe.remove_piece_at(square)
        opened = len(attacked(probe)) - len(exposed)
        if opened > 0:
            holding.append(
                {
                    "kind": "holds_the_king",
                    "piece": _piece_at(board, square),
                    "opens": opened,
                }
            )
    return len(exposed), sorted(_sq(s) for s in exposed), holding


def king_pressure(board: chess.Board) -> FeatureValue:
    """How much of each king's zone the other side attacks.

    Replaces a count of attacking pieces, which could not tell three attackers
    facing nobody from three facing three, and could not see a defender at all.
    Both halves are answered by measuring the zone rather than the men: what is
    under attack is the exposure, and a defender is a piece whose removal
    increases it.
    """
    on_black, black_squares, black_holding = _exposure_of(board, chess.BLACK)
    on_white, white_squares, white_holding = _exposure_of(board, chess.WHITE)
    evidence = []
    for side, count, squares, holding in (
        ("black", on_black, black_squares, black_holding),
        ("white", on_white, white_squares, white_holding),
    ):
        if count:
            evidence.append(
                {"kind": "king_exposed", "color": side, "squares": squares}
            )
        for item in holding:
            evidence.append({**item, "color": side})
    return FeatureValue("king_pressure", float(on_black - on_white), evidence)


def _distance(a: int, b: int) -> int:
    return max(
        abs(chess.square_file(a) - chess.square_file(b)),
        abs(chess.square_rank(a) - chess.square_rank(b)),
    )


def _attack_force_on(board: chess.Board, color: bool):
    """How many enemy pieces are taking part in the attack on `color`'s king.

    Separate from `king_pressure`, which only counts pieces a pawn can never
    drive away. That test is right for "this piece has moved in permanently"
    and wrong for "the attack is gathering": a knight arriving on g5 can be met
    by h6 and so counts for nothing there, while being exactly the move a
    player would describe as joining the attack.

    Everything is measured from the king's actual square, so a queenside or
    centre king gets its own neighbourhood rather than a hardcoded kingside.
    """
    king = board.king(color)
    if king is None:
        return 0.0, []

    zone = _king_zone(board, color)
    evidence = []
    score = 0.0
    for square in chess.SquareSet(board.occupied_co[not color]):
        piece = board.piece_at(square)
        if piece.piece_type in (chess.KING, chess.PAWN):
            continue
        hits = chess.SquareSet(board.attacks_mask(square)) & zone
        near = _distance(square, king) <= 3
        if not hits and not near:
            continue
        # Hitting the zone is participation; standing next to it is a piece
        # that will be participating shortly.
        score += 1.0 if hits else 0.5
        evidence.append(
            {
                "kind": "attacker" if hits else "gathering",
                "piece": _piece_at(board, square),
                "king": _sq(king),
                "hits": sorted(_sq(s) for s in hits),
            }
        )
    return score, evidence


def attack_force(board: chess.Board) -> FeatureValue:
    on_white, white_ev = _attack_force_on(board, chess.WHITE)
    on_black, black_ev = _attack_force_on(board, chess.BLACK)
    for item in white_ev:
        item["defender"] = "white"
    for item in black_ev:
        item["defender"] = "black"
    return FeatureValue("attack_force", on_black - on_white, white_ev + black_ev)


def _absent_defenders(board: chess.Board, color: bool):
    """`color`'s own pieces that cannot take part in defending their king.

    An attack is won as much by the defenders that never arrive as by the
    attackers that do — a knight on a5 while the king is on g1 is a piece the
    defender does not have. Counting only the attacking side misses half of
    every attack.
    """
    king = board.king(color)
    if king is None:
        return 0.0, []

    zone = _king_zone(board, color)
    evidence = []
    score = 0.0
    for square in chess.SquareSet(board.occupied_co[color]):
        piece = board.piece_at(square)
        if piece.piece_type in (chess.KING, chess.PAWN):
            continue
        if chess.SquareSet(board.attacks_mask(square)) & zone:
            continue
        if _distance(square, king) <= 3:
            continue
        score += 1.0
        evidence.append(
            {
                "kind": "out_of_play",
                "piece": _piece_at(board, square),
                "king": _sq(king),
                "distance": _distance(square, king),
            }
        )
    return score, evidence


def defense_gap(board: chess.Board) -> FeatureValue:
    white, white_ev = _absent_defenders(board, chess.WHITE)
    black, black_ev = _absent_defenders(board, chess.BLACK)
    for item in white_ev:
        item["color"] = "white"
    for item in black_ev:
        item["color"] = "black"
    return FeatureValue("defense_gap", white - black, white_ev + black_ev)


def _colour_complex_on(board: chess.Board, color: bool):
    """Squares of one colour near the king that `color`'s pawns cannot cover,
    counted only when the enemy owns a bishop of that colour.

    A hole is not a weakness in the abstract — it is a weakness for whoever can
    stand on it. Dark squares around the king matter when the opponent still
    has a dark-squared bishop and stop mattering the moment it is traded, which
    is why this cannot be folded into open lines or weak squares.
    """
    king = board.king(color)
    if king is None:
        return 0.0, []

    zone = _king_zone(board, color)
    own_pawn_cover = _pawn_attack_mask(board, color)
    evidence = []
    score = 0.0
    for name, mask in (
        ("light", chess.SquareSet(chess.BB_LIGHT_SQUARES)),
        ("dark", chess.SquareSet(chess.BB_DARK_SQUARES)),
    ):
        holes = (zone & mask) - own_pawn_cover
        if not holes:
            continue
        bishops = [
            square
            for square in board.pieces(chess.BISHOP, not color)
            if square in mask
        ]
        if not bishops:
            continue
        score += len(holes) * 0.5
        evidence.append(
            {
                "kind": f"{name}_square_complex",
                "king": _sq(king),
                "holes": sorted(_sq(s) for s in holes),
                "bishop": sorted(_piece_at(board, b) for b in bishops),
            }
        )
    return score, evidence


def colour_complex(board: chess.Board) -> FeatureValue:
    on_white, white_ev = _colour_complex_on(board, chess.WHITE)
    on_black, black_ev = _colour_complex_on(board, chess.BLACK)
    for item in white_ev:
        item["defender"] = "white"
    for item in black_ev:
        item["defender"] = "black"
    return FeatureValue("colour_complex", on_black - on_white, white_ev + black_ev)


def _king_lines_of(board: chess.Board, color: bool):
    """Files near `color`'s king with no friendly pawn and a heavy piece on them."""
    king = board.king(color)
    if king is None:
        return 0.0, []

    evidence = []
    score = 0.0
    king_file = chess.square_file(king)
    for file in range(max(0, king_file - 1), min(7, king_file + 1) + 1):
        mask = chess.SquareSet(chess.BB_FILES[file])
        if mask & board.pieces(chess.PAWN, color):
            continue
        heavy = mask & (
            board.pieces(chess.ROOK, not color) | board.pieces(chess.QUEEN, not color)
        )
        if not heavy:
            continue
        fully_open = not (mask & board.pieces(chess.PAWN, not color))
        score += 1.0 if fully_open else 0.6
        evidence.append(
            {
                "kind": "line_to_king",
                "file": chess.FILE_NAMES[file],
                "king": _sq(king),
                "open": fully_open,
                "pieces": sorted(_piece_at(board, s) for s in heavy),
            }
        )
    return score, evidence


def king_open_lines(board: chess.Board) -> FeatureValue:
    on_white, white_ev = _king_lines_of(board, chess.WHITE)
    on_black, black_ev = _king_lines_of(board, chess.BLACK)
    for item in white_ev:
        item["defender"] = "white"
    for item in black_ev:
        item["defender"] = "black"
    return FeatureValue("king_open_lines", on_black - on_white, white_ev + black_ev)


# --------------------------------------------------------------------------
# 3. mobility
# --------------------------------------------------------------------------

# What one reachable square is worth, relative to a square that is merely legal.
#
# `mobility` counted squares, so an outpost beside the enemy king and a corner
# nobody will ever contest were both worth one. These weights are the reviewer's
# proposal, staged so each term can be turned on alone: adding them together and
# measuring once tells you the total moved and not which part moved it.
#
# Deliberately *not* weighted by the moving piece's value. That was tried, as
# `piece_scope`, and it failed for a reason that has nothing to do with squares:
# weighting by piece value makes the side with more pieces score higher, so the
# column re-measured material and collided with it in the fit (correlation with
# `material` went from +0.26 to +0.49). Square value has no such coupling.
CENTRE = frozenset(chess.parse_square(name) for name in ("d4", "d5", "e4", "e5"))
BROAD_CENTRE = frozenset(
    chess.square(file, rank) for file in range(2, 6) for rank in range(2, 6)
)
SQUARE_VALUE = {
    "centre": 1.0,      # (a) the middle is worth more than the rim
    "far": 0.5,         # (b) squares in the enemy half
    "target": 0.5,      # (c) squares holding an enemy piece
    "king_zone": 0.5,   # (d) squares in the enemy king's zone -- overlap risk
    "chased": -0.5,     # (e) squares an enemy pawn can attack
}
# Which terms are live. Empty -- the original count, one square one point.
#
# Measured over 1,909 positions before spending an engine pass on a refit, and
# the result is a stopping argument rather than a slow start:
#
#     weights                          corr baseline  corr material  corr attack_force
#     as proposed  1.0/.5/.5/.5/-.5         0.932          0.611          0.568
#     stronger     3/2/2/3/-0.9             0.846          0.550          0.654
#     extreme      6/4/4/8/-1.0             0.789          0.513          0.697
#
# At the proposed weights the column is 93% the same column: a sum over attacked
# squares is dominated by how many there are, and multiplying a handful of them
# by 1.5 does not change that. Raising the weights until it *does* change --
# down to 0.79 with the baseline -- pushes the correlation with `attack_force`
# past 0.6, which was the agreed line for "this is not a new feature, it is two
# old ones added together".
#
# So the choice is between a column that measures nothing new and a column that
# measures what `attack_force` already measures. Neither is worth a refit, and
# the reviewer's diagnosis -- that `mobility` counts quantity and not quality --
# turns out to be true and not fixable by weighting the squares. A quality
# measure would have to stop being a sum over attacked squares.
#
# Left switchable rather than deleted: the next attempt should start from these
# numbers, not from a blank file.
ACTIVE_VALUE_TERMS = ()


def _square_value(board, square, color, zone, denied, terms):
    """How much one reachable square is worth to `color`."""
    value = 1.0
    if "centre" in terms:
        value += SQUARE_VALUE["centre"] if square in CENTRE else (
            SQUARE_VALUE["centre"] / 2 if square in BROAD_CENTRE else 0.0
        )
    if "far" in terms:
        rank = chess.square_rank(square)
        if (rank >= 4) if color == chess.WHITE else (rank <= 3):
            value += SQUARE_VALUE["far"]
    if "target" in terms and board.piece_at(square) is not None:
        value += SQUARE_VALUE["target"]
    if "king_zone" in terms and square in zone:
        value += SQUARE_VALUE["king_zone"]
    if "chased" in terms and square in denied:
        value += SQUARE_VALUE["chased"]
    return max(value, 0.0)


def _mobility_for(board: chess.Board, color: bool, terms=None):
    terms = ACTIVE_VALUE_TERMS if terms is None else terms
    own = chess.SquareSet(board.occupied_co[color])
    denied = _pawn_attack_mask(board, not color)
    # Squares an enemy pawn can attack are excluded outright unless the `chased`
    # term is live, in which case they are kept and discounted -- a square you
    # can use for one move is not nothing, and deleting it was always the cruder
    # of the two options.
    blocked = chess.SquareSet() if "chased" in terms else denied
    zone = _king_zone(board, not color) if "king_zone" in terms else chess.SquareSet()
    total = 0.0
    per_piece = []
    for piece_type in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN):
        for square in board.pieces(piece_type, color):
            targets = chess.SquareSet(board.attacks_mask(square)) & ~own & ~blocked
            if terms:
                worth = sum(
                    _square_value(board, target, color, zone, denied, terms)
                    for target in targets
                )
            else:
                worth = float(len(targets))
            total += worth
            per_piece.append((_piece_at(board, square), round(worth)))
    per_piece.sort(key=lambda item: -item[1])
    return total, per_piece


# Moved here from `tactics.py`, which imports this module: the scope measure
# below asks the same question about the squares a piece walks through, and a
# second copy of an exchange test is how two layers start disagreeing about
# what 'safe' means.
def _worth(board: chess.Board, square: int) -> float:
    piece = board.piece_at(square)
    if piece is None:
        return 0.0
    return 20.0 if piece.piece_type == chess.KING else PIECE_VALUE[piece.piece_type]


def _safe_square(
    board: chess.Board, piece_type: int, origin: int, target: int, color: bool
) -> bool:
    """Could this piece stand on `target` without simply being lost?

    The piece is moved before the question is asked, and both halves of that
    matter. Asked with it still on `origin` a queen counts as defending every
    square she could move to, because she attacks them from where she stands —
    and worse, she blocks the very line she is trying to escape. A queen on e5
    facing a rook on e8 read e4, e3, e2 and e1 as unattacked, because her own
    body was in the way of the rook; step onto any of them and the line opens.

    That is the third time in this file the right rule has been asked in the
    wrong position: the skewer test counted defenders with the front piece still
    standing there, and the material gate looked for a payoff down a line that
    had already been cut off.

    "Safely" is then an exchange question rather than an attacked-or-not one:
    undefended and attacked is lost whatever the attacker costs, and defended is
    fine as long as the cheapest attacker is not cheaper than the piece.
    """
    probe = board.copy()
    probe.remove_piece_at(origin)
    probe.set_piece_at(target, chess.Piece(piece_type, color))
    attackers = probe.attackers(not color, target)
    if not attackers:
        return True
    if not probe.attackers(color, target):
        return False
    value = PIECE_VALUE[piece_type]
    cheapest = min(_worth(probe, attacker) for attacker in attackers)
    return cheapest >= value


# How far a piece can actually get, in its own moves, with everything else where
# it stands. Two earlier shapes were measured and thrown away:
#
#   one move        what `_activity` counts. It sums, so a side that loses a queen
#                   loses nine points of "activity" -- the feature is 0.33
#                   correlated with material and partly restates it.
#   enemy removed,  saturates into a constant. Over 300 positions the knight
#   unlimited moves median was 52 and the queen never went below 46, so neither
#                   piece type could ever read as shut in.
#
# Walking the real board for a bounded number of moves keeps the gradation for
# all four types: at two moves the medians are knight 17, bishop 12, rook 14,
# queen 32, and 3.8% of rooks and 3.7% of bishops read zero. Three moves starts
# drifting back up (28/16/19/44), which is the saturation this exists to avoid.
SCOPE_MOVES = 2

# The ceiling each type is measured against: its scope from d4 on an empty board.
# A bishop reaches half the board and a rook all of it, so without this a bishop
# would score as permanently half-shut. Derived rather than sampled, so it does
# not move when the corpus does.
SCOPE_CEILING = {
    chess.KNIGHT: 34.0,
    chess.BISHOP: 31.0,
    chess.ROOK: 63.0,
    chess.QUEEN: 63.0,
}

# How sharply the score saturates. Small values make it nearly "is this piece shut
# in or not"; large ones keep a gradation between busy and very busy. Chosen by
# the calibration scan.
SCOPE_C = 0.25


def _scope(board: chess.Board, square: int, color: bool, moves: int = SCOPE_MOVES) -> int:
    """Squares this piece can reach in `moves` of its own, nothing else moving.

    A square counts when it is reached; it is only walked *through* when standing
    there is not simply losing the piece, which is what `_safe_square` decides. A
    capture is an endpoint: taking something is a different decision from touring,
    and continuing past it would need the captured piece removed and the exchange
    settled first.
    """
    piece = board.piece_at(square)
    if piece is None:
        return 0
    enemy = chess.SquareSet(board.occupied_co[not color])
    own = chess.SquareSet(board.occupied_co[color]) - chess.SquareSet([square])
    seen, frontier = set(), [square]
    for _ in range(moves):
        following = []
        for at in frontier:
            probe = board.copy()
            if at != square:
                probe.remove_piece_at(square)
                probe.set_piece_at(at, piece)
            for target in chess.SquareSet(probe.attacks_mask(at)) & ~own:
                if target in seen or target == square:
                    continue
                seen.add(target)
                if target not in enemy and _safe_square(
                    board, piece.piece_type, square, target, color
                ):
                    following.append(target)
        frontier = following
        if not frontier:
            break
    return len(seen)


def piece_scope(board: chess.Board, moves: int = SCOPE_MOVES, c: float = SCOPE_C) -> FeatureValue:
    """How much of the board each side's pieces can actually use.

    Weighted by piece value, so shutting a rook in costs more than shutting a
    knight in, and saturating, so the difference between busy and very busy is
    worth little while the difference between shut in and moving is worth
    everything. A piece that has been captured contributes nothing because it is
    not on the board, and one that cannot move contributes nothing because
    `_scope` is zero -- the same reading, which is the point: a queen with no
    squares is doing as much for you as a queen that is gone.
    """
    scores, evidence = {}, []
    for color in (chess.WHITE, chess.BLACK):
        total = 0.0
        shut = []
        for piece_type in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN):
            ceiling = SCOPE_CEILING[piece_type]
            for square in board.pieces(piece_type, color):
                reach = _scope(board, square, color, moves) / ceiling
                total += PIECE_VALUE[piece_type] * reach / (reach + c)
                if reach == 0:
                    shut.append(_piece_at(board, square))
        scores[color] = total
        evidence.append(
            {
                "kind": "piece_scope",
                "color": "white" if color else "black",
                "score": round(total, 2),
                # Named, because "your bishop is doing nothing" is the sentence
                # this feature exists to license.
                "shut_in": shut,
            }
        )
    return FeatureValue(
        "piece_scope", scores[chess.WHITE] - scores[chess.BLACK], evidence
    )


def _activity(board: chess.Board, piece_type: int, name: str) -> FeatureValue:
    """Mobility of one kind of piece.

    One aggregate hides the thing a player would actually say. Freeing a bishop
    while a rook gets shut in nets zero and reports nothing, so "this move opens
    the bishop's diagonal" — a sentence about one piece — could never be the
    reason for anything. Per-piece-type counts keep the gain and the loss from
    cancelling each other into silence.
    """
    totals, evidence = {}, []
    for color in (chess.WHITE, chess.BLACK):
        own = chess.SquareSet(board.occupied_co[color])
        denied = _pawn_attack_mask(board, not color)
        total = 0
        per_piece = []
        for square in board.pieces(piece_type, color):
            targets = chess.SquareSet(board.attacks_mask(square)) & ~own & ~denied
            total += len(targets)
            per_piece.append((_piece_at(board, square), len(targets)))
        per_piece.sort(key=lambda item: -item[1])
        totals[color] = total
        evidence.append(
            {
                "kind": f"{name}_activity",
                "color": "white" if color else "black",
                "total": total,
                "top": per_piece[:3],
            }
        )
    return FeatureValue(
        f"{name}_activity", float(totals[chess.WHITE] - totals[chess.BLACK]), evidence
    )


def mobility(board: chess.Board) -> FeatureValue:
    """Total activity of all pieces, with the per-type breakdown as evidence.

    The four-way split was an experiment and this is the control for it. The
    aggregate and its parts cannot both be fitted: the aggregate *is* the sum,
    so a regression containing both is collinear by construction and the ridge
    splits the credit arbitrarily. One has to be the predictor and the other
    has to be evidence.
    """
    parts = {
        name: _activity(board, piece_type, name)
        for name, piece_type in (
            ("knight", chess.KNIGHT),
            ("bishop", chess.BISHOP),
            ("rook", chess.ROOK),
            ("queen", chess.QUEEN),
        )
    }
    total = sum(part.value for part in parts.values())
    evidence = [item for part in parts.values() for item in part.evidence]
    return FeatureValue("mobility", total, evidence)


def knight_activity(board: chess.Board) -> FeatureValue:
    return _activity(board, chess.KNIGHT, "knight")


def bishop_activity(board: chess.Board) -> FeatureValue:
    return _activity(board, chess.BISHOP, "bishop")


def rook_activity(board: chess.Board) -> FeatureValue:
    return _activity(board, chess.ROOK, "rook")


def queen_activity(board: chess.Board) -> FeatureValue:
    return _activity(board, chess.QUEEN, "queen")


# --------------------------------------------------------------------------
# 4. outposts
# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
# pawn structure
#
# This is the layer the rest of a chess book hangs off:
#
#     pawn structure -> weak squares / holes -> outposts -> piece activity
#
# The system had only the back half of that chain, which is part of why
# `outposts` kept dying in the fit: whether a hole is permanent or temporary is
# a fact about the pawns, and the pawns were not being measured.
#
# Each type is its own feature because they do not share a sign. An isolated
# pawn is a liability and a passed pawn is an asset; summing them into one
# "pawn structure" number would cancel the two things a player would say.
# --------------------------------------------------------------------------

def _pawn_files(board: chess.Board, color: bool):
    """Ranks occupied by `color`'s pawns, per file."""
    files = {}
    for square in board.pieces(chess.PAWN, color):
        files.setdefault(chess.square_file(square), []).append(chess.square_rank(square))
    return files


def _isolated_for(board: chess.Board, color: bool):
    files = _pawn_files(board, color)
    found = []
    for file, ranks in files.items():
        if any(neighbour in files for neighbour in (file - 1, file + 1)):
            continue
        for rank in ranks:
            found.append(
                {
                    "kind": "isolated_pawn",
                    "color": "white" if color else "black",
                    "square": _sq(chess.square(file, rank)),
                    "file": chess.FILE_NAMES[file],
                }
            )
    return float(len(found)), found


def isolated_pawns(board: chess.Board) -> FeatureValue:
    """Pawns with no friendly pawn on either neighbouring file.

    No pawn can ever defend them, so defending them costs pieces, which is what
    makes them targets rather than merely lonely.
    """
    white, white_ev = _isolated_for(board, chess.WHITE)
    black, black_ev = _isolated_for(board, chess.BLACK)
    return FeatureValue("isolated_pawns", black - white, white_ev + black_ev)


def _doubled_for(board: chess.Board, color: bool):
    found = []
    for file, ranks in _pawn_files(board, color).items():
        for rank in sorted(ranks)[1:]:
            found.append(
                {
                    "kind": "doubled_pawn",
                    "color": "white" if color else "black",
                    "square": _sq(chess.square(file, rank)),
                    "file": chess.FILE_NAMES[file],
                }
            )
    return float(len(found)), found


def doubled_pawns(board: chess.Board) -> FeatureValue:
    """Extra pawns stacked on one file, which cannot defend each other."""
    white, white_ev = _doubled_for(board, chess.WHITE)
    black, black_ev = _doubled_for(board, chess.BLACK)
    return FeatureValue("doubled_pawns", black - white, white_ev + black_ev)


def _backward_for(board: chess.Board, color: bool):
    """Behind its neighbours, with the square in front held by an enemy pawn.

    Both halves are needed. A pawn that has merely fallen behind can advance and
    stop being backward; what fixes it in place, and turns it into a target, is
    that the square ahead is covered.
    """
    forward = 1 if color == chess.WHITE else -1
    enemy_cover = _pawn_attack_mask(board, not color)
    files = _pawn_files(board, color)
    found = []
    for square in board.pieces(chess.PAWN, color):
        file, rank = chess.square_file(square), chess.square_rank(square)
        supported = False
        for adjacent in (file - 1, file + 1):
            for other in files.get(adjacent, []):
                if (other - rank) * forward <= 0:
                    supported = True
        if supported:
            continue
        ahead = rank + forward
        if not 0 <= ahead <= 7:
            continue
        if chess.square(file, ahead) not in enemy_cover:
            continue
        found.append(
            {
                "kind": "backward_pawn",
                "color": "white" if color else "black",
                "square": _sq(square),
                "blocked_on": _sq(chess.square(file, ahead)),
            }
        )
    return float(len(found)), found


def backward_pawns(board: chess.Board) -> FeatureValue:
    white, white_ev = _backward_for(board, chess.WHITE)
    black, black_ev = _backward_for(board, chess.BLACK)
    return FeatureValue("backward_pawns", black - white, white_ev + black_ev)


def _passed_for(board: chess.Board, color: bool):
    """No enemy pawn ahead on its file or either neighbour, scored by distance.

    A passed pawn on the sixth rank is not the same asset as one on the third,
    so counting them equally discards the part that decides endgames.
    """
    forward = 1 if color == chess.WHITE else -1
    enemy = _pawn_files(board, not color)
    score = 0.0
    found = []
    for square in board.pieces(chess.PAWN, color):
        file, rank = chess.square_file(square), chess.square_rank(square)
        blocked = False
        for adjacent in (file - 1, file, file + 1):
            for other in enemy.get(adjacent, []):
                if (other - rank) * forward > 0:
                    blocked = True
        if blocked:
            continue
        advance = rank if color == chess.WHITE else 7 - rank
        protected = bool(
            board.attackers(color, square) & board.pieces(chess.PAWN, color)
        )
        score += (advance - 1) / 5.0 + (0.5 if protected else 0.0)
        found.append(
            {
                "kind": "passed_pawn",
                "color": "white" if color else "black",
                "square": _sq(square),
                "rank_advanced": advance,
                "protected": protected,
            }
        )
    return score, found


def passed_pawns(board: chess.Board) -> FeatureValue:
    white, white_ev = _passed_for(board, chess.WHITE)
    black, black_ev = _passed_for(board, chess.BLACK)
    return FeatureValue("passed_pawns", white - black, white_ev + black_ev)


# Which ranks a hole is counted on, read from the point of view of the side the
# hole is a weakness *for*. Own half only: `relative` 4 and 5 are that side's
# fifth and sixth ranks, and an enemy piece settling there is sitting in its own
# camp, which costs the nominal owner of the hole nothing.
#
# The band ran to 5 until it was read. Over 1,154 positions, 44% of every hole
# counted fell on the far side of the board -- a3 scored as a weakness of
# Black's, a6 as a weakness of White's -- and the first line of the docstring
# below had said "own half" the whole time. `outposts` uses the same idiom the
# other way up (`relative >= 3`, because an outpost has to be *in* enemy
# territory) and was always right; this one contradicted its own description.
#
# Named rather than written inline so a test can vary the thing it is testing.
HOLE_RANKS = (2, 3)


def _holes_for(board: chess.Board, color: bool):
    """Squares in this side's own half that no pawn of theirs can cover again.

    Distinct from `king_weak_squares`, which only looks at the ring around the
    king. This is the board-wide version, and it is what an outpost is made of:
    a square is a hole because the pawns that could have guarded it are gone or
    have gone past, and pawns do not come back.

    The earlier version asked only whether an enemy piece *attacked* the hole,
    and that made this column a pawn counter. Fewer pawns means fewer squares any
    pawn can ever cover, so an endgame side with two pawns collected seventeen
    holes against the four-pawn side's three -- a fact about the pawn count
    wearing the name of a positional weakness. Measured over 1,909 positions the
    old value correlated +0.59 with the difference in pawn counts; requiring a
    safe occupation drops that to +0.29 and the firing rate from 86% to 72%.

    That is also why it never predicted anything of its own: `material` and
    `passed_pawns` were already saying the part of it that carried signal.

    The rank band is `HOLE_RANKS`; see the note above it for why it is the side's
    own half and not the four middle ranks it used to be.
    """
    forward = 1 if color == chess.WHITE else -1
    files = _pawn_files(board, color)
    # Where every enemy piece could legally move, indexed by destination. Built
    # once: asking per square would generate the move list thirty-two times.
    #
    # The turn is flipped on a copy so the *other* side's moves are the legal
    # ones. That is not a null move and does not have to be legal chess -- it is
    # a question about reach, asked on a board that is only ever read. A side in
    # check has its answers restricted by the check, which is the same
    # restriction their pieces are actually under.
    probe = board.copy(stack=False)
    probe.turn = not color
    reachable = {}
    for move in probe.legal_moves:
        if probe.piece_type_at(move.from_square) == chess.PAWN:
            continue
        reachable.setdefault(move.to_square, []).append(move.from_square)
    found = []
    for file in range(8):
        for rank in range(8):
            relative = rank if color == chess.WHITE else 7 - rank
            if not HOLE_RANKS[0] <= relative <= HOLE_RANKS[1]:
                continue
            square = chess.square(file, rank)
            coverable = False
            for adjacent in (file - 1, file + 1):
                for other in files.get(adjacent, []):
                    if (rank - other) * forward > 0:
                        coverable = True
            if coverable:
                continue
            # A hole is a weakness because an enemy piece can *sit* in it, not
            # because one attacks through it. Attacking a square in passing and
            # being able to occupy it are different facts, and the first one is
            # far commoner -- so the old test admitted almost every hole on the
            # board and the column fired in 72% of comparisons.
            #
            # And occupying it has to be worth doing: a square where the piece is
            # taken next move is not an outpost for anybody. `_safe_square` moves
            # the piece there before asking, which is the only way to ask.
            #
            # Enemy pawns do not count. A pawn arriving does not occupy the hole
            # so much as rebuild the structure around it, and then the question
            # of which squares are holes has to be asked again from scratch. That
            # narrows what this measures -- squares an enemy *piece* can use --
            # which is the honest name for it and the exact mirror of `outposts`.
            usable = [
                origin
                for origin in reachable.get(square, [])
                if _safe_square(
                    probe, probe.piece_type_at(origin), origin, square, not color
                )
            ]
            if not usable:
                continue
            found.append(
                {
                    "kind": "hole",
                    "color": "white" if color else "black",
                    "square": _sq(square),
                    "usable_by": sorted(_piece_at(board, origin) for origin in usable),
                }
            )
    return float(len(found)), found


def weak_squares(board: chess.Board) -> FeatureValue:
    white, white_ev = _holes_for(board, chess.WHITE)
    black, black_ev = _holes_for(board, chess.BLACK)
    return FeatureValue("weak_squares", black - white, white_ev + black_ev)


# How lopsided the pawns have to be before the bishop is *called* good or bad.
# The value below needs no threshold -- it grows with the square of the lean, so
# one pawn is already worth little next to a chain -- but a name does: "나쁜
# 비숍" off a single moved pawn is a verdict the position has not earned, and the
# prose repeats verdicts, not numbers.
STRUCTURE_MIN = 2


def _bad_bishop_for(board: chess.Board, color: bool):
    """How far the pawns in front of each bishop lean onto its own colour.

    chess.com: a bad bishop is "blocked by its own pawns, making its scope and
    the number of squares it controls very low", and the case they name is centre
    pawns *locked* on the same colour as the bishop. Two words in that do the
    work, and both were being ignored.

    "Locked" first: a pawn still on its starting square has not chosen a colour.
    An unmoved e7 pawn can go to e6 or to e5, one light and one dark, so counting
    it as fixed on either decides a question the position has not asked yet. In a
    gambit that is most of the board — four of Black's five pawns were still home
    in the position this was written for, and the old rule duly called their
    bishop bad. It was neither bad nor good; nothing had happened to it.

    Then the lean, rather than a count of blockers: one pawn that happens to
    share the bishop's colour is not a bad bishop, a structure fixed against it
    is. The value is signed, because the other direction is a real thing with a
    real name -- pawns on the opposite colour are a *good* bishop, and throwing
    that half away would need a second feature to say the same thing twice.

    Only pawns ahead of the bishop count, because those are the ones it is
    behind. A bishop developed outside its own chain is not a bad bishop, and
    treating it as one is why the first version of this measure fitted with the
    sign reversed -- the French light-squared bishop is bad on c8 and fine on a6,
    with the same pawns on the board either way.
    """
    forward = 1 if color == chess.WHITE else -1
    home = 1 if color == chess.WHITE else 6
    score = 0.0
    found = []
    for square in board.pieces(chess.BISHOP, color):
        light = square in chess.SquareSet(chess.BB_LIGHT_SQUARES)
        rank = chess.square_rank(square)
        ahead = [
            pawn
            for pawn in board.pieces(chess.PAWN, color)
            if (chess.square_rank(pawn) - rank) * forward >= 0
            and chess.square_rank(pawn) != home
        ]
        mine = [p for p in ahead if (p in chess.SquareSet(chess.BB_LIGHT_SQUARES)) == light]
        theirs = [p for p in ahead if (p in chess.SquareSet(chess.BB_LIGHT_SQUARES)) != light]
        lean = len(mine) - len(theirs)
        if lean == 0:
            continue
        # Squared, and signed: one pawn out of line is worth a ninth of a chain
        # three deep rather than a third of it. A hard cut-off did the same job
        # with an invented number in it, and the number had to be defended
        # separately from the idea.
        score += lean * abs(lean)
        if abs(lean) < STRUCTURE_MIN:
            continue
        found.append(
            {
                "kind": "bad_bishop" if lean > 0 else "good_bishop",
                "color": "white" if color else "black",
                "bishop": _piece_at(board, square),
                "complex": "light" if light else "dark",
                "pawns_on_its_colour": sorted(_sq(p) for p in mine),
                "pawns_on_the_other": sorted(_sq(p) for p in theirs),
            }
        )
    return score, found


def _development_for(board: chess.Board, color: bool):
    """Pieces still sitting where the game started them.

    The axis a gambit actually buys, and the one nothing here was measuring. It
    was being counted by accident and wrongly: `worst_piece` reported the fewest
    squares any minor piece had, and 156 of the 182 zero readings over 904
    positions were pieces on their starting square with their own unmoved pawns
    in front — the opening working normally, read as a weakness. Removing that
    left the axis empty, so here it is on purpose.

    Minor pieces and the king's castling, which is what "development" means. Rooks
    are left out: they are developed by the rank clearing rather than by moving,
    so a rook on a1 says nothing on move eight and everything on move thirty, and
    a count cannot tell those apart.
    """
    home = {
        chess.KNIGHT: (chess.B1, chess.G1) if color == chess.WHITE else (chess.B8, chess.G8),
        chess.BISHOP: (chess.C1, chess.F1) if color == chess.WHITE else (chess.C8, chess.F8),
    }
    asleep = []
    for piece_type, squares in home.items():
        for square in squares:
            piece = board.piece_at(square)
            if piece and piece.piece_type == piece_type and piece.color == color:
                asleep.append(_piece_at(board, square))
    # The king counts as developed once it has castled, and not before. Reading
    # it as "still on e1 with the right to castle" gave credit for losing that
    # right: the king driven to d7 in Carlsen-Lazavik came out *better* developed
    # than the one that had not moved, when a king walking in the centre is the
    # thing the whole gambit was for.
    castled = chess.SquareSet(
        [chess.G1, chess.C1] if color == chess.WHITE else [chess.G8, chess.C8]
    )
    uncastled = board.king(color) not in castled
    score = float(len(asleep)) + (1.0 if uncastled else 0.0)
    evidence = []
    if score:
        evidence.append(
            {
                "kind": "undeveloped",
                "color": "white" if color else "black",
                "pieces": sorted(asleep),
                "king_still_home": uncastled,
            }
        )
    return score, evidence


def development(board: chess.Board) -> FeatureValue:
    white, white_ev = _development_for(board, chess.WHITE)
    black, black_ev = _development_for(board, chess.BLACK)
    return FeatureValue("development", black - white, white_ev + black_ev)


def _bad_knight_for(board: chess.Board, color: bool):
    """Squares each knight loses by standing near the edge.

    "Knight on the rim is dim" (Tarrasch), and the reason every source gives is
    the count: a knight in the centre reaches eight squares, one on the edge four,
    one in the corner two. Read off an empty board on purpose -- this is about
    where the knight is standing, not about what is in its way, which is
    `mobility`'s question and answered by a different number.
    """
    score = 0.0
    found = []
    for square in board.pieces(chess.KNIGHT, color):
        reach = chess.popcount(chess.BB_KNIGHT_ATTACKS[square])
        if reach >= 8:
            continue
        score += 8 - reach
        found.append(
            {
                "kind": "bad_knight",
                "color": "white" if color else "black",
                "knight": _piece_at(board, square),
                "squares": reach,
            }
        )
    return score, found


def bad_knight(board: chess.Board) -> FeatureValue:
    white, white_ev = _bad_knight_for(board, chess.WHITE)
    black, black_ev = _bad_knight_for(board, chess.BLACK)
    return FeatureValue("bad_knight", black - white, white_ev + black_ev)


def bad_bishop(board: chess.Board) -> FeatureValue:
    white, white_ev = _bad_bishop_for(board, chess.WHITE)
    black, black_ev = _bad_bishop_for(board, chess.BLACK)
    return FeatureValue("bad_bishop", black - white, white_ev + black_ev)


def _space_for(board: chess.Board, color: bool):
    """Room behind the pawn front, file by file, that enemy pawns cannot reach.

    The previous definition counted empty, unattacked squares on the central
    files of this side's own first three ranks, and skipped squares its own
    pawns stood on. Advancing a pawn emptied a square and the count went up;
    trading the pawn off did the same. It measured how clear the back was, not
    how much room had been taken, and those move in opposite directions on the
    move that defines the concept.

    Whether it predicted anything did not settle it -- it predicted nothing, and
    so do several columns that are correctly defined. What settled it is that a
    pawn push is what a space advantage *is*, and the number fell when one
    happened.

    The reviewer's formula was "squares in the enemy half my pawns cover and
    theirs do not". Implemented literally it says something odd: after 1.e4 d5
    2.e5 the White pawn covers d6 and f6, both still guarded by the c7 and e7
    pawns, so White scores zero for the push that gains the most space in the
    line. Requiring *uncontested* control punishes exactly the deep advance it
    should reward.

    So the frontier is what is counted. On each file, take this side's most
    advanced pawn and count the squares behind it that enemy pawns do not
    attack. Pushing moves the frontier up and adds squares; losing the pawn
    removes the file's contribution entirely; a capture that advances a pawn does
    both, correctly.

    Rank one is excluded -- the back rank is where the pieces start, not room
    they gained -- and all files count. A window of central files would be one
    more unexplained constant, and the enemy-pawn filter already discounts the
    squares nobody is fighting over.

    The reviewer's further step -- whether a piece can actually use the room --
    is deliberately not taken. It folds `mobility` into this, and the two are
    meant to be separate questions.
    """
    denied = _pawn_attack_mask(board, not color)
    pawns = board.pieces(chess.PAWN, color)
    home = 1 if color == chess.WHITE else 6
    held = []
    for file in range(8):
        ranks = [chess.square_rank(s) for s in pawns if chess.square_file(s) == file]
        if not ranks:
            continue
        front = max(ranks) if color == chess.WHITE else min(ranks)
        behind = (
            range(home, front) if color == chess.WHITE else range(front + 1, home + 1)
        )
        held += [
            square
            for rank in behind
            if (square := chess.square(file, rank)) not in denied
        ]
    return float(len(held)), [
        {
            "kind": "space",
            "color": "white" if color else "black",
            "squares": [chess.square_name(square) for square in sorted(held)],
        }
    ]


def space(board: chess.Board) -> FeatureValue:
    white, white_ev = _space_for(board, chess.WHITE)
    black, black_ev = _space_for(board, chess.BLACK)
    return FeatureValue("space", white - black, white_ev + black_ev)


# The four squares chess.com calls the centre, and the c3-f6 box it calls the
# extended centre. Kept as module constants so the definition is one place.
CENTRE = (chess.D4, chess.E4, chess.D5, chess.E5)
EXTENDED_CENTRE = tuple(
    chess.square(file, rank)
    for file in range(2, 6)
    for rank in range(2, 6)
    if chess.square(file, rank) not in (chess.D4, chess.E4, chess.D5, chess.E5)
)

# Three hand-set numbers, and the only ones in this feature: a pawn controls a
# central square more firmly than a piece does, because the piece can be chased
# off by a pawn and the pawn cannot be chased off by anything worth trading. The
# regression fits the overall scale; these only fix the ratios inside the count.
PAWN_CONTROL = 2.0
PIECE_CONTROL = 1.0
EXTENDED_SHARE = 0.5


def _centre_control_for(board: chess.Board, color: bool):
    """Occupation of, and attacks on, the central squares. NOT a fitted feature.

    Written to test a specific claim and kept to record that the claim was
    false. `doubled_pawns` and `open_files` both fitted with the sign reversed in
    the top band, and both are produced by the same move - a capture toward the
    centre doubles a pawn, opens a file, and wins the centre at once - so the
    prediction was that giving the centre its own column would let it reclaim the
    evaluation gain and release the other two.

    It did not. Adding this column moved `doubled_pawns` from -3.42 to -3.33 and
    `open_files` from -5.34 to -5.41, and left every other weight identical to
    two decimals. On its own the measure predicts strongly (solo t 11.4) and
    beside the others it says nothing (joint t 0.6): `mobility` correlates with
    it at +0.42 and already carries what it knows. Held out over five
    position-split folds, R^2 was 0.0613 with both, 0.0621 with mobility alone,
    0.0592 with this alone, and 0.0594 with neither - a set of numbers with one
    meaning, which is that neither column earns its place by prediction.

    Left out of FEATURES and FEATURE_NAMES rather than deleted, because the
    negative result is worth more than the code: the centre is not missing from
    the model, it is spelled `mobility`.

    The definition, if it is ever wanted: this is not `space`, which counts safe
    squares behind one's own pawns and so says nothing about d5 for White.
    Occupying a central square with a pawn counts as controlling it, since a pawn
    on e4 both stands there and attacks d5 and f5.
    """
    pawns = board.pieces(chess.PAWN, color)
    score = 0.0
    held = []
    for squares, share in ((CENTRE, 1.0), (EXTENDED_CENTRE, EXTENDED_SHARE)):
        for square in squares:
            attackers = board.attackers(color, square)
            by_pawn = len(attackers & pawns)
            by_piece = len(attackers) - by_pawn
            occupied = square in pawns
            value = by_pawn * PAWN_CONTROL + by_piece * PIECE_CONTROL
            if occupied:
                value += PAWN_CONTROL
            if not value:
                continue
            score += value * share
            if share == 1.0:
                held.append(
                    {
                        "kind": "centre_control",
                        "color": "white" if color else "black",
                        "square": chess.square_name(square),
                        "pawn_attacks": by_pawn,
                        "piece_attacks": by_piece,
                        "pawn_stands_there": occupied,
                    }
                )
    return score, held


def centre_control(board: chess.Board) -> FeatureValue:
    white, white_ev = _centre_control_for(board, chess.WHITE)
    black, black_ev = _centre_control_for(board, chess.BLACK)
    return FeatureValue("centre_control", white - black, white_ev + black_ev)


def _pawn_safe(board: chess.Board, square: int, color: bool) -> bool:
    """No enemy pawn can ever advance to attack this square.

    A piece that can be kicked by a pawn is a visitor; one that cannot is a
    fixture.  The distinction is what separates a knight parked on f5 from a
    knight passing through it, and it applies to outposts and to attackers
    around the king alike.
    """
    rank = chess.square_rank(square)
    file = chess.square_file(square)
    forward = 1 if color == chess.WHITE else -1
    for adj in (file - 1, file + 1):
        if not 0 <= adj <= 7:
            continue
        step = rank + forward
        while 0 <= step <= 7:
            piece = board.piece_at(chess.square(adj, step))
            if piece and piece.piece_type == chess.PAWN and piece.color != color:
                return False
            step += forward
    return True


def _is_outpost(board: chess.Board, square: int, color: bool) -> bool:
    """Square in enemy territory, pawn-protected, unreachable by enemy pawns."""
    rank = chess.square_rank(square)
    relative = rank if color == chess.WHITE else 7 - rank
    if relative < 3:
        return False
    if not board.attackers(color, square) & board.pieces(chess.PAWN, color):
        return False
    return _pawn_safe(board, square, color)


def outposts(board: chess.Board) -> FeatureValue:
    evidence = []
    score = {chess.WHITE: 0.0, chess.BLACK: 0.0}
    for color in (chess.WHITE, chess.BLACK):
        for piece_type in (chess.KNIGHT, chess.BISHOP):
            for square in board.pieces(piece_type, color):
                if not _is_outpost(board, square, color):
                    continue
                weight = 1.0 if piece_type == chess.KNIGHT else 0.6
                enemy_king_zone = _king_zone(board, not color)
                hits = chess.SquareSet(board.attacks_mask(square)) & enemy_king_zone
                if hits:
                    weight += 0.5
                score[color] += weight
                evidence.append(
                    {
                        "kind": "outpost",
                        "color": "white" if color else "black",
                        "piece": _piece_at(board, square),
                        "square": _sq(square),
                        "hits_king_zone": sorted(_sq(s) for s in hits),
                    }
                )
    return FeatureValue("outposts", score[chess.WHITE] - score[chess.BLACK], evidence)


# --------------------------------------------------------------------------
# 5. open files
# --------------------------------------------------------------------------

def open_files(board: chess.Board) -> FeatureValue:
    """Rooks and queens on files their own pawns have left.

    Two attempts to sharpen this failed and are recorded so they are not
    retried: requiring an entry square unblocked by enemy pawns changed nothing
    at all (it holds on every pawnless file), and requiring an undefended entry
    square on the seventh or eighth rank made the fit strictly worse.  The
    feature fires in a third of all positions and predicts the evaluation gap in
    neither form, so its weight is currently zero.

    Three later attempts to explain the top band's significant *negative* weight
    also failed, and are recorded for the same reason:

    * the band story — that the engine's best move among near-equals is the
      concrete one, so slow goods fit negative. Split by whether either move is
      forcing, this is more negative among the quiet pairs (t -4.7), not less.
    * a pawn-loss confound — the file opens because your own pawn was captured,
      so the feature rises exactly when material falls. Its correlation with the
      material diff is +0.10, the wrong way round.
    * a single collinear partner. Removing `king_open_lines`, its strongest,
      leaves -4.7.

    What is established: the correlation with the evaluation gap is 0.01, and the
    feature is near-silent alone (solo t -1.7) while significant beside the
    others (t -4.1). That shape is suppression among collinear columns rather
    than a statement about open files, and it is consistent with the simplest
    reading, which is the one above — the feature carries no marginal signal in
    this band at all.

    And the reason is scarcity rather than blindness. Selecting the positions
    where the concept decides something — the engine's best move is a rook or
    queen arriving quietly on a file its own pawns have left, and it beats the
    runner-up by 25 cp or more — leaves 12 of 573. The feature registers the
    change in every one of them, by +0.66 on average, which the wide band's
    weight makes 14 cp of a 98 cp gap. It sees the thing; the thing is rare.

    Which is also why the obvious refinements cannot be tested in the top band:
    doubling rooks being worth more than two single ones, a semi-open file being
    worth more when the pawn on it is weak, occupation not being the same as
    control when the opponent can contest the file. Twelve positions cannot
    separate any of those from noise. The wide band is where that work belongs —
    the feature already earns +21.6 there, against moves a human actually chose,
    and amateurs miss files far more often than the engine's own second choice
    does.
    """
    evidence = []
    score = {chess.WHITE: 0.0, chess.BLACK: 0.0}
    for file in range(8):
        mask = chess.SquareSet(chess.BB_FILES[file])
        white_pawns = mask & board.pieces(chess.PAWN, chess.WHITE)
        black_pawns = mask & board.pieces(chess.PAWN, chess.BLACK)
        for color in (chess.WHITE, chess.BLACK):
            own_pawns = white_pawns if color == chess.WHITE else black_pawns
            enemy_pawns = black_pawns if color == chess.WHITE else white_pawns
            if own_pawns:
                continue
            kind = "open_file" if not enemy_pawns else "semi_open_file"
            weight = 1.0 if kind == "open_file" else 0.6
            for piece_type in (chess.ROOK, chess.QUEEN):
                for square in mask & board.pieces(piece_type, color):
                    score[color] += weight * (1.0 if piece_type == chess.ROOK else 0.5)
                    evidence.append(
                        {
                            "kind": kind,
                            "color": "white" if color else "black",
                            "piece": _piece_at(board, square),
                            "file": chess.FILE_NAMES[file],
                        }
                    )
    return FeatureValue("open_files", score[chess.WHITE] - score[chess.BLACK], evidence)


# --------------------------------------------------------------------------

def _compression_for(board: chess.Board, color: bool, ratio: bool = False):
    """How far this side can narrow the other's choices with a forcing move.

    The first draft of this was "replies to the strongest threat", and choosing
    the strongest threat is a chess judgement -- the one thing the feature layer
    is built not to make. Taking the minimum over every forcing move removes it:
    a minimum is an aggregate, not an opinion.

    Forcing moves are checks and captures, which the rules decide. What the
    number then says is how few answers the other side can be left with, and
    that is all it says. It is deliberately *not* called pressure: a queen thrown
    away with check also leaves one legal reply, and scores as high as a mating
    attack. The name is the claim.

    Quiet positions have no forcing move at all, so the minimum is over an empty
    set. It reports the opponent's current count -- "cannot compress at all" --
    rather than zero, which would read as maximum compression.

    `ratio` divides by that same count, because the raw number falls in an
    endgame for a reason that has nothing to do with force: with fewer pieces
    there are fewer legal moves to begin with.
    """
    probe = board.copy(stack=False)
    probe.turn = color
    if probe.is_check() and color != board.turn:
        # Flipping the turn can leave the side to move already in check, which is
        # not a position chess reaches. Their "forcing moves" there are answers
        # to a check, so the question does not apply.
        return None
    try:
        forcing = [
            move
            for move in probe.legal_moves
            if probe.gives_check(move) or probe.is_capture(move)
        ]
    except ValueError:
        return None
    # How many answers the other side has before anything is forced. The
    # denominator of the ratio, and the fallback when nothing is forcing.
    after = probe.copy(stack=False)
    after.turn = not color
    if after.is_check():
        return None
    baseline = after.legal_moves.count()
    if not forcing:
        return 1.0 if ratio else float(baseline)
    least = baseline
    for move in forcing:
        probe.push(move)
        least = min(least, probe.legal_moves.count())
        probe.pop()
    if ratio:
        return least / baseline if baseline else 1.0
    return float(least)


def reply_compression(board: chess.Board, ratio: bool = True) -> FeatureValue:
    """Signed so that more of it is better for White, like every other column.

    `_compression_for(White)` is how few replies White can leave Black with, so a
    *small* number is White doing well. The subtraction is therefore black minus
    white the other way round from most features here, and the docstring says so
    because the sign is the part that gets copied wrong.
    """
    white = _compression_for(board, chess.WHITE, ratio)
    black = _compression_for(board, chess.BLACK, ratio)
    if white is None or black is None:
        return FeatureValue("reply_compression", 0.0, [])
    return FeatureValue(
        "reply_compression",
        black - white,
        [
            {
                "kind": "reply_compression",
                "white_can_force_black_down_to": round(white, 2),
                "black_can_force_white_down_to": round(black, 2),
            }
        ],
    )


FEATURES = [
    material,
    threats,
    loose_pieces,
    tempo,
    king_shelter,
    king_weak_squares,
    king_pressure,
    king_open_lines,
    attack_force,
    defense_gap,
    colour_complex,
    mobility,
    outposts,
    open_files,
    isolated_pawns,
    doubled_pawns,
    backward_pawns,
    passed_pawns,
    weak_squares,
    bad_bishop,
    bad_knight,
    development,
    space,
    reply_compression,
]
FEATURE_NAMES = [
    "material",
    "threats",
    "loose_pieces",
    "tempo",
    "king_shelter",
    "king_weak_squares",
    "king_pressure",
    "king_open_lines",
    "attack_force",
    "defense_gap",
    "colour_complex",
    "mobility",
    "outposts",
    "open_files",
    "isolated_pawns",
    "doubled_pawns",
    "backward_pawns",
    "passed_pawns",
    "weak_squares",
    "bad_bishop",
    "bad_knight",
    "development",
    "space",
    "reply_compression",
]


def evaluate(board: chess.Board) -> dict:
    """Run every feature.  Returns {name: FeatureValue}."""
    return {f.__name__: f(board) for f in FEATURES}
