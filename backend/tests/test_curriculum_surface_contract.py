"""Every surface the frontend asks for must be a surface the backend accepts.

On 2026-09-10 a HAR showed Play With Coach taking
`GET /coach/personal-curriculum?surface=play_with_coach -> 400 Unknown
curriculum surface` on every page load. The backend allowlist was
{None, "home", "learn", "progress"}; the frontend has used "play_with_coach"
in ten components since the surface was built. The client `.catch()`es the
failure, so PWC simply ran with no personal curriculum and nothing said so.

This enumerates the surfaces the frontend actually sends and requires the
backend to accept each one, so the two sides cannot drift apart in silence.
"""
import re
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
FRONTEND_SRC = BACKEND.parent / "frontend" / "src"
sys.path.insert(0, str(BACKEND))


def _frontend_surfaces() -> set:
    """Collect literal surface="..." props handed to curriculum components."""
    found = set()
    pattern = re.compile(r'surface=["\']([a-z_]+)["\']')
    for path in FRONTEND_SRC.rglob("*.jsx"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "Curriculum" not in text:
            continue
        found.update(pattern.findall(text))
    return found


def test_backend_accepts_every_surface_the_frontend_sends():
    from routes.coach import CURRICULUM_SURFACES

    sending = _frontend_surfaces()
    assert sending, "found no surface= props; the scan is broken, not the code"
    missing = sorted(s for s in sending if s not in CURRICULUM_SURFACES)
    assert not missing, (
        f"the frontend requests these curriculum surfaces but the backend "
        f"rejects them with 400: {missing}. Accepted: "
        f"{sorted(x for x in CURRICULUM_SURFACES if x)}"
    )


def test_play_with_coach_is_accepted():
    """The specific regression, pinned by name."""
    from routes.coach import CURRICULUM_SURFACES

    assert "play_with_coach" in CURRICULUM_SURFACES


def test_both_spellings_of_the_coach_play_surface_resolve():
    """focus_bridge calls it coach_play; the curriculum client calls it
    play_with_coach. Both name the same screen, so both must work."""
    from routes.coach import CURRICULUM_SURFACES
    from services.focus_bridge import COACHING_CONTEXT_SURFACES

    assert "coach_play" in COACHING_CONTEXT_SURFACES
    assert {"coach_play", "play_with_coach"} <= CURRICULUM_SURFACES


def test_default_none_surface_still_allowed():
    """Shared callers pass no surface at all; that must stay legal."""
    from routes.coach import CURRICULUM_SURFACES

    assert None in CURRICULUM_SURFACES
