"""Differential why: find where the eval gap lives, then read the reason off the board.

Mohit, 2026-10-31, after run 5 of the why-engine regression set (docs/qa/
why_engine_regression_baseline_2026_10_30.md): "do all these changes, and then
wire it to UI". The three changes, in the order they run here:

  1. MEASURE BOTH BRANCHES. The reply locator (counterfactual.py) is run on the
     branch after the played move AND on the branch after the better move. On
     its own the played-branch drop measures how forced the opponent's reply
     is, not how bad the move was: on the eight good moves in the set it ran
     from 25 to 661 cp. Against the gap it sorts the bad moves into families:
         punished  removing the reply recovers most of the gap   (7 of 25)
         missed    the gap stays; the better move's own line carries it (13)
         mixed     in between                                         (5)
     Thirteen of the sixteen silent positions in run 5 were in the missed and
     mixed families, where every played-branch tool is blind by construction.

  2. PUNISHED: EXPLAIN BACKWARDS FROM THE REPLY. Take the located reply, list
     the relations in its footprint (what it checks, captures, attacks, which
     line it opens) after the played move and after the better move, and keep
     only what exists on the played branch. One computation covers every shape
     seen in the set, and it is what stops the true-but-irrelevant answers:
         ho01  Qxe6 gives check only after Kc8            -> kept
         ho10  the pawn recapturing on d5 hits the c6 bishop only after Nxd5
         ho09  c3 hits the moved piece after BOTH Bb4+ and Nd4 -> excluded
         ho12  Nxe5 takes the e5 pawn after BOTH Nd4 and Nb8   -> excluded
     The moved piece is never its own reason: a relation whose object is the
     piece the mover just moved cancels across the branches by key, which is
     the "moved-piece artefact" that made 57 of Codex's 101 chain candidates.

  3. MISSED: THE BETTER MOVE'S FIRST FORCING CONSEQUENCE, read along the
     engine line by services/punishment_resolver.resolve_missed, which already
     walks a line to a quiet position and names what changes hands. Nothing is
     claimed that the line does not show.

The engine decides; this module writes a short deterministic sentence and a
facts dict. services/why_words.py turns the facts into English with gpt-6-luna
and refuses any chess the facts do not contain. Numbers never reach a sentence.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

import chess

from services.stored_line_verifier import parse_legal_move
from .contracts import ReasoningConfig, fingerprint
from .counterfactual import probe_reply_dependency
from .search import SearchSession

SCHEMA_VERSION = "reasoning.differential.v1"

# Family boundaries on drop / gap. Chosen from the run-5 join of the locator
# rows with the hand grades: every position the judge called "one reply
# carries it" sat at or above 0.6, every missed opportunity below 0.4.
PUNISHED_MIN_RATIO = 0.6
MISSED_MAX_RATIO = 0.4

# A mate score, for gap arithmetic only. Typed scores are kept in the output.
MATE_CP = 10_000

PIECE_NAME = {chess.PAWN: "pawn", chess.KNIGHT: "knight", chess.BISHOP: "bishop",
              chess.ROOK: "rook", chess.QUEEN: "queen", chess.KING: "king"}
_VALUE = {chess.PAWN: 100, chess.KNIGHT: 300, chess.BISHOP: 300, chess.ROOK: 500, chess.QUEEN: 900, chess.KING: 10_000}

# A net swing on one square of less than a pawn is an even exchange.
EXCHANGE_MIN_CP = 100
# The ledger reads this many plies of each line. Beyond it a pawn that falls
# is the engine's horizon, not the move's consequence (ho08: a pawn on ply 29).
LEDGER_PLIES = 12
# An unanswered capture is this move's consequence only while the line is
# still forcing; an exchange, being a concrete event both sides took part in,
# may sit a little deeper (ho05: the f1 exchange on plies 9 and 10).
UNANSWERED_MAX_PLY = 6
EXCHANGE_MAX_PLY = 10

# Which cause to lead with when the footprint diff finds several. Check and a
# lost guard are the ones a 1200 player can act on next game; a bare "attacks"
# is the weakest claim and goes last.
CAUSE_RANK = ("check", "hanging", "lost_guard", "uncovers_attack", "attacks")


# ---------------------------------------------------------------- scores --

def score_cp(score: Optional[dict]) -> Optional[int]:
    """A typed score as one integer for gap arithmetic. Mate keeps its sign."""
    if not score:
        return None
    if score["kind"] == "cp":
        return int(score["value"])
    n = int(score["value"])
    if n == 0:
        return -MATE_CP
    return (MATE_CP - abs(n)) if n > 0 else -(MATE_CP - abs(n))


def classify_gap(gap_cp: Optional[int], rating: Optional[int]) -> str:
    """good / inaccuracy / mistake / blunder from the single rating-aware table."""
    if gap_cp is None:
        return "unknown"
    from services.rating_resolver import move_classification_thresholds
    t = move_classification_thresholds(rating)
    change = -int(gap_cp)
    if change >= t["good"]:
        return "good"
    if change >= t["inaccuracy"]:
        return "inaccuracy"
    if change >= t["mistake"]:
        return "mistake"
    return "blunder"


def _record_by_id(session, record_id: Optional[str]):
    for record in session.records:
        if record.id == record_id:
            return record
    return None


def _owner(victim_is_mover: bool, mover_is_user: bool) -> str:
    """'your' or 'their' for the side a piece belongs to, read from whose move it is."""
    return ("your" if mover_is_user else "their") if victim_is_mover else ("their" if mover_is_user else "your")


# ------------------------------------------------------------- footprint --

def reply_footprint(board_before_reply: chess.Board, reply: chess.Move,
                    moved_to: Optional[int]) -> Dict[Tuple, Dict[str, Any]]:
    """Every relation the reply creates, keyed so the same relation on the other
    branch cancels.

    `moved_to` is where the side to be explained just moved. An attack on that
    square is keyed as "attacks_moved_piece" with no square, so that a reply
    hitting the bishop on b4 after Bb4+ cancels against the same reply hitting
    the knight on d4 after Nd4 (ho09). A capture is keyed by square only, so a
    recapture on the exchange square cancels whatever piece stood there (ho10).
    """
    if reply not in board_before_reply.legal_moves:
        return {}
    actor = board_before_reply.turn
    victim = not actor
    before = board_before_reply
    after = before.copy()
    after.push(reply)
    out: Dict[Tuple, Dict[str, Any]] = {}

    if after.is_check():
        out[("check",)] = {"kind": "check"}

    captured_square = reply.to_square
    captured = before.piece_at(reply.to_square)
    if captured is None and before.is_en_passant(reply):
        captured_square = chess.square(chess.square_file(reply.to_square), chess.square_rank(reply.from_square))
        captured = before.piece_at(captured_square)
    if captured is not None:
        out[("captures_on", chess.square_name(captured_square))] = {
            "kind": "captures", "piece": PIECE_NAME[captured.piece_type],
            "square": chess.square_name(captured_square),
            "recapturable": bool(after.attackers(victim, reply.to_square)),
            "on_moved_square": captured_square == moved_to}

    landed = reply.to_square
    for square in after.attacks(landed):
        target = after.piece_at(square)
        if target is None or target.color != victim or target.piece_type == chess.KING:
            continue
        defenders = after.attackers(victim, square)
        detail = {"kind": "attacks", "piece": PIECE_NAME[target.piece_type],
                  "square": chess.square_name(square),
                  "defenders": sorted(chess.square_name(s) for s in defenders)}
        if square == moved_to:
            out[("attacks_moved_piece",)] = {**detail, "kind": "attacks_moved_piece"}
        else:
            out[("attacks", PIECE_NAME[target.piece_type], chess.square_name(square))] = detail

    # Lines opened by the reply's departure: an own slider that now reaches an
    # enemy piece it did not reach before the reply.
    for own_square, piece in after.piece_map().items():
        if piece.color != actor or own_square == landed:
            continue
        if piece.piece_type not in (chess.BISHOP, chess.ROOK, chess.QUEEN):
            continue
        gained = set(after.attacks(own_square)) - set(before.attacks(own_square))
        for square in gained:
            target = after.piece_at(square)
            if target is None or target.color != victim:
                continue
            out[("uncovers_attack", PIECE_NAME[target.piece_type], chess.square_name(square))] = {
                "kind": "uncovers_attack", "piece": PIECE_NAME[target.piece_type],
                "square": chess.square_name(square), "slider_square": chess.square_name(own_square),
                "check": target.piece_type == chess.KING}
    return out


def differential_causes(root: chess.Board, played: chess.Move, alternative: chess.Move,
                        reply_uci: str, *, mover_is_user: bool) -> List[Dict[str, Any]]:
    """Relations the reply has after the played move and not after the better
    move, each with a deterministic plain-English sentence.

    Empty means the reply does the same thing on both branches: true, and not
    the reason this move was worse than the other one.
    """
    after_played = root.copy()
    after_played.push(played)
    after_alt = root.copy()
    after_alt.push(alternative)
    reply = chess.Move.from_uci(reply_uci)
    if reply not in after_played.legal_moves:
        return []
    played_san = root.san(played)
    alt_san = root.san(alternative)
    reply_san = after_played.san(reply)
    mover_owner = _owner(True, mover_is_user)
    a = reply_footprint(after_played, reply, played.to_square)
    reply_legal_on_alt = reply in after_alt.legal_moves
    b = reply_footprint(after_alt, reply, alternative.to_square) if reply_legal_on_alt else {}

    causes: List[Dict[str, Any]] = []

    if not reply_legal_on_alt:
        # The played move is what makes the reply possible at all. The only
        # relations that can be its reason are the ones touching the squares
        # the played move changed; the rest of the footprint would exist for
        # any reply at all.
        touched = {played.to_square, played.from_square}
        cap = a.get(("captures_on", chess.square_name(played.to_square)))
        # A piece moved onto a square where it is simply taken is hanging. A
        # piece that CAPTURED there and is taken back is an exchange, and the
        # exchange ledger judges exchanges (ho02: Nxf5 exf5 is a knight for a
        # knight, not a knight lost; ho15: Bxc3 bxc3 likewise).
        if cap is not None and root.piece_at(played.to_square) is None:
            causes.append({"kind": "hanging", "reply": reply_san, "piece": cap["piece"], "square": cap["square"],
                           "recapturable": cap["recapturable"], "owner": mover_owner,
                           "text": (f"After {played_san}, {reply_san} simply takes {mover_owner} {cap['piece']} on {cap['square']}."
                                    + ("" if cap["recapturable"] else " Nothing can take back."))})
        for key, detail in a.items():
            if detail["kind"] == "uncovers_attack" and chess.parse_square(detail["slider_square"]) not in touched:
                continue
            if detail["kind"] in ("attacks",) and chess.parse_square(detail["square"]) in touched:
                continue
            if detail["kind"] == "check":
                causes.append({"kind": "check", "reply": reply_san, "owner": mover_owner,
                               "text": f"After {played_san}, {reply_san} comes with check. After {alt_san} that reply is not there."})
        return _ranked(causes)

    for key, detail in a.items():
        kind = detail["kind"]
        if kind == "attacks_moved_piece":
            continue                      # the mover's own relocation is never its reason
        if key in b:
            if kind == "attacks":
                # Same target on both branches: the difference can only be in
                # who guards it. Guards present after the better move and
                # absent after the played move are what the played move cost.
                # A guard only matters when the attacker is worth at least the
                # target: a pawn attacking a knight chases it whether or not it
                # is guarded (ho07), so that is not a lost-guard reason.
                lost = set(b[key]["defenders"]) - set(detail["defenders"])
                reply_piece = after_played.piece_at(reply.from_square)
                target_type = {v: k for k, v in PIECE_NAME.items()}[detail["piece"]]
                attacker_worth_it = reply_piece is not None and _VALUE[reply_piece.piece_type] >= _VALUE[target_type]
                if lost and not detail["defenders"] and attacker_worth_it:
                    guard_sq = sorted(lost)[0]
                    guard_square = chess.parse_square(guard_sq)
                    guard_piece = after_alt.piece_at(guard_square)
                    guard_name = PIECE_NAME[guard_piece.piece_type] if guard_piece else "piece"
                    target_square = chess.parse_square(detail["square"])
                    # The mover's own piece guards the mover's piece: both are root.turn's.
                    guarded_before = guard_square in root.attackers(root.turn, target_square)
                    if guard_square == played.from_square:
                        text = (f"{played_san} moved the {guard_name} that was guarding {detail['square']}, so "
                                f"{reply_san} hits {mover_owner} {detail['piece']} on {detail['square']} with nothing defending it.")
                    elif guarded_before:
                        text = (f"After {played_san}, {mover_owner} {detail['piece']} on {detail['square']} has lost "
                                f"its guard on {guard_sq}, and {reply_san} attacks it.")
                    else:
                        text = (f"{alt_san} would have let the {guard_name} on {guard_sq} guard {detail['square']}. "
                                f"After {played_san} nothing does, and {reply_san} attacks {mover_owner} {detail['piece']} there.")
                    causes.append({"kind": "lost_guard", "reply": reply_san, "piece": detail["piece"],
                                   "square": detail["square"], "guard_square": guard_sq, "guard_piece": guard_name,
                                   "guard_was_the_moved_piece": guard_square == played.from_square,
                                   "owner": mover_owner, "text": text})
            continue
        if kind == "check":
            causes.append({"kind": "check", "reply": reply_san, "owner": mover_owner,
                           "text": f"After {played_san}, {reply_san} comes with check. After {alt_san} it does not."})
        elif kind == "attacks":
            defended = bool(detail["defenders"])
            tail = "" if defended else " Nothing defends it."
            causes.append({"kind": "attacks", "reply": reply_san, "piece": detail["piece"], "square": detail["square"],
                           "defended": defended, "owner": mover_owner,
                           "text": (f"After {played_san}, {reply_san} hits {mover_owner} {detail['piece']} on "
                                    f"{detail['square']}. After {alt_san} it would not.{tail}")})
        elif kind == "captures":
            if detail["on_moved_square"]:
                continue                  # keyed by square; a different piece on the exchange square is the exchange
            causes.append({"kind": "hanging", "reply": reply_san, "piece": detail["piece"], "square": detail["square"],
                           "recapturable": detail["recapturable"], "owner": mover_owner,
                           "text": (f"After {played_san}, {reply_san} takes {mover_owner} {detail['piece']} on {detail['square']}. "
                                    f"After {alt_san} there is nothing to take there.")})
        elif kind == "uncovers_attack":
            what = "king" if detail["check"] else detail["piece"]
            causes.append({"kind": "uncovers_attack", "reply": reply_san, "piece": what, "square": detail["square"],
                           "slider_square": detail["slider_square"], "owner": mover_owner,
                           "text": (f"After {played_san}, {reply_san} opens the line from {detail['slider_square']} to "
                                    f"{mover_owner} {what} on {detail['square']}. After {alt_san} that line stays closed.")})
    return _ranked(causes)


def _ranked(causes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(causes, key=lambda c: CAUSE_RANK.index(c["kind"]) if c["kind"] in CAUSE_RANK else len(CAUSE_RANK))


# ----------------------------------------------------------------- ledger --

def exchange_ledger(root: chess.Board, line_san: Sequence[str], mover: chess.Color,
                    max_plies: int = LEDGER_PLIES) -> List[Dict[str, Any]]:
    """Captures along a line, grouped by the square they happen on.

    `line_san` starts with the move being judged, so its own capture opens the
    first group and a recapture closes it as an exchange. `net_cp` is from the
    mover's side: what the mover won on that square minus what it lost there.
    A line is read, never evaluated: this is the engine's continuation.
    """
    board = root.copy()
    groups: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []
    for ply, san in enumerate(list(line_san)[:max_plies]):
        move = parse_legal_move(board, san)
        if move is None:
            break
        captured_square = move.to_square
        captured = board.piece_at(move.to_square)
        if captured is None and board.is_en_passant(move):
            captured_square = chess.square(chess.square_file(move.to_square), chess.square_rank(move.from_square))
            captured = board.piece_at(captured_square)
        if captured is not None:
            name = chess.square_name(captured_square)
            if name not in groups:
                groups[name] = {"square": name, "plies": [], "mover_won": [], "mover_lost": [],
                                "first_by_mover": board.turn == mover}
                order.append(name)
            g = groups[name]
            g["plies"].append({"ply": ply, "san": board.san(move), "by_mover": board.turn == mover,
                               "captured": PIECE_NAME[captured.piece_type]})
            (g["mover_won"] if board.turn == mover else g["mover_lost"]).append(PIECE_NAME[captured.piece_type])
        board.push(move)
    by_name = {v: k for k, v in PIECE_NAME.items()}
    last_ply = min(len(line_san), max_plies) - 1
    for g in groups.values():
        g["net_cp"] = sum(_VALUE[by_name[p]] for p in g["mover_won"]) - sum(_VALUE[by_name[p]] for p in g["mover_lost"])
        # A group whose last capture is the line's final move may be missing
        # its recapture (ho05: Bxf1 at the horizon, Rxf1 one ply beyond). It
        # is unknown only if a recapture is actually possible on that square.
        square = chess.parse_square(g["square"])
        g["open"] = (g["plies"][-1]["ply"] >= last_ply
                     and any(m.to_square == square for m in board.legal_moves))
    return [groups[s] for s in order]


def _same_exchange(g: Dict[str, Any], other: Sequence[Dict[str, Any]]) -> bool:
    return any(o["square"] == g["square"] and abs(o["net_cp"] - g["net_cp"]) < EXCHANGE_MIN_CP for o in other)


def _open(g: Dict[str, Any], line_plies: int) -> bool:
    """Unknown: the line ends on this group's capture and a recapture is legal."""
    return bool(g.get("open"))


def closed_groups(ledger: Sequence[Dict[str, Any]], line_plies: int) -> List[Dict[str, Any]]:
    return [g for g in ledger if not _open(g, line_plies)]


def _near_enough(g: Dict[str, Any]) -> bool:
    exchange = bool(g["mover_won"]) and bool(g["mover_lost"])
    return g["plies"][0]["ply"] <= (EXCHANGE_MAX_PLY if exchange else UNANSWERED_MAX_PLY)


def first_unshared_exchange(ledger: Sequence[Dict[str, Any]], other: Sequence[Dict[str, Any]], *,
                            losing: bool, near_only: bool = False) -> Optional[Dict[str, Any]]:
    """The first square where the mover comes out at least a pawn behind (or
    ahead), unless the other branch has the same exchange on the same square."""
    for g in ledger:
        if near_only and not _near_enough(g):
            continue
        if (g["net_cp"] <= -EXCHANGE_MIN_CP if losing else g["net_cp"] >= EXCHANGE_MIN_CP) and not _same_exchange(g, other):
            return g
    return None


def _dearest(names: Sequence[str]) -> Optional[str]:
    by_name = {v: k for k, v in PIECE_NAME.items()}
    return max(names, key=lambda n: _VALUE[by_name[n]]) if names else None


_COUNT_WORDS = {2: "two", 3: "three", 4: "four", 5: "five"}


def _pieces_phrase(names: Sequence[str], *, article: bool = True) -> Optional[str]:
    """Every piece that changed hands on the square, dearest first: "a knight
    and a pawn", "two pawns", "a rook and two pawns". Without the article the
    phrase follows "your" / "their": "knight and pawn".

    Before 2026-11-06 a group named only its dearest piece, so an exchange
    that also cost a pawn on the same square read as if it had not."""
    names = [str(n) for n in names if n]
    if not names:
        return None
    by_name = {v: k for k, v in PIECE_NAME.items()}
    parts = []
    for name in sorted(set(names), key=lambda n: -_VALUE[by_name[n]]):
        k = names.count(name)
        if k == 1:
            parts.append(f"a {name}" if article else name)
        else:
            parts.append(f"{_COUNT_WORDS.get(k, str(k))} {name}s")
    if len(parts) == 1:
        return parts[0]
    return ", ".join(parts[:-1]) + " and " + parts[-1]


def material_words(cp: int) -> str:
    """A net swing in words a 1200 player uses. Never a number."""
    cp = abs(int(cp))
    if cp < 150:
        return "a pawn"
    if cp < 250:
        return "two pawns"
    if cp < 350:
        return "a piece"
    if cp < 450:
        return "a piece and a pawn"
    if cp < 650:
        return "a rook"
    return "a lot of material"


def exchange_sentence(g: Dict[str, Any], *, played_san: str, reply_san: Optional[str], alt_san: str,
                      received: bool, mover_is_user: bool, with_clause: bool = True) -> Dict[str, Any]:
    """One plain sentence for a ledger group, plus the facts the words model may use.

    `with_clause` adds "for nothing" / "nothing takes back" and is the caller's
    promise that the rest of the line does not give the material back."""
    # Object position ("costs them"), never the subject form: 0801f1a8 m7 and
    # m8 read "costs they a queen for a knight" on the opponent's cards.
    them = "you" if mover_is_user else "them"
    your = "your" if mover_is_user else "their"
    their = "their" if mover_is_user else "your"
    captures = [p["san"] for p in g["plies"]]
    if received:
        lost, gained = _dearest(g["mover_lost"]), _dearest(g["mover_won"])
        lost_all, gained_all = _pieces_phrase(g["mover_lost"], article=False), _pieces_phrase(g["mover_won"])
        hit = next(p for p in g["plies"] if not p["by_mover"])
        if gained is None:
            if hit["ply"] == 1:
                text = f"After {played_san}, {hit['san']} simply takes {your} {lost_all} on {g['square']}" + \
                       (", and nothing can take back." if with_clause else ".")
            else:
                text = (f"After {played_san}, {reply_san} starts a line that ends with {hit['san']} taking {your} "
                        f"{lost_all} on {g['square']}" + (" for free." if with_clause else "."))
        else:
            text = (f"After {played_san}, the exchange on {g['square']} costs {them} "
                    f"{_pieces_phrase(g['mover_lost'])} for {gained_all}.")
        return {"mechanism": "WINS_MATERIAL", "direction": "received", "agent_move": hit["san"], "square": g["square"],
                "victim_piece": lost, "victim_pieces": list(g["mover_lost"]), "victim_square": g["square"],
                "gained_piece": gained, "gained_pieces": list(g["mover_won"]), "payoff_cp": -g["net_cp"],
                "ply": hit["ply"], "captures": captures, "text": text}
    won, lost = _dearest(g["mover_won"]), _dearest(g["mover_lost"])
    won_all = _pieces_phrase(g["mover_won"], article=False)
    hit = next(p for p in g["plies"] if p["by_mover"])
    if lost is None:
        if hit["ply"] == 0:
            text = f"{alt_san} simply takes {their} {won_all} on {g['square']}" + (" for free." if with_clause else ".")
        else:
            text = f"{alt_san} was the move: it leads to {hit['san']}, picking up {their} {won_all} on {g['square']}" + \
                   (" for free." if with_clause else ".")
    else:
        text = (f"{alt_san} was the move: the exchange on {g['square']} wins {their} {won_all} "
                f"for {_pieces_phrase(g['mover_lost'])}.")
    return {"mechanism": "WINS_MATERIAL", "direction": "missed", "agent_move": hit["san"], "square": g["square"],
            "victim_piece": won, "victim_pieces": list(g["mover_won"]), "victim_square": g["square"],
            "gained_piece": lost, "gained_pieces": list(g["mover_lost"]), "payoff_cp": g["net_cp"],
            "ply": hit["ply"], "captures": captures, "text": text}


def material_claim(ledger_played: Sequence[Dict[str, Any]], ledger_alt: Sequence[Dict[str, Any]], *,
                   played_plies: int, alt_plies: int, received: bool, gap: Optional[int], move_class: str,
                   played_san: str, reply_san: Optional[str], alt_san: str, mover_is_user: bool) -> Optional[Dict[str, Any]]:
    """What the material says, if it says anything the reader can rely on.

    Rules, each from a position in the regression set:
      - only on a mistake or worse: a pawn claim on an inaccuracy contradicts the eval (ho20, ho18)
      - a group open at the horizon is unknown (ho05, ho02)
      - the two lines must differ by at least a pawn in the mover's favour of the better move (ho05)
      - a group is the story when the line's net confirms it or the eval gap is at least its size
        (codex_bxd5: the g5 knight falls, the line regains a knight elsewhere, the eval says a piece)
      - "for nothing" needs the line's net to confirm nothing came back (ho08: the rook on c2 is
        answered by the queen on a4; dev_na4: the queen on d4 by the queen on d1)
      - otherwise the plain net of the exchanges, in words (ho08: a pawn up)
    """
    if move_class not in ("mistake", "blunder"):
        return None
    mine_all = ledger_played if received else ledger_alt
    other_all = ledger_alt if received else ledger_played
    mine = closed_groups(mine_all, played_plies if received else alt_plies)
    other = closed_groups(other_all, alt_plies if received else played_plies)
    uncertain = len(mine) != len(mine_all) or len(other) != len(other_all)
    total_mine = sum(g["net_cp"] for g in mine)
    total_other = sum(g["net_cp"] for g in other)
    better_by = (total_other - total_mine) if received else (total_mine - total_other)   # the better move's edge
    g = first_unshared_exchange(mine, other, losing=received, near_only=True)
    if g is not None:
        same_sign = (total_mine < 0) if received else (total_mine > 0)
        confirmed = same_sign and abs(total_mine) >= abs(g["net_cp"]) - EXCHANGE_MIN_CP
        eval_supported = gap is not None and gap >= abs(g["net_cp"])
        # Either the two lines differ by a pawn in the better move's favour, or
        # the eval gap is at least the size of this event (ho23: both lines
        # drop a pawn, and the exchange on a7 is still what the gap is about).
        if better_by < EXCHANGE_MIN_CP and not eval_supported:
            g = None
    if g is not None:
        if confirmed or eval_supported:
            unanswered = not (g["mover_won"] if received else g["mover_lost"])
            claim = exchange_sentence(g, played_san=played_san, reply_san=reply_san, alt_san=alt_san,
                                      received=received, mover_is_user=mover_is_user,
                                      with_clause=unanswered and confirmed)
            claim["net_cp_line"] = total_mine
            return claim
    # The exchanges give it back somewhere else: say the net, not the piece.
    # Not when a capture at the horizon leaves the net itself in doubt, and
    # only when this line itself ends ahead (missed) or behind (received): a
    # line that merely loses less than the other is not "a pawn up".
    if better_by < EXCHANGE_MIN_CP or uncertain or (total_mine >= 0 if received else total_mine <= 0):
        return None
    you = "you" if mover_is_user else "they"        # subject: "they come out"
    them = "you" if mover_is_user else "them"       # object: "leave them"
    # The sentence describes where THIS line ends ("a pawn up"), so it words
    # the line's own net. The gate above is on the edge between the lines;
    # until 2026-11-06 the edge was worded too, and a line that nets one pawn
    # while the other loses one read "two pawns up".
    amount = material_words(total_mine)
    if received:
        text = f"After {played_san}, the exchanges that follow {reply_san} leave {them} {amount} down."
        agent = reply_san
    else:
        text = f"{alt_san} was the move: after the exchanges {you} come out {amount} up."
        agent = alt_san
    captures = [p["san"] for grp in mine for p in grp["plies"]]
    return {"mechanism": "WINS_MATERIAL", "direction": "received" if received else "missed", "agent_move": agent,
            "square": None, "victim_piece": None, "victim_square": None, "gained_piece": None,
            "payoff_cp": better_by, "ply": None, "captures": captures, "net_cp_line": total_mine, "series": True, "text": text}


# ------------------------------------------------------------------ probe --

def _branch(session, root: chess.Board, move: chess.Move, *, depth: int) -> Dict[str, Any]:
    """Locate the reply on one branch and read its line and drop."""
    board = root.copy()
    board.push(move)
    probe = probe_reply_dependency(board, session, depth=depth)
    out: Dict[str, Any] = {"move_san": root.san(move), "move_uci": move.uci(), "status": probe["status"],
                           "signal": probe["signal"], "reply_san": probe.get("excluded_san"),
                           "reply_uci": probe.get("excluded_uci"), "drop_cp": None, "line_san": [],
                           "replacement_san": None}
    measurements = probe.get("measurements") or []
    if measurements:
        last = measurements[-1]
        out["drop_cp"] = last.get("drop_cp")
        record = _record_by_id(session, last.get("baseline_search_id"))
        if record is not None and record.lines:
            out["line_san"] = list(record.lines[0]["moves_san"])
            out["score"] = record.lines[0]["score"]
        if last.get("replacement_uci"):
            try:
                out["replacement_san"] = board.san(chess.Move.from_uci(last["replacement_uci"]))
            except (ValueError, AssertionError):
                out["replacement_san"] = None
    return out


def _root(session, root: chess.Board, played: chess.Move, *, depth: int,
          alternative: Optional[chess.Move] = None) -> Dict[str, Any]:
    """Root MultiPV, plus a restricted search for any move the lines did not rank.

    When the caller names the alternative (the card's stored best move), the gap
    is measured against THAT move, so the sentence and the card agree on what
    the better move was. The search's own best is kept for the record.
    """
    width = max(2, session.config.rank_width)
    record = session.query(root, "differential_root", width=width, depth=depth)
    lines = list(record.lines) if record.status == "complete_iteration" else []
    out: Dict[str, Any] = {"status": record.status, "lines": lines, "best_uci": None, "best_san": None,
                           "pv_best_san": [], "score_best": None, "score_played": None,
                           "alternative_uci": None, "score_alternative": None, "pv_alternative_san": []}
    if not lines:
        return out
    best = lines[0]
    out.update(best_uci=best["root_uci"], best_san=best["moves_san"][0], pv_best_san=list(best["moves_san"]),
               score_best=best["score"])

    def line_for(move: chess.Move, purpose: str):
        hit = next((l for l in lines if l["root_uci"] == move.uci()), None)
        if hit is None:
            restricted = session.query(root, purpose, roots=[move], depth=depth)
            if restricted.status == "complete_iteration" and restricted.lines:
                hit = restricted.lines[0]
        return hit

    mine = line_for(played, "differential_played")
    if mine is not None:
        out["score_played"] = mine["score"]
        out["pv_played_san"] = list(mine["moves_san"])
    chosen = alternative if alternative is not None else chess.Move.from_uci(best["root_uci"])
    theirs = line_for(chosen, "differential_alternative")
    if theirs is not None:
        out.update(alternative_uci=chosen.uci(), score_alternative=theirs["score"],
                   pv_alternative_san=list(theirs["moves_san"]))
    return out


def alternative_double_attack(root: chess.Board, played: chess.Move, alternative: chess.Move,
                              *, mover_is_user: bool) -> Optional[Dict[str, Any]]:
    """The better move hits two things at once and the played move does not.

    Read off the board the way the reply footprint is: direct attacks on pieces
    that are undefended or worth more than the attacker, lines it uncovers onto
    such pieces, and check. Two or more is a double attack. The caller only
    asks when the engine already graded the move a mistake or worse, so the
    "cannot save both" is the engine's finding; this names what it is about.
    dev_na4: Nd5 attacks the loose bishop on e7 and uncovers b2 onto the queen
    on d4, while Black's desperado hides the gain from a six-ply material walk.
    """
    value = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 100}

    by_name = {v: k for k, v in PIECE_NAME.items()}

    def targets(move: chess.Move) -> List[Tuple[str, str, Optional[str], Optional[str]]]:
        """(piece, square, via piece, via square), most valuable first."""
        mover_piece = root.piece_at(move.from_square)
        after = root.copy()
        after.push(move)
        out: List[Tuple[str, str, Optional[str], Optional[str]]] = []
        for key, d in reply_footprint(root, move, None).items():
            if d["kind"] == "attacks":
                worth_more = value[by_name[d["piece"]]] > value[mover_piece.piece_type] if mover_piece else False
                if not d["defenders"] or worth_more:
                    out.append((d["piece"], d["square"], None, None))
            elif d["kind"] == "uncovers_attack":
                sq = chess.parse_square(d["square"])
                slider = after.piece_at(chess.parse_square(d["slider_square"]))
                target = after.piece_at(sq)
                if target is None or slider is None:
                    continue
                defended = bool(after.attackers(target.color, sq))
                if d["check"] or not defended or value[target.piece_type] > value[slider.piece_type]:
                    out.append(("king" if d["check"] else d["piece"], d["square"],
                                PIECE_NAME[slider.piece_type], d["slider_square"]))
            elif d["kind"] == "check":
                out.append(("king", "", None, None))
        seen, uniq = set(), []
        for t in sorted(out, key=lambda t: -value[by_name[t[0]]]):
            if (t[0], t[1]) not in seen:
                seen.add((t[0], t[1]))
                uniq.append(t)
        return uniq

    hits = targets(alternative)
    if len(hits) < 2:
        return None
    if len(targets(played)) >= 2:
        return None                       # the played move hit two things as well; not the difference
    owner = _owner(False, mover_is_user)
    alt_san = root.san(alternative)

    def name(t):
        piece, square, via_piece, via_square = t
        base = f"{owner} {piece}" + (f" on {square}" if square else "")
        return base + (f" through the {via_piece} on {via_square}" if via_square else "")

    first, second = hits[0], hits[1]
    cannot = "They" if owner == "their" else "You"
    text = (f"{alt_san} was the move: it hits {name(first)} and {name(second)} at the same time. "
            f"{cannot} cannot save both.")
    return {"mechanism": "FORK", "direction": "missed", "agent_move": alt_san, "targets": hits,
            "victim_piece": first[0], "victim_square": first[1] or None, "payoff_cp": None, "line": [],
            "retreat_san": None, "returns_home": False, "text": text}


# ---------------------------------------------------------------- explain --

def explain_move(fen_before: str, played_san: str, *, config: ReasoningConfig, depth: int,
                 mover_is_user: bool = True, rating: Optional[int] = None,
                 alternative_san: Optional[str] = None, measure_alternative: bool = True,
                 session_factory=None, keep_searches: bool = False) -> Dict[str, Any]:
    """Why this move was worse than the better one, from the engine and the board.

    Returns a dict with `found`; when False, `reason` says why and
    `better_move` still names the engine's choice so the caller can show
    something true. Never raises for an engine result it did not like; raises
    ValueError only for an illegal input.
    """
    if isinstance(depth, bool) or not isinstance(depth, int) or depth < 1:
        raise ValueError("depth must be a positive integer")
    started = time.perf_counter()
    root = chess.Board(fen_before)
    played = parse_legal_move(root, played_san)
    if played is None:
        raise ValueError("played move is not legal in the position")
    played_san = root.san(played)
    session = (session_factory or SearchSession)(config, root.turn, fingerprint([root.fen(), []]))

    result: Dict[str, Any] = {"schema_version": SCHEMA_VERSION, "found": False, "reason": None,
                              "input": {"fen": root.fen(), "played_san": played_san, "played_uci": played.uci(),
                                        "mover_is_user": mover_is_user, "rating": rating},
                              "family": "unmeasured", "class": "unknown", "gap_cp": None,
                              "better_move": None, "played_branch": None, "alternative_branch": None,
                              "causes": [], "consequence": None, "shared_consequence": None,
                              "text": None, "facts": None, "line_san": [], "arrows": [],
                              "direction": None, "mechanism": None}

    # The card's stored best move, when given, is the alternative we measure
    # against; an unparseable one is ignored rather than fatal.
    named = parse_legal_move(root, alternative_san) if alternative_san else None
    if named is not None and named == played:
        named = None
    head = _root(session, root, played, depth=depth, alternative=named)
    result["root"] = {k: v for k, v in head.items() if k != "lines"}
    if not head["lines"]:
        result["reason"] = "root_search_unavailable"
        return _finish(result, session, started, keep_searches)

    alternative = chess.Move.from_uci(head["alternative_uci"]) if head["alternative_uci"] else chess.Move.from_uci(head["best_uci"])
    alt_cp = score_cp(head["score_alternative"] if head["alternative_uci"] else head["score_best"])
    played_cp = score_cp(head["score_played"])
    gap = (alt_cp - played_cp) if (alt_cp is not None and played_cp is not None) else None
    result["gap_cp"] = gap
    result["class"] = classify_gap(gap, rating)

    if alternative == played or (head["best_uci"] == played.uci() and named is None):
        result["family"] = "good"
        result["reason"] = "engine_choice"
        return _finish(result, session, started, keep_searches)
    alt_san = root.san(alternative)
    result["better_move"] = alt_san
    if result["class"] == "good":
        result["family"] = "good"
        result["reason"] = "no_gap"
        return _finish(result, session, started, keep_searches)

    played_branch = _branch(session, root, played, depth=depth)
    result["played_branch"] = played_branch
    alt_branch = None
    if measure_alternative:
        alt_branch = _branch(session, root, alternative, depth=depth)
        result["alternative_branch"] = alt_branch

    drop = played_branch.get("drop_cp")
    if played_branch["status"] == "terminal":
        result["family"] = "terminal"
    elif drop is not None and gap:
        ratio = drop / gap
        result["drop_over_gap"] = round(ratio, 2)
        result["family"] = ("punished" if ratio >= PUNISHED_MIN_RATIO else
                            "missed" if ratio < MISSED_MAX_RATIO else "mixed")

    # Lines, with the played / better move in front, as the resolver expects.
    pv_played_rest = list(played_branch.get("line_san") or [])
    if not pv_played_rest and head.get("pv_played_san"):
        pv_played_rest = list(head["pv_played_san"][1:])
    pv_alt_rest = list((alt_branch or {}).get("line_san") or []) or list(
        (head.get("pv_alternative_san") or head["pv_best_san"])[1:])

    from services.punishment_resolver import _line_material_gain, resolve_missed, resolve_received
    from services.why_on_demand import _arrows, _explains_the_loss, _phrase

    reply_uci = played_branch.get("reply_uci")
    reply_san = played_branch.get("reply_san")

    # MATERIAL is read from both engine lines with one ledger, square by
    # square, so a recapture is an exchange and an exchange the better move
    # also allows is not the difference. The resolver still names the
    # non-material mechanisms (mate, fork, trapped, promotion, forced retreat).
    played_line = [played_san] + pv_played_rest
    alt_line = [alt_san] + pv_alt_rest
    ledger_played = exchange_ledger(root, played_line, root.turn)
    ledger_alt = exchange_ledger(root, alt_line, root.turn)
    result["ledger"] = {"played": ledger_played, "better": ledger_alt}
    claim_kwargs = dict(played_plies=min(len(played_line), LEDGER_PLIES), alt_plies=min(len(alt_line), LEDGER_PLIES),
                        gap=gap, move_class=result["class"],
                        played_san=played_san, reply_san=reply_san, alt_san=alt_san, mover_is_user=mover_is_user)
    loss = material_claim(ledger_played, ledger_alt, received=True, **claim_kwargs)
    gain = material_claim(ledger_played, ledger_alt, received=False, **claim_kwargs)

    received = resolve_received(fen_before, played_san, pv_played_rest) if pv_played_rest else None
    received_alt = resolve_received(fen_before, alt_san, pv_alt_rest) if pv_alt_rest else None
    if received is not None and received.mechanism == "WINS_MATERIAL":
        received = None                   # the ledger speaks for material
    shared = (received is not None and received_alt is not None
              and received.mechanism == received_alt.mechanism
              and received.agent_move == received_alt.agent_move
              and (received.victim_piece or "") == (received_alt.victim_piece or ""))
    # The same chasing reply on both branches is the same chase, whatever the
    # resolver ranks first on the other branch (ho07: h6 after Nc3 and after d3).
    if (received is not None and not shared and received.mechanism in ("FORCES_RETREAT", "TRAPPED")
            and pv_alt_rest and pv_alt_rest[0] == received.agent_move):
        shared = True
        received_alt = received_alt or received
    if shared:
        result["shared_consequence"] = {"mechanism": received.mechanism, "after_played": received.agent_move,
                                        "after_better": received_alt.agent_move,
                                        "note": "the better move allows the same thing; not the difference"}
        received = None
    shared_material = [g for g in closed_groups(ledger_played, min(len(played_line), LEDGER_PLIES))
                       if g["net_cp"] <= -EXCHANGE_MIN_CP and _near_enough(g) and _same_exchange(g, ledger_alt)]
    if shared_material and loss is None and result.get("shared_consequence") is None:
        g = shared_material[0]
        result["shared_consequence"] = {"mechanism": "WINS_MATERIAL", "square": g["square"], "net_cp": g["net_cp"],
                                        "note": "the better move allows the same exchange; not the difference"}

    causes: List[Dict[str, Any]] = []
    if reply_uci:
        causes = differential_causes(root, played, alternative, reply_uci, mover_is_user=mover_is_user)
        # An attack by a piece that is taken on the very next move of the line
        # is not a reason: the piece does not live to make it (ho18).
        if len(pv_played_rest) >= 2:
            after_reply = root.copy(); after_reply.push(played)
            reply_move = chess.Move.from_uci(reply_uci); after_reply.push(reply_move)
            nxt = parse_legal_move(after_reply, pv_played_rest[1])
            if nxt is not None and nxt.to_square == reply_move.to_square:
                causes = [c for c in causes if c["kind"] not in ("attacks", "uncovers_attack")]
    result["causes"] = causes

    missed = resolve_missed(fen_before, alt_san, pv_alt_rest) if pv_alt_rest else None
    if missed is not None and missed.mechanism == "WINS_MATERIAL":
        missed = None                     # the ledger speaks for material
    if missed is not None and not _explains_the_loss(missed, gap):
        missed = None
    # In the punished family the gap sits on the played branch; a small gain
    # on the better move's line is not the reason (dev_qf8: a pawn in a lost
    # position while the played move drops a bishop).
    if gain is not None and result["family"] == "punished" and gap and gain["payoff_cp"] < 0.5 * gap:
        gain = None
    double = None
    if missed is None and result["class"] in ("mistake", "blunder"):
        double = alternative_double_attack(root, played, alternative, mover_is_user=mover_is_user)

    def punished_answer() -> bool:
        material = loss
        other = received if (received is not None and _explains_the_loss(received, gap)) else None
        if not causes and material is None and other is None:
            return False
        sentences = [c["text"] for c in causes[:1]]
        lead = causes[0] if causes else None
        consequence: Optional[Dict[str, Any]] = None
        if material is not None:
            # The cause already named this square: "c5 hits your pawn on d4"
            # needs no "the exchange on d4 costs you a pawn" after it.
            if not (lead is not None and material.get("square") and lead.get("square") == material["square"]):
                sentences.append(material["text"] if not causes else _without_prefix(material["text"], played_san))
            consequence = material
        elif other is not None:
            phrase = _phrase(other, played_san, mover_is_user)
            if phrase:
                sentences.append(phrase if not causes else _without_prefix(phrase, played_san))
            consequence = other.as_dict()
        result.update(found=True, direction="received",
                      mechanism=(consequence["mechanism"] if consequence else causes[0]["kind"].upper()),
                      text=" ".join(s for s in sentences if s), consequence=consequence)
        line = [played_san] + pv_played_rest[:3]
        result["line_san"] = line
        result["arrows"] = _arrows(fen_before, line, limit=2)
        return True

    def missed_answer() -> bool:
        if missed is not None:
            phrase = _phrase(missed, played_san, mover_is_user)
            if phrase:
                result.update(found=True, direction="missed", mechanism=missed.mechanism, text=phrase,
                              consequence=missed.as_dict())
                line = [alt_san] + list(missed.line)
                result["line_san"] = line
                result["arrows"] = _arrows(fen_before, line, limit=3)
                return True
        # A double attack is the cause; the ledger is its consequence. Cause
        # first (dev_na4: the fork, not the desperado queen trade it forces).
        if double is not None:
            result.update(found=True, direction="missed", mechanism="FORK", text=double["text"],
                          consequence={k: v for k, v in double.items() if k not in ("text", "targets")},
                          double_attack=double["targets"])
            result["line_san"] = [alt_san]
            result["arrows"] = _arrows(fen_before, [alt_san], limit=1)
            return True
        if gain is not None:
            result.update(found=True, direction="missed", mechanism="WINS_MATERIAL", text=gain["text"],
                          consequence=gain)
            line = [alt_san] + pv_alt_rest[:max(1, gain["ply"] or 1)]
            result["line_san"] = line
            result["arrows"] = _arrows(fen_before, line, limit=min(3, len(line)))
            return True
        return False

    # CHECK FIRST runs before the material answers. When both moves take the
    # same piece on the same square, "the better move wins that piece" is not
    # the difference: 3628ebef m32, Rxe7 against Re6+, answered "Re6+ was the
    # move: it leads to Rxe7, picking up their knight on e7 for free" about a
    # knight the played move takes too. The difference is the king, which
    # takes back after Rxe7 and has stepped away after the check. The
    # measurement is kept whether or not it fires.
    from .check_first import check_first_claim
    check_first = check_first_claim(root, played_line, alt_line, mover_is_user=mover_is_user)
    result["check_first"] = {k: v for k, v in check_first.items() if k not in ("text", "facts", "consequence")}
    if check_first["fires"] and result["class"] not in ("mistake", "blunder"):
        result["check_first"].update(fires=False, why_not="class")
    if result["check_first"]["fires"]:
        result.update(found=True, direction="missed", mechanism="CHECK_FIRST", text=check_first["text"],
                      consequence=check_first["consequence"], check_first_facts=check_first["facts"])
        line = [alt_san] + pv_alt_rest[:check_first["capture_ply"]]
        result["line_san"] = line
        result["arrows"] = _arrows(fen_before, line, limit=min(3, len(line)))
    else:
        # A capture the played move makes too is not what the better move
        # "picks up": the missed-material sentence would name a piece both
        # moves take (the same defect, where the family above stayed silent).
        taken = root.piece_at(played.to_square)
        if (gain is not None and not gain.get("series") and taken is not None and taken.color != root.turn
                and gain.get("square") == chess.square_name(played.to_square)
                and PIECE_NAME[taken.piece_type] in (gain.get("victim_pieces") or [gain.get("victim_piece")])):
            result["shared_capture"] = {"square": gain["square"], "piece": PIECE_NAME[taken.piece_type],
                                        "note": "the played move takes the same piece; not the difference"}
            gain = None
        order = (punished_answer, missed_answer) if result["family"] in ("punished", "mixed", "unmeasured", "terminal") \
            else (missed_answer, punished_answer)
        for attempt in order:
            if attempt():
                break

    # TEMPO runs last: when nothing material separates the lines and the move
    # is an inaccuracy or a mistake, the difference may be that the better
    # move brings a piece out and the played move does not (Mohit's 4...b6,
    # 2026-11-02). The measurement is kept whether or not it fires, so a run
    # over many positions gives the fire-rate distribution.
    if not result["found"] and result["class"] in ("inaccuracy", "mistake"):
        from .tempo import tempo_claim
        tempo = tempo_claim(root, played, alternative, played_line=played_line, alt_line=alt_line,
                            move_class=result["class"], mover_is_user=mover_is_user, ledger_played=ledger_played)
        result["tempo"] = {k: v for k, v in tempo.items() if k not in ("text", "facts")}
        if tempo["fires"]:
            result.update(found=True, direction="missed", mechanism="TEMPO", text=tempo["text"],
                          consequence=tempo["consequence"], tempo_facts=tempo["facts"])
            result["line_san"] = [alt_san]
            result["arrows"] = _arrows(fen_before, [alt_san], limit=1)

    if not result["found"]:
        result["reason"] = "shared_consequence_only" if result.get("shared_consequence") else "no_mechanism"
    result["facts"] = build_facts(result)
    return _finish(result, session, started, keep_searches)


def _without_prefix(phrase: str, played_san: str) -> str:
    """'After Nd4, Nxe5 wins your pawn.' -> 'Nxe5 wins your pawn.' when a cause already set the scene.

    A move is never re-capitalised: a pawn move's SAN starts lowercase and
    "C5 wins" is not a move. A plain word is (ho10, run 7: "the exchanges that
    follow exd5 leave you a pawn down." began a sentence in lowercase)."""
    prefix = f"After {played_san}, "
    if not phrase.startswith(prefix):
        return phrase
    rest = phrase[len(prefix):]
    first = rest.split(" ", 1)[0]
    from services.llm_caption import _SAN
    if first and first[0].islower() and not _SAN.fullmatch(first.rstrip(".,")):
        rest = first[0].upper() + rest[1:]
    return rest


def _finish(result: Dict[str, Any], session, started: float, keep_searches: bool) -> Dict[str, Any]:
    result["runtime"] = {"wall_ms": round(1000 * (time.perf_counter() - started), 1),
                         "query_count": getattr(session, "executed_queries", None),
                         "requested_nodes": getattr(session, "requested_nodes", None)}
    if keep_searches:
        result["searches"] = [r.document() for r in session.records]
        result["reproducibility"] = session.document() if hasattr(session, "document") else None
    return result


# ------------------------------------------------------------------ facts --

# What each cause is CLAIMING, in words the engine owns, is defined ONCE in
# services/why_words.py (_RELATION), next to the resolver's mechanisms and the
# regexes that check the model kept the claim. A copy here would drift and the
# check would silently stop applying.
CAUSE_KINDS = ("CHECK", "LOST_GUARD", "HANGING", "ATTACKS", "UNCOVERS_ATTACK")


def cause_relation(kind: str) -> str:
    from services.why_words import _RELATION
    key = kind.upper()
    if key not in CAUSE_KINDS or key not in _RELATION:
        raise KeyError(f"no relation text for cause {kind}")
    return _RELATION[key]


def build_facts(result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """The finding as facts a model can read and nothing more. No evaluations."""
    if not result.get("found"):
        return None
    mover_is_user = bool(result["input"]["mover_is_user"])
    facts: Dict[str, Any] = {
        "whose_move": "the reader's" if mover_is_user else "their opponent's",
        "the_move_played": result["input"]["played_san"],
        "the_better_move": result.get("better_move"),
    }
    if result.get("mechanism") == "TEMPO":
        # The tempo family's facts are all board facts about development; none
        # of the material keys below apply. The line is withheld here too.
        facts["this_happens_after_the_move_played"] = False
        facts["the_move_that_does_it"] = result.get("better_move")
        facts.update(result.get("tempo_facts") or {})
        return facts
    if result.get("mechanism") == "CHECK_FIRST":
        # Board facts read off both lines by the family module: the square,
        # the king's recapture, the king's step, the capture after it.
        facts["this_happens_after_the_move_played"] = False
        facts["the_move_that_does_it"] = result.get("better_move")
        facts.update(result.get("check_first_facts") or {})
        return facts
    consequence = result.get("consequence")
    causes = result.get("causes") or []
    if result["direction"] == "received":
        facts["their_reply"] = (result.get("played_branch") or {}).get("reply_san")
        facts["this_happens_after_the_move_played"] = True
        if causes:
            lead = causes[0]
            facts["what_the_move_played_changed"] = lead["text"]
            facts["relation"] = cause_relation(lead["kind"])
            if lead.get("piece"):
                from services.why_words import _owned
                facts["the_piece_involved"] = _owned(lead["owner"], lead["piece"])
            if lead.get("square"):
                facts["the_square_it_is_on"] = lead["square"]
            if lead.get("guard_square"):
                facts["the_guard_that_was_lost"] = f"the {lead['guard_piece']} on {lead['guard_square']}"
        facts["the_move_that_does_it"] = facts["their_reply"]
    else:
        facts["this_happens_after_the_move_played"] = False
        facts["the_move_that_does_it"] = result.get("better_move")
    if consequence is not None:
        from services.punishment_resolver import victim_owner
        from services.why_words import _RELATION, _owned
        whose = victim_owner(consequence["direction"], mover_is_user)
        if "relation" not in facts:
            facts["relation"] = _RELATION.get(consequence["mechanism"], "")
        else:
            facts["and_then"] = _RELATION.get(consequence["mechanism"], "")
        named = consequence.get("victim_piece")
        if consequence["mechanism"] == "MATE" and not named:
            named = "king"
        if named or consequence["mechanism"] in ("TRAPPED", "FORCES_RETREAT", "WINS_MATERIAL"):
            facts.setdefault("the_piece_involved", _owned(whose, named))
        if consequence.get("victim_square"):
            facts.setdefault("the_square_it_is_on", consequence["victim_square"])
        if consequence.get("retreat_san"):
            facts["the_only_square_it_can_go_to"] = consequence["retreat_san"]
        if consequence.get("text"):
            # A ledger consequence: the capture that does it and what, if
            # anything, was had in return. Both are engine-line facts.
            facts["what_happens_to_the_material"] = consequence["text"]
            if consequence.get("gained_piece"):
                facts["what_was_had_in_return"] = f"a {consequence['gained_piece']}"
            if consequence.get("captures"):
                facts["the_captures_in_the_line"] = list(consequence["captures"])
            if consequence["direction"] == "received" and consequence.get("agent_move") != facts.get("their_reply"):
                facts["the_capture_that_does_it"] = consequence["agent_move"]
    return facts
