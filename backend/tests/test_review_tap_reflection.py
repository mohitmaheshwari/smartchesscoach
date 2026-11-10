"""Game review tap reflection: docs/review_tap_reflection_scope.md.

The board decides every question and every grade; a moment the board cannot
grade keeps the button question (build_tap_moment returns None).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services import review_tap_reflection as rt  # noqa: E402

# Mohit's lichess game (main account copy), move 9 as White: Ne2 leaves the
# queen on f3 to the knight on e5. Stored as piece_safety.simple_hang.
NE2_BEFORE = "r1bq1rk1/pp1p1ppp/4pn2/4n3/1b2P3/1BN2Q2/PPP2PPP/R1B1K1NR w KQ - 9 9"
# The test account's copy of the same opening, move 8: Qf3 itself lands where
# the knight on e5 takes it, and Black did take.
QF3_BEFORE = "r1bqk2r/pp1p1ppp/4pn2/4n3/1b2P3/1BN5/PPP2PPP/R1BQK1NR w KQkq - 7 8"
QF3_AFTER = "r1bqk2r/pp1p1ppp/4pn2/4n3/1b2P3/1BN2Q2/PPP2PPP/R1B1K1NR b KQkq - 8 8"


def _event(event_id="g:17:x:allowed", concept="piece_safety.simple_hang", cause=None,
           eligible=True):
    e = {"event_id": event_id, "concept": {"id": concept},
         "display": {"authorized": True, "reflection_eligible": eligible},
         "evidence": {"quality_id": "q"}}
    if cause is not None:
        e["cause"] = cause
    return e


def test_simple_hang_asks_about_the_piece_that_can_be_taken_not_the_one_that_moved():
    m = rt.build_tap_moment(_event(), {"fen_before": NE2_BEFORE, "move_san": "Ne2"}, None)
    assert m["kind"] == "landing"
    assert m["to"] == "e2"
    assert m["target"] == {"sq": "f3", "piece": "queen"}
    assert [(a["sq"], a["piece"], a["kind"]) for a in m["test"]["answer"]] == [("e5", "knight", "knight")]


def test_the_reply_that_takes_the_target_carries_the_cost():
    m = rt.build_tap_moment(
        _event(cause={"kind": "legal_material_loss", "affected": {"piece": "queen", "square": "f3"}}),
        {"fen_before": QF3_BEFORE, "move_san": "Qf3"},
        {"fen_before": QF3_AFTER, "move_san": "Nxf3+"},
    )
    assert m["target"] == {"sq": "f3", "piece": "queen"}
    assert m["reply_san"] == "Nxf3+"
    assert m["cost"] == {"lost": "queen", "won": "knight", "can_recapture": True}
    # The tap flow's "what was it for": the queen now attacks the knight on f6.
    assert any(i["kind"] == "attack" and i["sq"] == "f6" for i in m["intents"])


def test_a_reply_from_a_different_position_is_ignored():
    m = rt.build_tap_moment(
        _event(cause={"kind": "legal_material_loss", "affected": {"piece": "queen", "square": "f3"}}),
        {"fen_before": QF3_BEFORE, "move_san": "Qf3"},
        {"fen_before": NE2_BEFORE, "move_san": "Ne2"},
    )
    assert m["reply_san"] is None and "cost" not in m


EXCH = {"kind": "verified_stored_line", "lesson_kind": "exchange_sequence"}
# White takes on e5; the c6 knight takes back. With the d-pawn on d4 White can
# take back again (an even trade); without it the knight is simply gone.
NXE5_WITH_D4 = "r1bqkbnr/pppp1ppp/2n5/4p3/3PP3/5N2/PPP2PPP/RNBQKB1R w KQkq - 0 3"
NXE5_NO_D4 = "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3"


def _after(fen, san):
    import chess
    b = chess.Board(fen)
    b.push_san(san)
    return b.fen()


def test_exchange_moment_asks_only_when_his_reply_took_the_piece():
    took = rt.build_tap_moment(_event(cause=EXCH), {"fen_before": NXE5_NO_D4, "move_san": "Nxe5"},
                               {"fen_before": _after(NXE5_NO_D4, "Nxe5"), "move_san": "Nxe5"})
    assert took["target"] == {"sq": "e5", "piece": "knight"}
    assert took["cost"] == {"lost": "knight", "won": "knight", "can_recapture": False}
    quiet = rt.build_tap_moment(_event(cause=EXCH), {"fen_before": NXE5_NO_D4, "move_san": "Nxe5"},
                                {"fen_before": _after(NXE5_NO_D4, "Nxe5"), "move_san": "Qe7"})
    assert quiet is None
    no_reply = rt.build_tap_moment(_event(cause=EXCH), {"fen_before": NXE5_NO_D4, "move_san": "Nxe5"}, None)
    assert no_reply is None


def test_an_even_trade_is_not_described_as_a_cost():
    m = rt.build_tap_moment(_event(cause=EXCH), {"fen_before": NXE5_WITH_D4, "move_san": "Nxe5"},
                            {"fen_before": _after(NXE5_WITH_D4, "Nxe5"), "move_san": "Nxe5"})
    assert m["reply_san"] == "Nxe5"
    assert "cost" not in m


def test_nothing_can_take_it_means_no_tap_question():
    start = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    m = rt.build_tap_moment(
        _event(cause={"kind": "verified_stored_line", "lesson_kind": "exchange_sequence"}),
        {"fen_before": start, "move_san": "e4"}, None)
    assert m is None


def test_a_pinned_piece_is_not_offered_as_a_taker():
    # The black knight on c6 attacks the white knight on d4, but the bishop on
    # b5 pins it to the king on e8, so it cannot legally take. The d5 pawn
    # blocks the queen. A plain "attackers" count would wrongly say c6.
    import chess
    after = chess.Board("r1bqkbnr/ppp2ppp/2n5/1B1p4/3N4/8/PPP2PPP/RNBQK2R b KQkq - 0 5")
    d4 = chess.parse_square("d4")
    assert chess.parse_square("c6") in after.attackers(chess.BLACK, d4)
    assert rt._takers(after, d4) == []


def test_missed_material_finds_the_stored_best_and_names_what_it_takes():
    cause = {"kind": "verified_stored_line", "lesson_kind": "missed_material_opportunity",
             "best_captures": [{"actor": "initiator", "ply": 1, "captured_piece": "knight",
                                "captured_square": "e5"}]}
    fen = "r1bqkbnr/pppp1ppp/8/4n3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 0 4"
    m = rt.build_tap_moment(_event(cause=cause), {"fen_before": fen, "move_san": "d4",
                                                  "best_move_uci": "f3e5"}, None)
    assert m["kind"] == "missed_tactic" and m["pattern"] is None
    assert m["test"]["accept"] == ["f3e5"] and m["test"]["best"]["san"] == "Nxe5"
    assert m["test"]["explain"]["wins"] == {"piece": "knight", "sq": "e5", "first": True}
    assert "f3e5" in m["practice"]["moves"] and "loss" not in m["practice"]["moves"]["f3e5"]


def test_missed_mate_is_a_find_the_move_test():
    fen = "6k1/5ppp/8/8/8/8/5PPP/3R2K1 w - - 0 1"
    m = rt.build_tap_moment(
        _event(cause={"kind": "verified_stored_line", "lesson_kind": "missed_forced_mate"}),
        {"fen_before": fen, "move_san": "Kf1", "best_move_uci": "d1d8"}, None)
    assert m["pattern"] == "mate" and m["test"]["explain"]["mate"] is True


def test_kinds_without_a_built_test_keep_the_buttons():
    for cause in ({"kind": "verified_stored_line", "lesson_kind": "allowed_forced_mate"},
                  {"kind": "exact_endgame"}):
        assert rt.tap_kind(_event(cause=cause)) is None


def test_found_when_asked_is_graded_from_the_board():
    m = rt.build_tap_moment(_event(), {"fen_before": NE2_BEFORE, "move_san": "Ne2"}, None)
    assert rt.found_when_asked(m, ["e5"]) is True
    assert rt.found_when_asked(m, ["f6"]) is False
    assert rt.found_when_asked(m, []) is False
    find = {"test": {"kind": "find_move", "accept": ["f3e5"]}}
    assert rt.found_when_asked(find, ["f3e5"]) is True
    assert rt.found_when_asked(find, ["a2a3", "b2b3", "f3e5"]) is False  # third try does not count
    assert rt.found_when_asked(find, ["c2c3"], also_good=["c2c3"]) is True


def test_the_keep_line_follows_the_cause():
    m = rt.build_tap_moment(_event(), {"fen_before": NE2_BEFORE, "move_san": "Ne2"}, None)
    assert "knight could jump" in rt.keep_line(m, "unknown_pattern")
    assert rt.keep_line(m, "not_looking").startswith("Before any piece lands, look from that square")
    assert "count what you lose" in rt.keep_line(m, "misjudged")
    assert rt.keep_line(m, None) is None  # an unclear answer keeps the event's own principle


def test_the_document_stores_the_cause_and_no_raw_position():
    m = rt.build_tap_moment(_event(), {"fen_before": NE2_BEFORE, "move_san": "Ne2"}, None)
    answers = {"picks": [], "tapped": ["e5"], "seen_in_game": "no", "found_when_asked": True}
    doc = rt.build_document(user_id="u", game_id="g", event=_event(), m=m, answers=answers)
    assert doc["reflection_kind"] == "game_review_tap"
    assert doc["response"]["cause"] == "not_looking"
    assert doc["response"]["summary"] == ["You found his knight on e5 when you looked.",
                                          "In the game you didn't see it."]
    assert "fen" not in str(doc).lower()
    hist = rt.public_tap_history([doc])
    assert hist == [{"event_id": "g:17:x:allowed", "cause": "not_looking",
                     "keep_line": doc["response"]["keep_line"], "summary": doc["response"]["summary"]}]


def test_clean_answers_drops_anything_the_page_should_not_decide():
    m = {"test": {"kind": "tap_pieces", "answer": []}}
    out = rt.clean_answers(m, {"picks": [{"kind": "attack", "sq": "f6"}, {"kind": "hack"}],
                               "tapped": ["e5", "x" * 40], "seen_in_game": "maybe",
                               "found_when_asked": True})
    assert out == {"picks": [{"kind": "attack", "sq": "f6"}], "tapped": ["e5"], "seen_in_game": "unsure"}


def test_attach_only_builds_for_eligible_events_in_the_response():
    rows = [
        {"fen_before": NE2_BEFORE, "move_san": "Ne2", "teachable_event": _event("a")},
        {"fen_before": NE2_BEFORE, "move_san": "Ne2", "teachable_event": _event("b")},
    ]
    resp = {"teachable_events": [_event("a"), _event("b", eligible=False)]}
    rt.attach_tap_moments(resp, rows)
    assert [m["key"] for m in resp["tap_moments"]] == ["a"]


def test_find_stored_moment_refuses_an_event_that_cannot_take_reflection():
    rows = [{"fen_before": NE2_BEFORE, "move_san": "Ne2", "teachable_event": _event("a", eligible=False)}]
    assert rt.find_stored_moment(rows, "a") == (None, None)
    rows[0]["teachable_event"] = _event("a")
    ev, m = rt.find_stored_moment(rows, "a")
    assert ev["event_id"] == "a" and m["target"]["sq"] == "f3"
