"""
Tests for opp_traded_active_detector (opp-failure V3, 2026-06-07).
Corpus-validated: 87 fires / 408 games, 0 misfires on 696 good opp moves.
"""
import chess
from services.opp_traded_active_detector import detect_opp_traded_active, clause_for


def _m(fen, san):
    b = chess.Board(fen)
    mv = next((x for x in b.legal_moves if b.san(x) == san), None)
    assert mv is not None, f"{san} illegal in {fen}"
    return b, mv


# Black (opponent) Bg4 captures Nf3; White recaptures gxf3 → a trade of an
# active, developed bishop, flagged as a mistake.
TRADE_FEN = "6k1/8/8/8/6b1/5N2/5PPP/3Q2K1 b - - 0 1"


def test_fires_on_active_trade():
    b, mv = _m(TRADE_FEN, "Bxf3")
    v3 = detect_opp_traded_active(b, mv, ["gxf3"], cp_loss=200)
    assert v3 is not None
    assert v3["piece"] == "bishop" and v3["square"] == "f3"
    assert "trades off their active bishop" in clause_for(v3)


def test_cp_loss_gate():
    b, mv = _m(TRADE_FEN, "Bxf3")
    assert detect_opp_traded_active(b, mv, ["gxf3"], cp_loss=80) is None   # not a real mistake


def test_requires_recapture_not_free_grab():
    # if the "next move" isn't a recapture on the captured square, it's not a trade
    b, mv = _m(TRADE_FEN, "Bxf3")
    assert detect_opp_traded_active(b, mv, ["Kg1f1"], cp_loss=200) is None


def test_non_capture_never_fires():
    b = chess.Board(chess.STARTING_FEN)
    mv = next(x for x in b.legal_moves if b.san(x) == "e4")
    assert detect_opp_traded_active(b, mv, ["e5"], cp_loss=300) is None


if __name__ == "__main__":
    test_fires_on_active_trade()
    test_cp_loss_gate()
    test_requires_recapture_not_free_grab()
    test_non_capture_never_fires()
    print("opp_traded_active_detector tests passed")
