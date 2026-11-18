"""Every lichess game fetch must ask for clocks.

Lichess leaves [%clk] out of the PGN unless `clocks=true` is sent (verified
2026-11-09 on one game: 0 clock tags without, 52 with). The background sync
asked; the manual import, which onboarding uses, did not, and 577 lichess games
were stored with no think-time. This scans each call site that fetches a user's
lichess games and checks the request asks for clocks.
"""
import re
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
CALL_SITES = ["routes/analysis.py", "journey_service.py"]


def _windows_after_the_lichess_url(text: str):
    for m in re.finditer(r"lichess\.org/api/games/user", text):
        # Wide on purpose. The params dict can sit either side of the URL and
        # each flag carries a comment saying why it is there, so a tight
        # window starts failing as soon as someone documents a flag -- which
        # is exactly what happened on 2026-11-18. Each of these files holds a
        # single lichess fetch (the test below keeps it that way), so a wide
        # window cannot pick up a different call's flags.
        yield text[max(0, m.start() - 4000): m.end() + 2000]


def test_each_lichess_game_fetch_asks_for_clocks():
    for rel in CALL_SITES:
        text = (BACKEND / rel).read_text(encoding="utf-8")
        windows = list(_windows_after_the_lichess_url(text))
        assert windows, f"{rel}: no lichess games fetch found, update CALL_SITES"
        for w in windows:
            assert re.search(r"[\"']clocks[\"']\s*:\s*[\"']?true", w, re.I), (
                f"{rel}: a lichess games fetch does not send clocks=true")


def test_each_lichess_game_fetch_asks_for_the_opening():
    """Same fault as clocks, found 2026-11-18.

    Lichess sends no [Opening]/[ECO] header unless `opening=true` is asked
    for (verified against the live API: without it the PGN carries neither,
    with it both appear). Measured on production: 0 of 2,013 lichess games
    had an opening name, against 21,846 of 22,274 chess.com games. Engine 2
    records exactly one signal from a finished game -- opening exposure --
    so a lichess-only player recorded no skill attempt at all.
    """
    for rel in CALL_SITES:
        text = (BACKEND / rel).read_text(encoding="utf-8")
        windows = list(_windows_after_the_lichess_url(text))
        assert windows, f"{rel}: no lichess games fetch found, update CALL_SITES"
        for w in windows:
            assert re.search(r"[\"']opening[\"']\s*:\s*[\"']?true", w, re.I), (
                f"{rel}: a lichess games fetch does not send opening=true")


def test_no_other_file_fetches_lichess_user_games_unchecked():
    found = set()
    for p in BACKEND.rglob("*.py"):
        if "tests" in p.parts or "scripts" in p.parts:
            continue
        if "lichess.org/api/games/user" in p.read_text(encoding="utf-8", errors="ignore"):
            found.add(p.relative_to(BACKEND).as_posix())
    assert found <= set(CALL_SITES), f"new lichess fetch sites to check: {found - set(CALL_SITES)}"
