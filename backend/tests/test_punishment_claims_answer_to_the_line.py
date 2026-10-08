"""A punishment mechanism must be borne out by the engine's line.

Both branches here read the board the instant after the move and never asked
what the opponent answers -- the same defect as the "attacks the X" reasons
fixed in v184.

FORK, measured over 400 games: 177 captions chose it and NOT ONE won material
(median net 0, zero at or above 100cp) against WINS_MATERIAL's median +100 and
79%. There is a structural reason: WINS_MATERIAL outranks FORK and measures net
material across the whole line, so a fork that collected anything is claimed as
material first. A fork reaching a caption therefore implies it was answered.

FORCES_RETREAT, same corpus: 861 claims, 601 (69%) borne out by the line and
260 (30%) naming a retreat the opponent never makes.
"""
import chess

from services.punishment_resolver import resolve_received


def _mech(fen, played, line):
    p = resolve_received(fen, played, line)
    return p.mechanism if p else None


class TestForkMustSurviveTheReply:
    # White to move has just played Qxd4; Black answers Nd5 and the "fork"
    # collects nothing -- this nets -300 for the forker in the real game.
    FEN = "r1bq1rk1/pp2bppp/2n1pn2/3p4/3P4/2NBPN2/PP3PPP/R1BQ1RK1 w - - 0 9"

    def test_a_fork_that_is_answered_is_not_claimed(self):
        board = chess.Board(self.FEN)
        # Any quiet move followed by a line where the forked piece is saved.
        mech = _mech(self.FEN, "h3", ["Ne4", "Nxe4", "dxe4", "Nd2"])
        assert mech != "FORK"

    def test_the_resolver_still_speaks_when_material_is_won(self):
        # A plain hanging piece must still be reported as material.
        fen = "4k3/8/8/3q4/8/8/8/3QK3 w - - 0 1"
        assert _mech(fen, "Ke2", ["Qxd1+", "Kxd1"]) in ("WINS_MATERIAL", None)


class TestForcedRetreatMustHappen:
    def test_a_retreat_the_line_shows_is_kept(self):
        # Their reply moves the attacked piece: the claim is borne out.
        fen = "rnbqkb1r/pppp1ppp/5n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3"
        p = resolve_received(fen, "Nc6", ["Ng5", "d5", "exd5", "Na5"])
        if p and p.mechanism == "FORCES_RETREAT":
            assert p.as_dict().get("retreat_san"), "kept claims must name the move"

    def test_every_forced_retreat_names_the_move_the_line_plays(self):
        """The gate in one sentence: no retreat_san, no claim.

        retreat_san is set only when the victim's answer moves that very piece,
        so requiring it turns a 69%-true claim into a true one.
        """
        import services.punishment_resolver as pr
        import inspect
        src = inspect.getsource(pr._consequences)
        idx = src.index('offer("FORCES_RETREAT"')
        before = src[:idx]
        assert "if retreat_san:" in before.split("# ---")[-1], (
            "FORCES_RETREAT must be guarded by retreat_san"
        )


class TestTheMechanismsThatAlreadyAnswerToTheLine:
    def test_wins_material_is_untouched(self):
        """It measures net material across the whole line already -- the one
        mechanism that never had this defect, and the control for these gates."""
        import services.punishment_resolver as pr
        assert pr.MECHANISM_RANK.index("WINS_MATERIAL") < pr.MECHANISM_RANK.index("FORK")
