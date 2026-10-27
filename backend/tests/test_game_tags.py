"""Game tags come only from the ledger, with the moves behind them."""
import re

from services.game_tags import TACTICALLY_ACTIVE_MIN, derive_game_tags


def mistake(san="Ng5", danger="queen_trapped", punished=False, decisive=True):
    return {"kind": "your_mistake", "side": "you", "san": san, "move_number": 16,
            "danger": {"kind": danger, "reply": "Rh1"}, "punished": punished,
            "decisive": decisive}


def ledger(events, outcome="win", opening=None):
    return {"events": events, "outcome": outcome,
            "opening": opening or {"name": "Queen's Pawn Opening", "eval_at_end": 140,
                                   "costliest": {"cp_loss": 100}}}


def test_mohits_example_queen_trapped_and_missed():
    tags = derive_game_tags(ledger([mistake()]))
    assert "user_queen_trapped_opponent_missed" in tags["ids"]
    assert "user_let_off" in tags["ids"]
    assert tags["moves"]["user_queen_trapped_opponent_missed"] == [
        {"move_number": 16, "san": "Ng5", "side": "you"}]


def test_punished_is_its_own_tag():
    tags = derive_game_tags(ledger([mistake(punished=True)]))
    assert "user_queen_trapped_opponent_punished" in tags["ids"]
    assert "user_lost_winning_position" in tags["ids"]
    assert "user_queen_trapped_opponent_missed" not in tags["ids"]


def test_rook_trap_and_mate():
    tags = derive_game_tags(ledger([mistake("Rd1", "rook_trapped"),
                                    mistake("Kg1", "mate_allowed", punished=True)]))
    assert {"user_rook_trapped_opponent_missed",
            "user_mate_allowed_opponent_punished"} <= set(tags["ids"])


def test_trapping_their_piece():
    boxed = {"kind": "you_boxed_in", "side": "you", "san": "e5", "move_number": 15,
             "piece": "knight", "won_it": "Bxh7"}
    tags = derive_game_tags(ledger([boxed]))
    assert {"user_trapped_opponent_knight", "user_won_trapped_knight"} <= set(tags["ids"])


def test_tactically_active_needs_three_successes():
    taken = {"kind": "their_mistake", "side": "them", "san": "f4", "move_number": 17,
             "decisive": True, "taken": True}
    found = {"kind": "your_good_move", "side": "you", "san": "Bxc3", "move_number": 17,
             "label": "found_best_in_critical"}
    two = derive_game_tags(ledger([taken, found]))
    assert "user_tactically_active" not in two["ids"]
    three = derive_game_tags(ledger([taken, found, {**taken, "san": "h4", "move_number": 13}]))
    assert TACTICALLY_ACTIVE_MIN == 3
    assert "user_tactically_active" in three["ids"]


def test_opening_family_and_verdict_and_result():
    tags = derive_game_tags(ledger([]), {"type": {"id": "clean_win"}})
    assert {"opening_queens_pawn_opening", "opening_came_out_better",
            "result_win", "story_clean_win"} <= set(tags["ids"])


def test_ids_are_plain_snake_case():
    tags = derive_game_tags(ledger([mistake()], opening={"name": "King's Indian Attack",
                                                         "eval_at_end": 0, "costliest": {}}))
    for tag in tags["ids"]:
        assert re.fullmatch(r"[a-z0-9_]+", tag), tag


class _Cur:
    def __init__(self, rows):
        self.rows = rows

    def __aiter__(self):
        self._it = iter(self.rows)
        return self

    async def __anext__(self):
        try:
            return next(self._it)
        except StopIteration:
            raise StopAsyncIteration

    async def to_list(self, length=None):
        return self.rows


class _Col:
    def __init__(self, rows):
        self.rows = rows

    def find(self, query, projection=None):
        ids = set(query["game_id"]["$in"])
        return _Cur([r for r in self.rows if r["game_id"] in ids])

    def aggregate(self, pipeline):
        from collections import Counter
        c = Counter(t for r in self.rows for t in r.get("tags", []))
        return _Cur([{"_id": t, "n": n} for t, n in c.items()])


def test_the_games_list_gets_titles_and_the_rarest_readable_tags():
    import asyncio
    import services.game_tags as T
    T._counts_cache.update(at=0.0, counts={})
    db = {
        "game_headlines": _Col([{"game_id": "g1", "title": "You won after your opponent missed chances"}]),
        "game_tag_index": _Col([
            {"game_id": "g1", "tags": ["result_win", "user_let_off", "user_queen_trapped_opponent_missed",
                                       "reached_rook_endgame", "user_punished_blunder", "time_control_rapid",
                                       "user_castled_queenside", "opposite_side_castling",
                                       "user_in_time_scramble", "user_never_castled"]},
            {"game_id": "g2", "tags": ["user_let_off", "user_punished_blunder"]},
            {"game_id": "g3", "tags": ["user_punished_blunder", "reached_rook_endgame"]},
        ]),
    }
    loop = asyncio.new_event_loop()
    try:
        out = loop.run_until_complete(T.list_fields_for_games(db, ["g1", "g2"]))
    finally:
        loop.close()
    assert out["g1"]["story_title"] == "You won after your opponent missed chances"
    labels = [t["label"] for t in out["g1"]["story_tags"]]
    # Rarest first (ties alphabetical); result, time-control and bare-fact
    # tags (castling side, time scramble, endgame reached) are never shown.
    assert labels == ["never castled", "queen trapped, opponent missed", "let off by the opponent"]
    assert out["g2"]["story_title"] is None


def test_list_labels_read_naturally():
    from services.game_tags import list_tag_label
    assert list_tag_label("user_won_trapped_knight") == "trapped and won their knight"
    assert list_tag_label("user_trapped_opponent_rook") == "shut in their rook"
    assert list_tag_label("user_delivered_back_rank_mate") == "back rank mate for you"
    assert list_tag_label("user_suffered_back_rank_mate") == "back rank mate against you"
    assert list_tag_label("user_delivered_queen_mate") == "mated with the queen"
    assert list_tag_label("user_suffered_knight_mate") == "mated by their knight"
