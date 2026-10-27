"""The home card's title and teaching: model-written, but only from verified
facts, and refused the moment it says anything those facts do not."""
import asyncio
import re

import services.game_headline as H

FACTS = [
    "The student won by resignation.",
    "The game's story: A win with narrow escapes.",
    "The student gave away a winning position twice, and the opponent did not punish it.",
    "Ng5 nearly cost you your queen. After Rh1, she would have had no safe square. They played f4 instead.",
]

STORY = {
    "plan": {"type": {"title": "A win with narrow escapes"},
             "home_lines": [{"text": FACTS[3]}],
             "lesson": {"text": "Your opponent let you off more than once."}},
    "ledger": {"outcome": "win", "events": [
        {"kind": "your_mistake", "decisive": True, "punished": False},
        {"kind": "your_mistake", "decisive": True, "punished": False},
        {"kind": "their_mistake", "decisive": True, "taken": True},
    ]},
    "tags": {"ids": ["user_let_off"]},
}
GAME = {"game_id": "g1", "termination": "resignation"}


class TestValidator:
    def ok(self, title, teaching, outcome="win"):
        return H.validate(FACTS, title, teaching, outcome)

    def test_a_good_headline_passes(self):
        assert self.ok("You won after your opponent missed chances",
                       "You gave away a winning position twice. Look for their best reply "
                       "before you move.") is None

    def test_no_move_may_be_named_even_one_in_the_facts(self):
        """Mohit, 2026-10-23: a title "without naming the moves". The story
        lines under the headline carry the moves."""
        assert self.ok("You won after your opponent missed chances",
                       "After Ng5 your queen had no safe square. Check their best reply first.") \
            .startswith("named a move")
        assert self.ok("You won after Qxd5 went unpunished",
                       "You gave away a winning position twice. Look for their best reply.") \
            .startswith("named a move")

    def test_a_square_is_a_move_too(self):
        assert self.ok("You won after your opponent missed chances",
                       "Your queen on h4 had no safe square. Check their best reply first.") \
            .startswith("named a move")

    def test_a_word_the_facts_only_imply_is_still_refused(self):
        # True by the ledger, but the facts given to the model say "no safe
        # square", not "trapped"; the check is about what it was told.
        assert self.ok("You won after your opponent missed chances",
                       "Your queen was nearly trapped. Check their best reply before you move.") \
            == "not in the facts: trapped"

    def test_a_pattern_the_facts_never_name_is_refused(self):
        assert self.ok("You won after your opponent missed chances",
                       "You missed a fork twice. Check their best reply before you move.") \
            == "not in the facts: fork"

    def test_numbers_are_refused(self):
        assert self.ok("You won after 2 narrow escapes",
                       "You gave away a winning position twice. Look for their best reply.") == "a number"

    def test_a_piece_the_facts_never_mention_is_refused(self):
        assert self.ok("You won after your opponent missed chances",
                       "Your bishop was loose twice. Look for their best reply before you move.") \
            == "not in the facts: bishop"

    def test_checkmate_in_the_facts_covers_mate(self):
        facts = FACTS + ["The student lost by checkmate."]
        assert H.validate(facts, "They found the mate in the end",
                          "Watch your king and look for their best reply before you move.", "loss") is None

    def test_empty_praise_is_refused(self):
        """Mohit's complaint was exactly this word."""
        assert self.ok("You were the steadier player",
                       "You gave away a winning position twice. Look for their best reply.") \
            == "empty praise: steadier"

    def test_a_title_that_contradicts_the_result_is_refused(self):
        assert H.validate(FACTS, "You won in the end", "You gave away a winning position twice. "
                          "Look for their best reply.", "loss") == "title contradicts the result"

    def test_empty_or_too_short_is_refused(self):
        assert self.ok("", "something") == "empty"
        assert self.ok("Won", "You gave away a winning position twice. Look first.") == "title length"


class TestFacts:
    def test_facts_have_no_digits_and_name_what_happened(self):
        facts = H.headline_facts(STORY, GAME)
        assert "The student won by resignation." in facts
        assert any("gave away a winning position twice" in f for f in facts)
        assert any("made them pay once" in f for f in facts)
        for fact in facts:
            assert not re.search(r"\d", H._TOKEN.sub("", fact)), fact

    def test_no_pay_is_said_plainly(self):
        story = {**STORY, "ledger": {"outcome": "win", "events": [
            {"kind": "their_mistake", "decisive": True, "taken": False}]}}
        facts = H.headline_facts(story, GAME)
        assert any(f.endswith("the student did not make them pay.") for f in facts)


class _Coll:
    def __init__(self):
        self.rows = []

    async def find_one(self, query, projection=None):
        for r in self.rows:
            if all(r.get(k) == v for k, v in query.items()):
                return dict(r)
        return None

    def find(self, query, projection=None):
        rows = [r for r in self.rows if all(r.get(k) == v for k, v in query.items())]

        class _Cursor:
            async def to_list(self, length=None):
                return rows
        return _Cursor()

    async def update_one(self, query, update, upsert=False):
        for r in self.rows:
            if all(r.get(k) == v for k, v in query.items()):
                r.update(update["$set"])
                return
        self.rows.append({**query, **update["$set"]})


class _Db(dict):
    def __missing__(self, key):
        self[key] = _Coll()
        return self[key]


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class TestHeadlineForGame:
    def test_a_passing_model_headline_is_used_and_cached(self, monkeypatch):
        calls = []

        async def fake(facts, outcome):
            calls.append(1)
            return {"ok": True, "title": "You won after your opponent missed chances",
                    "teaching": "Look for their best reply before you move.", "model": "m"}

        monkeypatch.setattr(H, "write_headline", fake)
        db = _Db()
        first = _run(H.headline_for_game(db, GAME, STORY))
        again = _run(H.headline_for_game(db, GAME, STORY))
        assert first["source"] == "llm" and first["title"].startswith("You won after")
        assert again["title"] == first["title"]
        assert len(calls) == 1

    def test_a_rejected_headline_falls_back_to_rules(self, monkeypatch):
        async def fake(facts, outcome):
            return {"ok": False, "reason": "empty praise: steadier", "model": "m"}

        monkeypatch.setattr(H, "write_headline", fake)
        result = _run(H.headline_for_game(_Db(), GAME, STORY))
        assert result["source"] == "rules"
        assert result["title"] == "A win with narrow escapes"
        assert "stronger player" in result["teaching"]

    def test_a_model_outage_is_not_cached(self, monkeypatch):
        async def down(facts, outcome):
            return {"ok": False, "reason": "llm_error", "model": "m"}

        monkeypatch.setattr(H, "write_headline", down)
        db = _Db()
        _run(H.headline_for_game(db, GAME, STORY))
        assert db[H.COLLECTION].rows == []


class TestMainPoint:
    def test_a_win_the_opponent_let_happen_says_so(self):
        """Mohit's game: the model had written "You won when your opponent
        resigned" -- true, and not the point."""
        assert H.main_point(STORY).startswith("the student won partly because the opponent missed")
        assert any(f.startswith("MAIN POINT:") for f in H.headline_facts(STORY, GAME))

    def test_a_lost_winning_position(self):
        story = {"plan": {"type": {"id": "slipped_away"}},
                 "ledger": {"outcome": "loss", "events": []}}
        assert H.main_point(story) == "the student had a winning position and lost it"

    def test_a_loss_names_what_decided_it(self):
        """1,468 losses were titled "Your big mistakes were punished"; 847 of
        them had a mate, a lost queen or a lost rook the title never said."""
        punished = {"kind": "your_mistake", "decisive": True, "punished": True,
                    "danger": {"kind": "queen_lost"}}
        story = {"plan": {"type": {"id": "hard_game"}},
                 "ledger": {"outcome": "loss", "events": [punished]}}
        assert H.main_point(story) == ("the opponent punished the student's big mistakes, "
                                       "and the student lost the queen")
        mated = {**story, "tags": {"ids": ["user_suffered_back_rank_mate"]}}
        assert H.main_point(mated).endswith("and the game ended in a back rank checkmate")
        by_queen = {**story, "tags": {"ids": ["user_suffered_queen_mate"]}}
        assert H.main_point(by_queen).endswith("checkmate by the opponent's queen")

    def test_an_unpunished_danger_did_not_decide_the_loss(self):
        story = {"plan": {"type": {"id": "hard_game"}},
                 "ledger": {"outcome": "loss", "events": [
                     {"kind": "your_mistake", "decisive": True, "punished": False,
                      "danger": {"kind": "queen_trapped"}}]}}
        assert H.main_point(story) == "the opponent was better for most of the game"

    def test_a_mistake_is_named_only_when_it_came_back(self, monkeypatch):
        monkeypatch.setattr(H, "_allowed", lambda qid: True)
        story = {"plan": {"type": {"id": "slipped_away"}},
                 "ledger": {"outcome": "loss", "events": []}}
        hang = {"subtype": "simple_hang", "missed_pattern": "piece_safety", "phase": "middlegame"}
        assert H.main_point(story, [hang]) == "the student had a winning position and lost it"
        assert H.main_point(story, [hang, hang]) == (
            "the student had a winning position and lost it, and one mistake came more than "
            "once: left a piece undefended")
        pin = {"subtype": "missed_pin", "missed_pattern": "missed_tactic", "phase": "opening"}
        assert H.main_point(story, [pin, pin]).endswith("and the student missed a pin more than once")

    def test_a_loss_with_no_named_cause_says_the_missed_chances(self):
        story = {"plan": {"type": {"id": "game"}}, "tags": {"ids": ["user_missed_their_blunder"]},
                 "ledger": {"outcome": "loss", "events": []}}
        assert H.main_point(story) == ("the student lost, and the opponent made big mistakes too, "
                                       "and the student did not take them")

    def test_wins_are_unchanged(self):
        assert H.main_point({**STORY, "tags": {"ids": ["user_suffered_back_rank_mate"]}}) \
            .startswith("the student won partly because")

    def test_no_point_is_invented(self):
        assert H.main_point({"plan": {"type": {"id": "game"}},
                             "ledger": {"outcome": "draw", "events": []}}) is None


class TestSentenceCase:
    FACTS = ["The student lost by resignation.",
             "You came out of the Scotch Game with the better position.",
             "Ng5 nearly cost you your queen."]

    def test_title_case_is_lowered(self):
        assert H.sentence_case("They Punished Your Big Mistakes", self.FACTS) == \
            "They punished your big mistakes"

    def test_opening_names_and_moves_keep_their_capitals(self):
        assert H.sentence_case("The Scotch Game Went Wrong After Ng5", self.FACTS) == \
            "The Scotch Game went wrong after Ng5"


class TestObservationFacts:
    def test_only_gate_allowed_names_and_no_moves(self):
        observations = [
            {"subtype": "missed_fork", "missed_pattern": "missed_tactic", "phase": "middlegame", "move_san": "Nf3"},
            {"subtype": "missed_fork", "missed_pattern": "missed_tactic", "phase": "middlegame", "move_san": "Nc3"},
            {"subtype": "missed_generic_tactic", "missed_pattern": "missed_tactic", "phase": "opening"},
            {"found_best_in_critical": True, "move_san": "Bxc3"},
        ]
        facts = H.observation_facts(observations)
        assert facts[0] == ("Pattern in the student's mistakes: Fork you could have played, "
                            "twice, mostly in the middlegame.")
        assert "Pattern in the student's good moves: Found the best move in a sharp moment, once." in facts
        assert not any("generic" in f.lower() for f in facts)
        assert not any(H._TOKEN.search(f) for f in facts)

    def test_tags_read_as_phrases(self):
        phrases = H.tag_phrases({"user_never_castled", "user_queen_trapped_opponent_missed",
                                 "result_win", "story_clean_win", "user_let_off"})
        assert phrases == ["never castled", "queen trapped, and the opponent missed it"]


class TestOneModelCallPerGame:
    """Mohit, 2026-10-23: "once LLM is used, don't make another call,
    llm_used = true, no LLM"."""

    def test_a_used_game_is_never_asked_again_even_if_its_facts_change(self, monkeypatch):
        calls = []

        async def fake(facts, outcome):
            calls.append(1)
            return {"ok": True, "title": "You won after your opponent missed chances",
                    "teaching": "Look for their best reply before you move.", "model": "m"}

        monkeypatch.setattr(H, "write_headline", fake)
        db = _Db()
        first = _run(H.headline_for_game(db, GAME, STORY))
        changed = {**STORY, "plan": {**STORY["plan"], "type": {"title": "Something else"}}}
        again = _run(H.headline_for_game(db, GAME, changed))
        assert len(calls) == 1
        assert first["llm_used"] is True and again["title"] == first["title"]

    def test_a_refused_answer_still_counts_as_used(self, monkeypatch):
        calls = []

        async def refused(facts, outcome):
            calls.append(1)
            return {"ok": False, "reason": "named a move: ['Ng5']", "model": "m"}

        monkeypatch.setattr(H, "write_headline", refused)
        db = _Db()
        _run(H.headline_for_game(db, GAME, STORY))
        _run(H.headline_for_game(db, GAME, STORY))
        assert len(calls) == 1
        assert db[H.COLLECTION].rows[0]["llm_used"] is True

    def test_an_outage_does_not_count_as_used(self, monkeypatch):
        calls = []

        async def down(facts, outcome):
            calls.append(1)
            return {"ok": False, "reason": "llm_error", "model": "m"}

        monkeypatch.setattr(H, "write_headline", down)
        db = _Db()
        _run(H.headline_for_game(db, GAME, STORY))
        _run(H.headline_for_game(db, GAME, STORY))
        assert len(calls) == 2


class TestHonestWordsAreNotRefused:
    """With one model call per game a wrong refusal is permanent. The first
    336 backfilled games showed 21 of 25 refusals were honest words."""

    def test_outplayed_in_a_loss_is_honest(self):
        facts = ["The student lost by resignation.",
                 "MAIN POINT: the opponent was better for most of the game."]
        assert H.validate(facts, "The opponent outplayed you from the start",
                          "They were better for most of the game. Look for safer moves and "
                          "their best reply.", "loss") is None

    def test_steady_and_time_as_advice(self):
        assert H.validate(FACTS, "You won after your opponent missed chances",
                          "Stay steady and take your time. Look for their best reply before "
                          "you move.", "win") is None

    def test_steadier_is_still_refused(self):
        assert H.validate(FACTS, "You were the steadier player",
                          "You gave away a winning position twice. Look for their best reply.",
                          "win") == "empty praise: steadier"
