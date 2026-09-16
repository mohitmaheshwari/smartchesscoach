import ast
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ROUTE = BACKEND / "routes" / "coach_play.py"
SESSION = BACKEND / "coach_play" / "coach_game_session.py"


def _evaluate_pending_source() -> str:
    source = ROUTE.read_text(encoding="utf-8")
    start = source.index("async def evaluate_pending_move")
    end = source.index("\n@router.", start)
    return source[start:end]


def test_route_remains_valid_python_and_persists_shadow_out_of_band():
    source = ROUTE.read_text(encoding="utf-8")
    ast.parse(source)
    body = _evaluate_pending_source()
    assert '"pwc_v2_shadow_enabled": 1' in body
    assert "build_shadow_packet_from_unified_response" in body
    assert '{"pwc_v2_shadow": v2_shadow_packet}' in body
    assert "return unified_response" in body


def test_route_never_decorates_the_public_unified_response_with_shadow():
    body = _evaluate_pending_source()
    forbidden = (
        'unified_response["pwc_v2_shadow"]',
        "unified_response['pwc_v2_shadow']",
        'unified_response.update({"pwc_v2_shadow"',
    )
    assert all(fragment not in body for fragment in forbidden)
    assert "except Exception as shadow_exc" in body


def test_shadow_rollout_metadata_is_not_returned_to_the_browser():
    session_source = SESSION.read_text(encoding="utf-8")
    ast.parse(session_source)
    assert 'visible.pop("pwc_v2_shadow_enabled", None)' in session_source
    assert 'if key != "pwc_v2_shadow"' in session_source
    assert session_source.count('"session": session.to_public_dict()') == 4

    route_source = ROUTE.read_text(encoding="utf-8")
    assert "session_dict = session.to_public_dict()" in route_source
    assert (
        route_source.count(
            "sessions = [public_session_document(session) for session in sessions]"
        )
        == 2
    )
    export_start = route_source.index("async def export_session")
    export_end = route_source.index("\n@router.", export_start)
    export_source = route_source[export_start:export_end]
    assert '"user_id": user.user_id' in export_source
    assert "session = public_session_document(session)" in export_source

    reviewer_export_start = route_source.index("async def export_coach_session_bundle")
    reviewer_export_end = route_source.index("\n@router.", reviewer_export_start)
    reviewer_export = route_source[reviewer_export_start:reviewer_export_end]
    assert "if not is_reviewer:" in reviewer_export
    assert "session = public_session_document(session)" in reviewer_export
