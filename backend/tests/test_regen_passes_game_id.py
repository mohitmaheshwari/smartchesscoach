"""The corpus re-render must not discard authored captions.

`generate_game_decryption_v5` looks up `authored_caption_overrides` by game_id
and, when game_id is None, logs:

    [v5_decryption] game_id=None -- authored_caption_overrides lookup will be
    silently skipped for every move in this game. Production callers should
    pass game_id; only audit/probe scripts should accept the override-skip.

`scripts/regen_v5_decryption.py` rewrites decryption_v5_data for EVERY analyzed
game, so omitting game_id there means a full run overwrites every authored
caption with generated text. There are 190 of them across 29 games, and they
are hand-written coaching prose -- "the whole point of gambiting the f pawn was
to push the e pawn, but black misses it" -- not something the generator can
reproduce.

Measured on the same 10 games, with and without the argument: 7-better /
9-worse becomes 12-better / 5-worse. That one keyword is the difference between
a re-render that improves the corpus and one that damages it.

This test reads the call site out of the AST rather than running the script, so
it needs no DB and no engine.
"""
from __future__ import annotations

import ast
import os

_SCRIPT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "scripts",
    "regen_v5_decryption.py",
)


def _generator_calls(tree: ast.AST) -> list[ast.Call]:
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        name = getattr(fn, "id", None) or getattr(fn, "attr", None)
        if name == "generate_game_decryption_v5":
            found.append(node)
    return found


def test_regen_script_calls_the_generator_exactly_once():
    tree = ast.parse(open(_SCRIPT, encoding="utf-8").read())
    calls = _generator_calls(tree)
    assert len(calls) == 1, f"expected one call site, found {len(calls)}"


def test_regen_script_passes_game_id():
    """The guard. Without this the run silently destroys authored captions."""
    tree = ast.parse(open(_SCRIPT, encoding="utf-8").read())
    call = _generator_calls(tree)[0]
    kwargs = {kw.arg for kw in call.keywords if kw.arg}
    assert "game_id" in kwargs, (
        "regen_v5_decryption.py must pass game_id to "
        "generate_game_decryption_v5, or a full run overwrites all 190 "
        "authored_caption_overrides with generated text"
    )


def test_game_id_is_not_passed_as_a_literal_none():
    """`game_id=None` would satisfy the keyword check and still skip lookups."""
    tree = ast.parse(open(_SCRIPT, encoding="utf-8").read())
    call = _generator_calls(tree)[0]
    for kw in call.keywords:
        if kw.arg == "game_id":
            assert not (isinstance(kw.value, ast.Constant) and kw.value.value is None), (
                "game_id is passed but hardcoded to None"
            )
