"""A published coach study becomes the card's caption (docs/why_study_on_card_scope.md).

Covers the pure pieces (caption, side, arrows), the side guard on the Why
button, and the re-render a ruling triggers. The V5 hook itself is checked on
real games with the dry-run render, not here.
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.abspath(os.path.join(_HERE, "..")))
sys.path.insert(0, os.path.abspath(_HERE))

import test_why_queue as base  # noqa: E402
from services import why_queue as wq  # noqa: E402


class _Games(base._Collection):
    async def update_many(self, query, update):
        m = self._match(query)
        for row in m:
            row.update(update.get("$set") or {})

        class _R:
            modified_count = len(m)
        return _R()


class _DB(base._DB):
    def __init__(self):
        super().__init__()
        self.game_analyses = _Games()


E5_CARD = "Your opponent played e5. That was a mistake. Play Nge7 — it brings a new piece into the game. They missed c3 here."
E5_STUDY = "Their e5 does not win back the pawn they gave up. So you stay one pawn up."
RF7_CARD = "Rf7 was a mistake. Kg7 was better. That lets them play Qg6 with check."


class TestTheCaption:
    def test_opponent_card_keeps_its_grade_line_and_takes_the_study(self):
        out = wq.card_caption_from_study(E5_CARD, E5_STUDY, "e5", mover_is_user=False)
        assert out == "Your opponent played e5. That was a mistake. " + E5_STUDY
        assert "Nge7" not in out

    def test_own_card_keeps_its_grade_line_and_takes_the_study(self):
        out = wq.card_caption_from_study(RF7_CARD, "Rf7 lets their queen go to g6 with check.", "Rf7",
                                         mover_is_user=True)
        assert out == "Rf7 was a mistake. Rf7 lets their queen go to g6 with check."

    def test_no_grade_line_means_the_study_alone(self):
        assert wq.card_caption_from_study("Something else entirely.", E5_STUDY, "e5",
                                          mover_is_user=False) == E5_STUDY
        assert wq.card_caption_from_study(None, E5_STUDY, "e5", mover_is_user=False) == E5_STUDY

    def test_a_san_with_regex_characters_is_matched_literally(self):
        out = wq.card_caption_from_study("Qh5+ was a mistake. Old.", "New.", "Qh5+", mover_is_user=True)
        assert out == "Qh5+ was a mistake. New."


class TestTheSide:
    def test_a_study_for_the_asker_who_faced_the_move(self):
        r = {"side": "opponent"}
        assert wq.study_fits_viewer(r, opponent=True) is True
        assert wq.study_fits_viewer(r, opponent=False) is False

    def test_a_study_for_the_asker_who_made_the_move(self):
        r = {"side": "user"}
        assert wq.study_fits_viewer(r, opponent=False) is True
        assert wq.study_fits_viewer(r, opponent=True) is False

    def test_the_why_button_never_shows_a_study_written_for_the_other_side(self):
        db = _DB()
        base._ask(db, base._nothing())
        db.why_reasons.rows.append(base._reason(wq.PUBLISHED))          # side: opponent
        assert base._known(db, opponent=True)["engine"] == "studied"
        assert base._known(db, opponent=False) is None                  # live engine runs instead
        out = base._ask(db, base._nothing(), opponent=False)
        assert out["found"] is False and "study" not in out and "Qg6" not in str(out)


class TestTheArrows:
    def test_the_card_draws_the_why_box_arrows(self):
        arrows = wq.card_arrows_from_study(base._reason(wq.PUBLISHED))
        assert arrows == [{"from": "g6", "to": "g2", "color": "blue", "teach": True}]


class TestTheRerender:
    def _seed(self, status):
        db = _DB()
        base._ask(db, base._nothing())                                  # asker g1
        base._ask(db, base._nothing(), game_id="g2")                    # asker g2
        db.why_reasons.rows.append(base._reason(status))
        for gid in ("g1", "g2", "g3"):
            db.game_analyses.rows.append({"game_id": gid, "decryption_v5_version": 243})
        return db

    def _versions(self, db):
        return {r["game_id"]: r["decryption_v5_version"] for r in db.game_analyses.rows}

    def test_agree_re_renders_only_the_games_that_asked(self):
        db = self._seed(wq.HELD_FOR_REVIEW)
        key = wq.position_key(base.FEN, "b3")
        assert base._run(wq.apply_ruling(db, key, "agree", ruled_by="t")) == wq.PUBLISHED
        assert self._versions(db) == {"g1": 0, "g2": 0, "g3": 243}

    def test_withdrawing_a_published_study_re_renders_too(self):
        db = self._seed(wq.PUBLISHED)
        key = wq.position_key(base.FEN, "b3")
        assert base._run(wq.apply_ruling(db, key, "disagree", ruled_by="t")) == wq.REJECTED
        assert self._versions(db)["g1"] == 0

    def test_a_ruling_that_never_touches_a_card_re_renders_nothing(self):
        db = self._seed(wq.HELD_FOR_REVIEW)
        key = wq.position_key(base.FEN, "b3")
        base._run(wq.apply_ruling(db, key, "disagree", ruled_by="t"))
        assert self._versions(db) == {"g1": 243, "g2": 243, "g3": 243}


class TestPublishedStudiesRead:
    def test_only_published_rows_with_text(self):
        db = _DB()
        db.why_reasons.rows += [base._reason(wq.PUBLISHED),
                                base._reason(wq.HELD_FOR_REVIEW, key="k2"),
                                base._reason(wq.PUBLISHED, key="k3", reason="  ")]
        got = base._run(wq.published_studies_by_key(db))
        assert list(got) == [wq.position_key(base.FEN, "b3")]

    def test_no_db_is_no_studies(self):
        assert base._run(wq.published_studies_by_key(None)) == {}
