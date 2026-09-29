"""The scorer must find a real signal AND fail to find a fake one.

A scoring script that only ever gets run once, on data that took a person three
hours to produce, has to be right the first time. So it is shown four coaches
whose answers we already know the truth about:

    a coach who agrees      -> high confirmed, p below 0.05
    a coach answering at random -> p above 0.05, whatever the raw rate looks like
    a coach who says "cannot tell" -> everything NOT SEEN, nothing contradicted
    a coach who says the opposite  -> everything CONTRADICTED

The second is the one that matters. A permutation test that cannot fail to
reject is not a test, and "the coach agreed with us" is worthless unless the
same machinery would have said so when they did not.
"""
from __future__ import annotations

import csv
import importlib.util
import re
import json
import random
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "score_blind_labels", BACKEND / "scripts" / "score_blind_labels.py")
score = importlib.util.module_from_spec(_spec)
sys.modules["score_blind_labels"] = score
_spec.loader.exec_module(score)

TRAITS = ["clock_front_loaded", "knowledge_breadth", "moves_fast",
          "plays_on_when_lost", "thinks_long", "throws_away_won_games"]
COLUMNS = TRAITS + ["tactical_misses"]


def build_key(n_players=12, seed=1):
    """A key shaped like a real one: most traits silent, a few spoken."""
    rng = random.Random(seed)
    entries = {}
    for i in range(1, n_players + 1):
        label = "P%02d" % i
        ours = {}
        # Three spoken traits per player, the rest in the middle -- close to
        # what the real packet carries.
        spoken = rng.sample(TRAITS, 3)
        for trait in TRAITS:
            ours[trait] = rng.choice(["A", "B"]) if trait in spoken else "-"
        ours["tactical_misses"] = rng.choice(["A", "B", "C"])
        entries[label] = {"user_id": "user_%02d" % i, "ours": ours,
                          "layer": None, "balanced": False}
    return {"repeat_pairs": [["P01", "P02"]], "entries": entries}


def write_form(path: Path, key, answer):
    """`answer(label, column, ours) -> letter`."""
    with path.open("w", newline="", encoding="utf-8") as fh:
        fh.write("# a comment line the reader must skip\n")
        writer = csv.writer(fh)
        writer.writerow(["player"] + COLUMNS + ["confidence_1_to_5", "notes"])
        for label, entry in key["entries"].items():
            writer.writerow(
                [label] + [answer(label, c, entry["ours"][c]) for c in COLUMNS]
                + ["3", ""])


def run(tmp_path, key, answer, monkeypatch, capsys):
    key_path = tmp_path / "key.json"
    key_path.write_text(json.dumps(key), encoding="utf-8")
    form_path = tmp_path / "form.csv"
    write_form(form_path, key, answer)
    monkeypatch.setattr(sys, "argv",
                        ["score", "--form", str(form_path), "--key", str(key_path)])
    score.main()
    return capsys.readouterr().out


def spoken_counts(out):
    """(confirmed, not_seen, contradicted, total) off the summary line."""
    line = [l for l in out.splitlines() if l.strip().startswith("behaviour traits")]
    assert line, "no behaviour-trait summary line was printed\n" + out
    # Pick the count/total pairs off the line rather than fixed word offsets,
    # so renaming the label cannot silently read the wrong columns.
    pairs = [tuple(int(x) for x in m.split("/"))
             for m in re.findall(r"\d+/\d+", line[0])]
    assert len(pairs) == 3, "expected three count/total pairs: " + line[0]
    return pairs[0][0], pairs[1][0], pairs[2][0], pairs[0][1]


def p_value_of(out):
    line = [l for l in out.splitlines() if "p = " in l]
    assert line, "no permutation result was printed\n" + out
    return float(line[0].split("p = ")[1].split(")")[0])


def test_a_coach_who_agrees_is_found(tmp_path, monkeypatch, capsys):
    out = run(tmp_path, build_key(), lambda l, c, ours: ours, monkeypatch, capsys)
    confirmed, not_seen, contradicted, total = spoken_counts(out)
    assert total > 0, "nothing was scored, so the test proves nothing"
    assert confirmed == total
    assert (not_seen, contradicted) == (0, 0)
    assert "Where the coach said the opposite" not in out
    assert p_value_of(out) < 0.05, out
    assert "Better than the same answers on the wrong players." in out


def test_a_coach_answering_at_random_is_not_found(tmp_path, monkeypatch, capsys):
    """THE CONTROL THAT MATTERS.

    Without this the permutation test could be rejecting everything, and a real
    coach's agreement would mean nothing.
    """
    rng = random.Random(7)
    out = run(tmp_path, build_key(),
              lambda l, c, ours: rng.choice(["A", "B", "-", "?"]),
              monkeypatch, capsys)
    p_line = [l for l in out.splitlines() if "p = " in l][0]
    p_value = float(p_line.split("p = ")[1].split(")")[0])
    assert p_value > 0.05, "a random coach was declared better than chance\n" + out
    assert "NOT DISTINGUISHABLE FROM CHANCE" in out


def test_cannot_tell_is_not_counted_against_us(tmp_path, monkeypatch, capsys):
    out = run(tmp_path, build_key(), lambda l, c, ours: "?", monkeypatch, capsys)
    assert "Where the coach said the opposite" not in out, out
    confirmed, not_seen, contradicted, total = spoken_counts(out)
    assert total > 0
    assert (confirmed, contradicted) == (0, 0)
    assert not_seen == total


def test_a_coach_who_says_the_opposite_is_reported(tmp_path, monkeypatch, capsys):
    flip = {"A": "B", "B": "A", "C": "A"}
    out = run(tmp_path, build_key(),
              lambda l, c, ours: flip.get(ours, "?"), monkeypatch, capsys)
    assert "Where the coach said the opposite" in out
    confirmed, _, contradicted, total = spoken_counts(out)
    assert confirmed == 0
    assert contradicted == total


def test_the_repeat_control_is_printed_before_anything_else(tmp_path,
                                                            monkeypatch, capsys):
    """It bounds every other number, so it must not be buried below them."""
    out = run(tmp_path, build_key(), lambda l, c, ours: ours, monkeypatch, capsys)
    assert out.index("THE COACH AGAINST THEMSELVES") < \
        out.index("THE CLAIMS WE WOULD SHOW A PLAYER")


def test_an_inconsistent_coach_is_flagged_as_uninterpretable(tmp_path,
                                                             monkeypatch, capsys):
    rng = random.Random(3)

    def answer(label, column, ours):
        # P01 and P02 are the repeat pair; answer them independently at random
        # so the coach disagrees with themselves.
        if label in ("P01", "P02"):
            return rng.choice(["A", "B"])
        return ours

    out = run(tmp_path, build_key(), answer, monkeypatch, capsys)
    assert "self-agreement:" in out
    assert ("THIS IS LOW" in out) or ("Moderate" in out), out


def test_silent_traits_are_never_scored(tmp_path, monkeypatch, capsys):
    """We never render a middle-half trait, so agreeing about it is not a win.

    A coach who nails every '-' and nothing else must score nothing at all.
    """
    out = run(tmp_path, build_key(),
              lambda l, c, ours: "-" if ours == "-" else "?",
              monkeypatch, capsys)
    confirmed, not_seen, contradicted, total = spoken_counts(out)
    assert total > 0, "nothing was scored at all, so the test proves nothing"
    assert confirmed == 0, "agreeing about silence was counted as a hit\n" + out
    assert (not_seen, contradicted) == (total, 0)


def test_unreadable_answers_are_reported_not_guessed(tmp_path, monkeypatch, capsys):
    out = run(tmp_path, build_key(),
              lambda l, c, ours: "maybe" if l == "P03" else ours,
              monkeypatch, capsys)
    assert "UNREADABLE ANSWERS" in out
    assert "'MAYBE'" in out.upper()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
