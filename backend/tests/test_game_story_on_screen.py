"""The rules that make the game story safe to put on a screen.

Signed off by Mohit 2026-10-21, docs/game_story_on_screen_scope.md. Measured
on the last three games of the 60 most active players (168 games) before
these rules existed:

    lost games                                   79
    lost games whose deciding move was hidden    41
    lost games that led with a compliment        15
    games headlined "Answered a threat"          12

Each class below pins one rule from the scope.
"""
import re

from services.both_sides_review import story_card_fields
from services.game_story import (
    LOCATED_ID,
    MAX_HOME_LINES,
    build_game_story,
)

SHADOW = "gap:missed_tactic:missed_generic_tactic"


def observation(**kw):
    base = {"move_number": 30, "ply": 59, "color": "white",
            "severity": "moderate", "cp_loss": 150,
            "eval_before": 20, "eval_after": -130,
            "move_san": "Kg3", "move_uci": "f2g3",
            "fen_before": "8/8/8/8/8/8/5K2/k7 w - - 0 30"}
    base.update(kw)
    return base


def decisive_mistake(subtype="missed_generic_tactic",
                     pattern="missed_tactic", **kw):
    kw.setdefault("eval_before", 400)
    kw.setdefault("eval_after", -250)
    kw.setdefault("cp_loss", 650)
    kw.setdefault("severity", "critical")
    return observation(missed_pattern=pattern, subtype=subtype, **kw)


def found_best(**kw):
    kw.setdefault("move_number", 39)
    kw.setdefault("move_san", "b4")
    kw.setdefault("move_uci", "b3b4")
    return observation(found_best_in_critical=True, **kw)


def answered_threat(**kw):
    kw.setdefault("move_number", 2)
    kw.setdefault("move_san", "Nf3")
    kw.setdefault("move_uci", "g1f3")
    return observation(responded_to_threat=True, **kw)


def hide_shadow(quality_id):
    return quality_id != SHADOW


def story(observations, *, outcome, showable=hide_shadow):
    return build_game_story(
        observations=list(observations),
        move_evaluations=[],
        user_color="white",
        is_showable=showable,
        outcome=outcome,
    )


class TestALostGameNeverLeadsWithACompliment:
    def test_a_hidden_deciding_mistake_is_located_by_its_move(self):
        """Game 20619e20 before the rule: lost, headlined 'Found the best
        move when it mattered', while the move that lost it was hidden."""
        result = story([decisive_mistake(), found_best()], outcome="loss")
        lead = result["headline"]
        assert lead["id"] == LOCATED_ID
        assert lead["display_name"] == "This is where the game got away."
        assert lead["move_san"] == "Kg3"
        # It names no detector, so it quotes none.
        assert lead["detector_quality_id"] is None
        assert lead["located_from"] == SHADOW

    def test_the_hidden_moment_stays_on_the_record(self):
        result = story([decisive_mistake(), found_best()], outcome="loss")
        assert any(m["id"] == "missed_generic_tactic" for m in result["moments"])

    def test_a_named_deciding_mistake_leads_without_a_located_line(self):
        named = decisive_mistake("simple_hang", "piece_safety")
        result = story([named, found_best()], outcome="loss")
        assert result["headline"]["id"] == "simple_hang"
        assert all(m["id"] != LOCATED_ID for m in result["moments_showable"])

    def test_only_compliments_in_a_loss_means_no_compliment_leads(self):
        result = story([found_best()], outcome="loss")
        assert result["headline"] is None or result["headline"]["polarity"] != "positive"
        # The compliment is still in the story, lower down.
        assert any(m["polarity"] == "positive" for m in result["moments_showable"])

    def test_a_won_game_may_lead_with_a_compliment(self):
        result = story([found_best()], outcome="win")
        assert result["headline"]["id"] == "found_best_in_critical"

    def test_outside_a_loss_the_located_line_does_not_say_got_away(self):
        result = story([decisive_mistake(), found_best()], outcome="win")
        assert result["headline"]["display_name"] == "This move gave a lot away."


class TestAnsweredAThreatNeverLeads:
    def test_it_never_leads(self):
        result = story([answered_threat()], outcome="win")
        assert result["headline"] is None

    def test_it_never_reaches_home(self):
        result = story([answered_threat(), found_best()], outcome="win")
        assert all(line["id"] != "responded_to_threat"
                   for line in result["home_lines"])

    def test_it_can_still_appear_in_the_review(self):
        result = story([answered_threat(), found_best()], outcome="win")
        assert any(m["id"] == "responded_to_threat"
                   for m in result["moments_showable"])


class TestHomeLines:
    def test_at_most_three(self):
        many = [decisive_mistake("simple_hang", "piece_safety"),
                found_best(),
                observation(missed_pattern="piece_safety", subtype="small_slip",
                            move_san="a3", move_uci="a2a3")]
        result = story(many, outcome="loss")
        assert len(result["home_lines"]) <= MAX_HOME_LINES

    def test_the_headline_comes_first(self):
        result = story([decisive_mistake(), found_best()], outcome="loss")
        assert result["home_lines"][0]["id"] == result["headline"]["id"]


def review(turning):
    return {"turning_point": turning}


THEIRS_LATER = {"move_number": 31, "san": "Ne6+", "whose": "theirs",
                "fen_before": "8/8/8/8/8/8/8/k6K b - - 0 31",
                "board_orientation": "white"}
THEIRS_EARLIER = {**THEIRS_LATER, "move_number": 12, "san": "Qh5"}


class TestTheBoardAndTheFirstLineAgree:
    def test_the_board_follows_the_story_lead(self):
        result = story([decisive_mistake(), found_best()], outcome="loss")
        fields = story_card_fields(result, review(THEIRS_EARLIER),
                                   user_colour="white")
        assert fields["board"]["source"] == "story"
        assert fields["board"]["san"] == fields["story_lines"][0]["san"] == "Kg3"
        assert (fields["board"]["from"], fields["board"]["to"]) == ("f2", "g3")

    def test_no_story_move_falls_back_to_the_turning_point(self):
        fields = story_card_fields(None, review(THEIRS_LATER), user_colour="white")
        assert fields["board"]["source"] == "turning_point"
        assert fields["board"]["san"] == "Ne6+"
        assert fields["story_lines"] == []

    def test_their_later_error_is_told_after_his_deciding_one(self):
        """Game 8f40005b, checked by hand: Rxf3+ threw a won game away,
        Ne6+ gave it back, and the clock ended it."""
        result = story([decisive_mistake(), found_best()], outcome="loss")
        fields = story_card_fields(result, review(THEIRS_LATER), user_colour="white")
        assert [l["san"] for l in fields["story_lines"][:2]] == ["Kg3", "Ne6+"]
        assert fields["story_lines"][1]["text"] == "They went wrong here too."
        assert len(fields["story_lines"]) <= 3

    def test_every_line_reads_as_a_sentence(self):
        result = story([decisive_mistake(), found_best()], outcome="loss")
        fields = story_card_fields(result, review(THEIRS_LATER), user_colour="white")
        assert fields["story_lines"]
        assert all(l["text"].endswith(".") for l in fields["story_lines"])

    def test_their_earlier_error_is_not_called_a_second_one(self):
        result = story([decisive_mistake(), found_best()], outcome="loss")
        fields = story_card_fields(result, review(THEIRS_EARLIER), user_colour="white")
        assert all(l["kind"] != "theirs" for l in fields["story_lines"])


# A square or a move such as "Kg3", "a1" or "Rxf3+" is how a line is located,
# and the only place a digit may appear.
_SQUARE = re.compile(r"\b[a-h][1-8]\b")


class TestNoNumbersReachThePlayer:
    def test_no_digit_in_any_line_text(self):
        result = story([decisive_mistake(), found_best(), answered_threat()],
                       outcome="loss")
        fields = story_card_fields(result, review(THEIRS_LATER), user_colour="white")
        texts = [l["text"] for l in fields["story_lines"]]
        texts += [m["display_name"] for m in result["moments_showable"]]
        texts += [m["display_detail"] or "" for m in result["moments_showable"]]
        for text in texts:
            assert not re.search(r"\d", _SQUARE.sub("", text)), text


# ─── The one loader ─────────────────────────────────────────────────────


class _Cursor:
    def __init__(self, rows):
        self._rows = list(rows)

    async def to_list(self, length=None):
        return list(self._rows)

    def __aiter__(self):
        self._it = iter(self._rows)
        return self

    async def __anext__(self):
        try:
            return next(self._it)
        except StopIteration:
            raise StopAsyncIteration


class _Collection:
    def __init__(self, rows):
        self.rows = rows

    async def find_one(self, query, projection=None):
        for row in self.rows:
            if all(row.get(k) == v for k, v in query.items()):
                keep = [k for k, v in (projection or {}).items() if v and k != "_id"]
                return {k: row[k.split(".")[0]] for k in keep if k.split(".")[0] in row}
        return None

    def find(self, query, projection=None):
        return _Cursor(r for r in self.rows
                       if all(r.get(k) == v for k, v in query.items()))


class _Db:
    def __init__(self, analyses, observations=()):
        self.game_analyses = _Collection(analyses)
        self.move_observations = _Collection(list(observations))
        self.user_active_focus = _Collection([])


GAME = {"game_id": "g1", "user_id": "u1", "user_color": "white", "result": "0-1"}


class TestTheLoader:
    def _run(self, db):
        import asyncio
        from services.game_story import story_for_game
        # A private loop: asyncio.run() clears the shared one, and other
        # suites in the same session still call get_event_loop().
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(story_for_game(db, GAME))
        finally:
            loop.close()

    def test_an_analysis_with_no_stored_story_is_rebuilt_not_refused(self):
        """The projection of an analysis without `game_story` is {}, which is
        falsy; reading that as "not analysed" hid every older game."""
        db = _Db([{"game_id": "g1", "stockfish_analysis": {"move_evaluations": []}}],
                 [dict(decisive_mistake(), game_id="g1")])
        result = self._run(db)
        assert result is not None
        assert result["source"] == "recomputed"
        assert result["outcome"] == "loss"

    def test_no_analysis_at_all_is_none(self):
        assert self._run(_Db([])) is None

    def test_an_older_stored_story_is_rebuilt(self):
        db = _Db([{"game_id": "g1", "game_story": {"schema_version": "game_story.v2"},
                   "stockfish_analysis": {"move_evaluations": []}}])
        assert self._run(db)["source"] == "recomputed"
