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
        yield text[max(0, m.start() - 1200): m.end() + 600]


def test_each_lichess_game_fetch_asks_for_clocks():
    for rel in CALL_SITES:
        text = (BACKEND / rel).read_text(encoding="utf-8")
        windows = list(_windows_after_the_lichess_url(text))
        assert windows, f"{rel}: no lichess games fetch found, update CALL_SITES"
        for w in windows:
            assert re.search(r"[\"']clocks[\"']\s*:\s*[\"']?true", w, re.I), (
                f"{rel}: a lichess games fetch does not send clocks=true")


def test_no_other_file_fetches_lichess_user_games_unchecked():
    found = set()
    for p in BACKEND.rglob("*.py"):
        if "tests" in p.parts or "scripts" in p.parts:
            continue
        if "lichess.org/api/games/user" in p.read_text(encoding="utf-8", errors="ignore"):
            found.add(p.relative_to(BACKEND).as_posix())
    assert found <= set(CALL_SITES), f"new lichess fetch sites to check: {found - set(CALL_SITES)}"
