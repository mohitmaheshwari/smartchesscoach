from __future__ import annotations

import json
from pathlib import Path

from services.caption_principles import PRINCIPLES


ARTIFACT = Path(__file__).parents[1] / "data" / "positional_caption_candidates.json"


def _records():
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))["records"]


def test_generated_artifact_has_requested_position_split():
    records = _records()
    assert len(records) == 240
    assert sum(row["disposition"] == "eligible_positional" for row in records) == 199
    assert sum(row["disposition"] == "already_decided" for row in records) == 17
    assert sum(row["disposition"] == "not_mistake" for row in records) == 24


def test_all_199_caption_targets_pass_local_proof_but_have_no_runtime_authority():
    targets = [row for row in _records() if row["disposition"] == "eligible_positional"]
    assert len(targets) == 199
    for row in targets:
        assert row["verification"]["status"] == "pass"
        assert row["verification"]["deterministic_issues"] == []
        assert row["final"]["caption"]
        assert row["final"]["better_move_fact"]
        assert row["final"]["played_move_fact"]
        assert row["final"]["contrast"]
        assert row["final"]["transferable_lesson"]
        assert row["caption_eligible"] is False
        assert row["tracker_eligible"] is False


def test_generated_canonical_concepts_use_the_single_registry():
    known = {row["id"] for row in PRINCIPLES}
    used = {
        row["final"]["canonical_concept_id"]
        for row in _records()
        if row["final"].get("canonical_concept_id")
    }
    assert used <= known
