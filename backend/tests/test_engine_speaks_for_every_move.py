"""The engine emits something for every move, and keeps what it computes.

Mohit, 2026-10-22:

    "when you say engine is ready, it should not throw in silent moves,
     engine should give us something for everything, are you getting me?"

and, in the same session:

    "arrows and all were building excellent, so no code changes there
     please, i was very happy with that please"

Both constraints at once, which is what shapes these tests.

WHAT WAS WRONG. Measured over 8,831 stored move evaluations:

    good moves (cp_loss < 50)   6,160   91.8% carry NO line at all
    small (50-99)               1,014   32.1%
    flagged (100+)              1,657    7.1%

Good moves are 70% of a game, so the engine was silent about most of what a
player did -- including everything they got right. It was never a search
cost: eval_after is stored on 100% of moves, so the search ran every time and
`evaluate_position` threw the principal variation away.

Separately, `opp_replies` and `opp_reply_is_clear` were computed by the
analysis and dropped by `_serialize_move`. Present on 0.0% of stored moves in
every era -- May, June, September and October.

THE SHAPE OF THE FIX. The floor line is stored under its OWN key,
`eval_line_played`, and never merged into `pv_after_played`. That field feeds
the arrow builder and the caption layer, both of which are working and must
not move. A new key means a new fact reaches the fact layer while every
existing consumer sees exactly what it saw before.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import chess  # noqa: E402

from stockfish_service import MoveEvaluation  # noqa: E402


class TestTheFieldsExist:
    def test_move_evaluation_carries_the_floor_line(self):
        m = MoveEvaluation(
            move_number=1, move_san="e4", move_uci="e2e4", player="white",
            fen_before=chess.STARTING_FEN, eval_before=0, eval_after=0,
            cp_loss=0, classification="best", best_move_san="e4",
            best_move_uci="e2e4", is_mate_before=False, is_mate_after=False,
            mate_in_before=None, mate_in_after=None)
        assert hasattr(m, "eval_line_played")

    def test_it_is_separate_from_the_punishment_line(self):
        """They must not be the same field. pv_after_played is the
        punishment line at PUNISHMENT_DEPTH for faulted moves and feeds the
        arrows; eval_line_played is the floor from the evaluation search."""
        m = MoveEvaluation(
            move_number=1, move_san="e4", move_uci="e2e4", player="white",
            fen_before=chess.STARTING_FEN, eval_before=0, eval_after=0,
            cp_loss=0, classification="best", best_move_san="e4",
            best_move_uci="e2e4", is_mate_before=False, is_mate_after=False,
            mate_in_before=None, mate_in_after=None,
            pv_after_played=["a", "b"], eval_line_played=["c", "d", "e"])
        assert m.pv_after_played == ["a", "b"]
        assert m.eval_line_played == ["c", "d", "e"]

    def test_the_reply_fields_exist(self):
        m = MoveEvaluation(
            move_number=1, move_san="e4", move_uci="e2e4", player="white",
            fen_before=chess.STARTING_FEN, eval_before=0, eval_after=0,
            cp_loss=0, classification="best", best_move_san="e4",
            best_move_uci="e2e4", is_mate_before=False, is_mate_after=False,
            mate_in_before=None, mate_in_after=None)
        assert hasattr(m, "opp_replies")
        assert hasattr(m, "opp_reply_is_clear")


class TestNothingIsDroppedOnTheWayToTheDatabase:
    """`_serialize_move` is where the fields were lost. It is a closure inside
    analyze_game_with_stockfish, so it is exercised through the source: the
    test asserts the keys are written, which is the thing that regressed."""

    def _serializer_source(self):
        src = Path(__file__).resolve().parents[1] / "stockfish_service.py"
        text = src.read_text(encoding="utf-8")
        start = text.index("def _serialize_move(")
        end = text.index("return {", start)
        end = text.index("\n            }", end)
        return text[start:end]

    def test_opp_replies_is_serialised(self):
        body = self._serializer_source()
        assert '"opp_replies": m.opp_replies' in body, (
            "computed by the analysis and dropped here -- 0.0% of stored "
            "moves had it, in every era")

    def test_opp_reply_is_clear_is_serialised(self):
        assert '"opp_reply_is_clear": m.opp_reply_is_clear' in \
            self._serializer_source()

    def test_the_floor_line_is_serialised(self):
        assert '"eval_line_played": m.eval_line_played' in \
            self._serializer_source()

    def test_both_sides_get_the_floor_line_not_just_the_user(self):
        """Serialising the field is not the same as SETTING it. The user
        path set it this morning and the opponent path did not, so across
        five re-analysed games 185 of 187 user moves carried a floor line
        and 0 of 84 opponent moves did -- while the serializer test above
        passed the whole time.

        2,075 of 11,959 faulted cards are opponent moves, and purposes_for
        has no line at all on them without this.
        """
        src = (Path(__file__).resolve().parents[1] / "stockfish_service.py")
        text = src.read_text(encoding="utf-8")
        n = text.count("eval_line_played=eval_line_played")
        assert n >= 2, (
            f"only {n} MoveEvaluation construction(s) pass the floor line; "
            f"both the user and the opponent path must")

    def test_the_punishment_line_still_maps_to_its_own_key(self):
        """The arrows read this. If the floor line were ever merged into it,
        every good-move card would gain arrows it never had and every
        faulted card could draw a different line."""
        body = self._serializer_source()
        assert '"pv_after_played": m.pv_after_played' in body
        assert '"pv_after_played": m.eval_line_played' not in body


class TestTheFloorSearchKeepsWhatItAlreadyFound:
    def test_evaluate_position_with_line_exists_and_is_additive(self):
        """Added beside evaluate_position rather than changing it: that one
        has 21 callers and none of them should have to care."""
        from stockfish_service import StockfishEngine
        assert hasattr(StockfishEngine, "evaluate_position_with_line")
        assert hasattr(StockfishEngine, "evaluate_position")

    def test_it_returns_three_things_not_two(self):
        import inspect
        from stockfish_service import StockfishEngine
        sig = inspect.signature(StockfishEngine.evaluate_position_with_line)
        assert "pv_length" in sig.parameters
        src = inspect.getsource(StockfishEngine.evaluate_position_with_line)
        # one analyse call, not two: the whole point is that it is free
        assert src.count("self.engine.analyse(") == 1, (
            "a second search would make the floor cost real engine time")


class TestAFinishedJobProvesItsWritesLanded:
    """2026-10-22: two of five games re-analysed together came back with
    stale move_evaluations and a decryption_v5_version from an earlier era
    -- 172 and 228 against the others' 230 -- no captions and no engine
    cards, while both queue rows read status=completed, last_error=None.
    Re-running either on the same code succeeded, so the writes were lost
    rather than the code being wrong.

    Every phase in process_job has its own try/except and several log a
    swallowed warning on a Mongo failure, so a lost write reports success
    and the review page keeps serving the previous analysis with nothing to
    say so. Reaching the end of the pipeline is not evidence that the
    pipeline's writes survived.
    """

    def _worker_source(self):
        src = Path(__file__).resolve().parents[1] / "analysis_worker.py"
        return src.read_text(encoding="utf-8")

    def test_it_rereads_the_document_before_declaring_success(self):
        body = self._worker_source()
        i = body.index("[SUCCESS] Analyzed game")
        # the verification has to come BEFORE the success line, not after
        head = body[:i]
        assert "[ANALYSIS NOT VERIFIED]" in head, (
            "a job may not report success without checking its writes "
            "landed")

    def test_it_checks_both_the_version_and_the_floor_line(self):
        """Either alone would have missed one of the two real cases: one
        game kept v228 and the other v172, and both lacked floor lines."""
        body = self._worker_source()
        i = body.index("[ANALYSIS NOT VERIFIED]")
        block = body[max(0, i - 2000):i + 2000]
        assert "decryption_v5_version" in block
        assert "eval_line_played" in block

    def test_it_marks_the_queue_row_rather_than_retrying(self):
        """A loud marker beats a retry loop on a genuinely odd game."""
        body = self._worker_source()
        assert "analysis_verified" in body

    def test_the_check_cannot_itself_fail_the_job(self):
        body = self._worker_source()
        i = body.index("[ANALYSIS NOT VERIFIED] check itself failed")
        assert "logger.warning" in body[max(0, i - 200):i + 200]


class TestAJobSaysWhoRanItAndWhatItWrote:
    """2026-10-23: one of five re-analysed games came back with 47 faulted
    moves and NO captions, while its queue row read plain success. Finding
    out which of two worker containers had run it was impossible, because
    `WORKER_ID` was `worker-{os.getpid()}` and inside a container the main
    process is PID 1 -- so every replica reported `worker-1`.

    That cost hours. The row now carries a worker id that distinguishes
    containers, and the caption outcome, so the same event answers itself.
    """

    def _src(self):
        p = Path(__file__).resolve().parents[1] / "analysis_worker.py"
        return p.read_text(encoding="utf-8")

    def test_the_worker_id_is_not_just_the_pid(self):
        src = self._src()
        assert 'WORKER_ID = f"worker-{os.getpid()}"' not in src, (
            "PID 1 in every container makes every worker look like the "
            "same one")
        assert "socket.gethostname()" in src

    def test_the_worker_id_distinguishes_two_containers(self):
        import importlib
        import sys as _s
        _s.path.insert(0, str(Path(__file__).resolve().parents[1]))
        w = importlib.import_module("analysis_worker")
        wid = w._worker_id()
        assert wid.startswith("worker-")
        # host AND pid, so two replicas on one host still differ
        assert wid.count("-") >= 2, wid

    def test_the_caption_outcome_lands_on_the_queue_row(self):
        src = self._src()
        for field in ("captions_written", "captions_refused",
                      "captions_neither", "captions_faulted_moves"):
            assert field in src, field

    def test_neither_is_counted_separately_from_refused(self):
        """A move with no caption and no refusal means the task raised and
        gather(return_exceptions=True) swallowed it -- a different fault
        from an honest refusal, and the one that hid for hours."""
        src = self._src()
        i = src.index("captions_neither")
        assert "_silent = len(_flagged) - _ok - _no" in src[:i]
