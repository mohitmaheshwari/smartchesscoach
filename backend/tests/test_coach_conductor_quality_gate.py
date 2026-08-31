from __future__ import annotations

import services.concept_detectors.registry as detector_registry
import services.detector_quality as detector_quality
from services.coach_conductor import compute_endgame_thread


START_FEN = "8/8/8/8/8/8/4K3/6R1 w - - 0 1"


def test_endgame_caption_gate_blocks_before_detector_execution(monkeypatch):
    executed = []

    def forbidden_detector(*_args, **_kwargs):
        executed.append(True)
        return "applied"

    monkeypatch.setattr(detector_registry, "get_detector", lambda _skill: forbidden_detector)
    monkeypatch.setattr(detector_quality, "can_influence", lambda *_args, **_kwargs: False)

    result = compute_endgame_thread(
        fen_before=START_FEN,
        played_san="Rg2",
        user_is_white=True,
        threads_pulled=set(),
    )

    assert result is None
    assert executed == []


def test_endgame_caption_gate_uses_caption_surface(monkeypatch):
    checked = []

    def authorize(quality_id, surface):
        checked.append((quality_id, surface))
        return quality_id == "concept:endgame_lucena"

    monkeypatch.setattr(detector_quality, "can_influence", authorize)
    monkeypatch.setattr(
        detector_registry,
        "get_detector",
        lambda skill: (lambda *_args, **_kwargs: "applied") if skill == "endgame_lucena" else None,
    )

    result = compute_endgame_thread(
        fen_before=START_FEN,
        played_san="Rg2",
        user_is_white=True,
        threads_pulled=set(),
    )

    assert result is not None
    assert result["motif"] == "endgame_lucena"
    assert checked[0] == (
        "concept:endgame_lucena",
        detector_quality.QualitySurface.CAPTION,
    )
