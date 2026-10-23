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

    def test_a_move_not_in_the_facts_is_refused(self):
        assert self.ok("You won after your opponent missed chances",
                       "After Qxd5 your opponent could have won. Check their best reply first.") \
            .startswith("invented chess")

    def test_a_move_in_the_facts_may_be_used(self):
        assert self.ok("You won after your opponent missed chances",
                       "After Ng5, Rh1 would have left your queen no safe square. Check their best reply first.") is None

    def test_a_word_the_facts_only_imply_is_still_refused(self):
        # True by the ledger, but the facts given to the model say "no safe
        # square", not "trapped"; the check is about what it was told.
        assert self.ok("You won after your opponent missed chances",
                       "After Ng5, Rh1 would have trapped your queen. Check their best reply first.") \
            == "not in the facts: trapped"

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
