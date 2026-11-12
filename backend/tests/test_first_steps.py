"""First steps: every authored answer agrees with the rules, and every wrong
tap gets the right mistake kind. docs/first_steps_scope.md."""
import random

import chess
import pytest

from services import first_steps as fs


def _all_items():
    content = fs.load_content()
    for item in content["placement"]["items"]:
        yield "placement", item
    for cls in content["classes"]:
        for item in cls["items"]:
            yield cls["id"], item


ALL = list(_all_items())


@pytest.mark.parametrize("cls_id,item", ALL, ids=[i["id"] for _, i in ALL])
def test_authored_answers_match_the_rules(cls_id, item):
    if "expect" in item:
        assert fs.answers(item) == set(item["expect"]), item["id"]
    if item["kind"] == "stars":
        par = fs.stars_par(item)
        assert par is not None, f"{item['id']}: a star cannot be reached"
        if "expect_par" in item:
            assert par == item["expect_par"]
        for s in item["stars"]:
            assert s not in item.get("walls", []) and s != item["start"]
    if item["kind"] in fs.TAP_KINDS | {"move_goal", "choose"}:
        assert fs.answers(item), f"{item['id']} has no answer"


def test_every_class_is_complete():
    ids = set()
    for cls in fs.classes():
        items = {i["id"]: i for i in cls["items"]}
        assert not (ids & set(items)), "item ids must be unique"
        ids |= set(items)
        assert any(i.get("test") for i in cls["items"]), f"{cls['id']} has no check item"
        assert any(i["kind"] in ("stars", "game") or i["part"] == "Play it" for i in cls["items"])
        if cls.get("recall"):
            assert items[cls["recall"]].get("recall_only")
        for target in (cls.get("warm_up_by_kind") or {}).values():
            assert target in items, f"{cls['id']}: warm-up {target} missing"
        for i in cls["items"]:
            assert i.get("say") and i.get("sub"), i["id"]
        # Every mistake a warm-up is keyed on must be one the grader can produce.
        for kind in (cls.get("warm_up_by_kind") or {}):
            assert kind in fs.MISTAKE_WORDS, f"{cls['id']}: unknown mistake kind {kind}"
    assert [c["order"] for c in fs.classes()] == list(range(1, 14))


# ---------------------------------------------------------------------------
# thinking habits (classes 9-13): checks, captures, threats, loose pieces, openings
# ---------------------------------------------------------------------------
def test_the_thinking_habit_classes_follow_checkmate():
    ids = [c["id"] for c in fs.classes()]
    assert ids[8:] == ["captures", "threats", "loose_pieces", "before_you_move", "opening_basics"]
    # A child who finished checkmate is sent on to captures, not left with nothing.
    assert fs.next_class(2, ["checkmate"])["id"] == "captures"


def test_move_items_are_white_to_move():
    # The class page only lets the child pick up white pieces.
    for cls in fs.classes():
        for i in cls["items"]:
            if i["kind"] in ("move_goal", "game"):
                assert chess.Board(i["fen"]).turn == chess.WHITE, i["id"]


@pytest.mark.parametrize("item_id,square,kind", [
    ("cap-tap", "a1", "own_piece_take"),
    ("cap-tap", "e8", "cant_take"),
    ("cap-free", "b5", "defended_target"),
    ("cap-free", "a6", "cant_take"),
    ("thr-tap", "a2", "not_attacked"),
    ("loose-tap-black", "d5", "defended"),
    ("loose-tap-white", "f3", "defended"),
    ("cct-tap-checks", "b2", "no_check_from"),
])
def test_wrong_habit_taps(item_id, square, kind):
    r = fs.grade(_item(item_id), {"square": square})
    assert r["outcome"] == "wrong" and r["kind"] == kind
    assert r["say"] == fs.MISTAKE_WORDS[kind]


@pytest.mark.parametrize("item_id,square", [
    ("thr-tap", "b4"),          # an enemy piece is not "one of yours"
    ("loose-tap-black", "e8"),  # kings are never loose pieces
    ("loose-tap-black", "e1"),  # wrong colour
    ("cap-tap", "d4"),          # empty square
])
def test_habit_taps_that_are_not_attempts_are_ignored(item_id, square):
    assert fs.grade(_item(item_id), {"square": square})["outcome"] == "ignored"


def test_habit_taps_need_every_answer():
    item = _item("cap-tap")
    state = {}
    for square in ("a7", "b5"):
        r = fs.grade(item, {"square": square}, state)
        assert r["outcome"] == "progress"
        state = r["state"]
    r = fs.grade(item, {"square": "e4"}, state)
    assert r["outcome"] == "right" and r["total"] == 3


@pytest.mark.parametrize("item_id,move,kind", [
    ("cap-play", "d1d5", "not_free"),       # the knight is protected by e6
    ("cap-play", "d1d2", "not_capture"),
    ("thr-save", "g1g2", "still_hanging"),  # the knight is still attacked
    ("thr-defend", "e1e2", "not_defended"),
    ("open-castle", "e1f1", "not_castle"),
    ("open-develop", "b1a3", "not_develop"),  # the rim is not the middle
    ("open-centre", "a2a4", "not_centre"),
    ("open-line-1", "b1c3", "not_line"),
])
def test_wrong_habit_moves(item_id, move, kind):
    r = fs.grade(_item(item_id), {"move": move})
    assert r["outcome"] == "wrong" and r["kind"] == kind


def test_a_pawn_given_away_is_hanging():
    # "Safe" includes pawns: a pawn attacked and unprotected is hanging.
    board = chess.Board("4k3/8/8/3p4/4P3/8/8/4K3 w - - 0 1")
    assert fs.is_hanging(board, chess.E4) and fs.is_hanging(board, chess.D5)


def test_a_protected_piece_attacked_by_a_cheaper_one_is_hanging():
    # Rook on d4 protected by the king, attacked by a pawn: still lost.
    board = chess.Board("4k3/8/8/4p3/3R4/4K3/8/8 w - - 0 1")
    assert fs.is_defended(board, chess.D4)
    assert fs.is_hanging(board, chess.D4)
    # The same rook attacked only by a queen is not hanging.
    board = chess.Board("4k3/8/8/8/3R3q/4K3/8/8 w - - 0 1")
    assert not fs.is_hanging(board, chess.D4)


def test_a_free_capture_cannot_be_taken_back():
    board = chess.Board("6k1/8/4p3/3n4/b7/8/8/3Q2K1 w - - 0 1")
    assert fs._is_free_capture(board, chess.Move.from_uci("d1a4"))
    assert not fs._is_free_capture(board, chess.Move.from_uci("d1d5"))


def test_coach_notes_cover_the_new_mistakes():
    notes = fs.coach_notes({"still_hanging": 3, "not_free": 2})
    assert notes == ["leaves pieces where they can be taken for free",
                     "takes protected pieces instead of free ones"]


def test_new_habit_items_hide_their_answers_and_carry_a_tally():
    shown = fs.public_item(_item("cap-tap"))
    assert shown["total"] == 3 and shown["found"] == []
    assert "expect" not in shown and "right" not in shown and "color" not in shown


def _item(item_id):
    return next(i for _, i in ALL if i["id"] == item_id)


@pytest.mark.parametrize("item_id,square,kind", [
    ("rook-lines", "e5", "like_bishop"),
    ("rook-lines", "e6", "like_knight"),
    ("rook-blocked", "a7", "jumped"),
    ("rook-blocked", "a5", "own_piece"),
    ("bishop-lines", "d6", "like_rook"),
    ("knight-jumps", "d6", "like_rook"),
    ("knight-jumps", "e5", "like_bishop"),
    ("pawn-take", "e5", "pawn_blocked"),
    ("pawn-forward", "d3", "pawn_diag_empty"),
    ("pawn-later", "e6", "pawn_two"),
    ("pawn-later", "e3", "pawn_backward"),
    ("king-danger", "e2", "into_check"),
    ("king-steps", "e6", "too_far"),
])
def test_wrong_reach_taps_get_the_right_kind(item_id, square, kind):
    out = fs.grade(_item(item_id), {"square": square})
    assert out["outcome"] == "wrong" and out["kind"] == kind, out


@pytest.mark.parametrize("item_id,square,kind", [
    ("rook-take", "d8", "jumped"),
    ("rook-take", "a4", "not_on_line"),
    ("bishop-take", "b7", "not_on_line"),
    ("king-take", "f5", "protected"),
    ("queen-take", "d6", "jumped"),
])
def test_wrong_take_taps(item_id, square, kind):
    out = fs.grade(_item(item_id), {"square": square})
    assert out["kind"] == kind
    hint = _item(item_id).get("hints", {}).get(kind)
    if hint:
        assert out["say"] == hint


def test_tap_reach_needs_every_square():
    item = _item("knight-corner")
    first = fs.grade(item, {"square": "b3"})
    assert first["outcome"] == "progress"
    second = fs.grade(item, {"square": "c2"}, first["state"])
    assert second["outcome"] == "right"
    again = fs.grade(item, {"square": "c2"}, second["state"])
    assert again["outcome"] == "ignored"


@pytest.mark.parametrize("item_id,move,kind", [
    ("mate-queen", "a7f7", "stalemate"),
    ("mate-queen", "a7a1", "check_not_mate"),
    ("mate-queen", "a7e7", "no_check"),
    ("check-escape", "b3d4", "leaves_check"),
    ("check-give", "g1g2", "no_check"),
    ("pawn-promote", "e1d2", "not_goal"),
])
def test_wrong_moves(item_id, move, kind):
    out = fs.grade(_item(item_id), {"move": move})
    assert out["outcome"] == "wrong" and out["kind"] == kind, out


def test_promotion_without_a_piece_letter_becomes_a_queen():
    out = fs.grade(_item("pawn-promote"), {"move": "b7b8"})
    assert out["outcome"] == "right" and out["san"].startswith("b8=Q")


def test_stars_fewest_and_longer_routes():
    item = _item("rook-stars-1")
    state = None
    for sq in ("a6", "f6", "f2"):
        out = fs.grade(item, {"square": sq}, state)
        state = out["state"]
    assert out["outcome"] == "right"
    state = None
    for sq in ("a3", "a6", "f6", "f2"):
        out = fs.grade(item, {"square": sq}, state)
        state = out["state"]
    assert out["outcome"] == "done" and out["kind"] == "extra_moves"
    wall = fs.grade(_item("rook-stars-2"), {"square": "a6"})
    assert wall["kind"] == "jumped"


def test_the_targets_are_black_pawns_that_vanish_when_captured():
    item = _item("rook-stars-1")
    assert fs.public_item(item)["fen"].split()[0] == "8/8/p4p2/8/8/8/5p2/R7"
    out = fs.grade(item, {"square": "a6"})
    assert fs.public_item(item, out["state"])["fen"].split()[0] == "8/8/R4p2/8/8/8/5p2/8"
    blocked = fs.grade(item, {"square": "a7"})      # past the pawn on a6
    assert blocked["kind"] == "jumped"


def test_a_king_can_capture_a_target_pawn_next_to_it():
    item = _item("king-stars")
    state = None
    for sq in ("b2", "c3"):
        out = fs.grade(item, {"square": sq}, state)
        state = out["state"]
    assert "c3" not in state["left"]


def test_a_right_move_returns_the_position_after_it():
    out = fs.grade(_item("mate-test"), {"move": "h1h8"})
    assert out["fen_after"].split()[0] == "k6R/8/1K6/8/8/8/8/8"


@pytest.mark.parametrize("item_id", ["pawn-race", "queen-race", "mate-game"])
def test_games_always_end(item_id):
    item = _item(item_id)
    rng = random.Random(7)
    for _ in range(30):
        state = None
        for _ply in range(80):
            board = fs.board_of((state or {}).get("fen") or item["fen"])
            if item["game"] == "queen_mate":
                moves = [m.uci() for m in board.legal_moves]
            else:
                moves = [chess.Move(s, t).uci() for s, p in board.piece_map().items()
                         if p.color == board.turn for t in fs.reach(board, s)]
            out = fs.grade(item, {"move": rng.choice(moves)}, state)
            assert out["outcome"] in ("progress", "right", "done"), out
            state = out["state"]
            if out["outcome"] != "progress":
                assert out["result"] in ("won", "lost", "draw")
                break
        else:
            pytest.fail(f"{item_id} did not end in 80 moves")


STOCKFISH = next((p for p in ("/usr/games/stockfish", "/usr/local/bin/stockfish", "/usr/bin/stockfish")
                  if __import__("os").path.exists(p)), None)


@pytest.mark.skipif(STOCKFISH is None, reason="needs the Stockfish binary")
def test_queen_mate_can_be_won_within_the_move_limit():
    """Good play must win against our defending king inside max_moves, or the
    game can never be won and a child is told 'draw' however well they play."""
    import chess.engine
    item = _item("mate-game")
    engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH)
    try:
        state, out = None, None
        for _ in range(item["max_moves"]):
            board = fs.board_of((state or {}).get("fen") or item["fen"])
            move = engine.play(board, chess.engine.Limit(depth=12)).move
            out = fs.grade(item, {"move": move.uci()}, state)
            state = out["state"]
            if out["outcome"] != "progress":
                break
        assert out.get("result") == "won", out
        assert state["moves"] <= item["max_moves"] // 2, f"good play needed {state['moves']} moves"
    finally:
        engine.quit()


def test_public_item_hides_answers():
    for _, item in ALL:
        shown = fs.public_item(item)
        assert "expect" not in shown and "hints" not in shown and "right" not in shown


def test_placement_and_next_class():
    assert fs.placement_level({"knight": False}) == 0
    assert fs.placement_level({"knight": True, "check": True, "mate": False}) == 1
    assert fs.placement_level({"knight": True, "check": True, "mate": True}) == 2
    assert fs.next_class(0, [])["id"] == "rook"
    assert fs.next_class(0, ["rook", "bishop"])["id"] == "queen"
    assert fs.next_class(1, [])["id"] == "check"
    assert fs.next_class(2, ["checkmate"])["id"] == "captures"


def test_warm_up_uses_recall_then_the_top_mistake():
    rook, bishop = fs.class_by_id("rook"), fs.class_by_id("bishop")
    warm = fs.warm_up_for(bishop, rook, {"jumped": 3, "like_bishop": 1})
    assert [w["id"] for w in warm] == ["rook-recall", "rook-blocked"]
    assert fs.warm_up_for(rook, None, {}) == []


def test_coach_notes_are_words():
    assert fs.coach_notes({"jumped": 3, "like_bishop": 2}) == [
        "tries to move through pieces", "moves pieces diagonally when they can't"]


def test_one_slip_is_not_a_note_about_the_child():
    key = next(iter(fs.NOTICE_WORDS))
    assert fs.coach_notes({key: 1}) == []
    assert fs.coach_notes({key: 2}) == [fs.NOTICE_WORDS[key]]
