"""
Opening Theory Walker
=====================

Walks a user's played move sequence against our curated opening theory
tree (`data/opening_curriculum.json`). Returns a per-ply record telling
us exactly when the user (or the opponent) left book, and — at the
deviation point — what the theory move would have been plus the coach
teaching text we've already written for that node.

This is the authoritative "in-book vs out-of-book" check. It replaces
the move-number heuristic, which was too blunt: "move 8" means
different things in Giuoco Pianissimo vs Evans Gambit.

Contract:
- Deterministic. No LLM, no heuristics. If the tree doesn't cover it,
  we say so honestly ("book ends here") rather than invent.
- Pairs cleanly with Stockfish's cp_loss — a "real" opening mistake is
  BOTH off-theory AND flagged by the engine as materially worse.
"""

from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

_CURRICULUM_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "opening_curriculum.json",
)


@lru_cache(maxsize=1)
def _load_curriculum() -> Dict[str, Any]:
    try:
        with open(_CURRICULUM_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"could not load curriculum: {e}")
        return {}


def get_opening_curriculum(opening_key: str) -> Optional[Dict[str, Any]]:
    """Return the raw curriculum entry (tree + summary + golden_rules)
    for an opening_key. Returns None when missing."""
    if not opening_key:
        return None
    return _load_curriculum().get(opening_key)


def _san_norm(s: Optional[str]) -> str:
    if not s:
        return ""
    return s.replace("+", "").replace("#", "").replace("!", "").replace("?", "").strip()


def walk_opening_theory(
    opening_key: str,
    san_history: List[str],
) -> List[Dict[str, Any]]:
    """Walk `san_history` against the opening tree for `opening_key`.

    Returns a list of per-ply records:
        {
          "ply": int,              # 0-indexed; even=white, odd=black
          "side": "white"|"black",
          "played": str,           # the SAN actually played
          "expected": str|None,    # what theory wanted (None when no guidance)
          "in_theory": bool,       # did `played` match theory at this ply?
          "guidance": dict,        # node-level teaching fields from JSON
        }

    Walk stops at the FIRST deviation (either side). Records before the
    deviation are all `in_theory: True`. The deviation record has
    `in_theory: False` and carries the richest guidance available.
    """
    curriculum = get_opening_curriculum(opening_key)
    if not curriculum or not san_history:
        return []
    tree = curriculum.get("tree") or {}
    if not tree:
        return []

    out: List[Dict[str, Any]] = []
    # Ply 0 = white's first move. Theory's root keys are white-move SANs.
    played_0 = _san_norm(san_history[0])
    # Build case-insensitive match against tree keys.
    tree_keys_norm = { _san_norm(k): k for k in tree.keys() }
    first_key = tree_keys_norm.get(played_0)
    if first_key is None:
        expected_white = next(iter(tree.keys()), None)
        out.append({
            "ply": 0,
            "side": "white",
            "played": san_history[0],
            "expected": expected_white,
            "in_theory": False,
            "guidance": {
                "summary": curriculum.get("summary"),
            },
        })
        return out

    root_node = tree[first_key]
    out.append({
        "ply": 0,
        "side": "white",
        "played": san_history[0],
        "expected": first_key,
        "in_theory": True,
        "guidance": {
            "idea": root_node.get("idea"),
            "right_feedback": root_node.get("right_feedback"),
        },
    })

    # `current_node` holds the context for the NEXT pair: the .responses
    # dict defines valid opponent (black) replies, and each opp node's
    # .next defines the expected white follow-up. So after white's move:
    #   current_node = the white-move node
    # After black's reply lands in .responses:
    #   current_node = black-reply node (has .next for white, .responses for black's next)
    current_node = root_node

    for i in range(1, len(san_history)):
        played = san_history[i]
        played_n = _san_norm(played)
        is_white_ply = (i % 2 == 0)
        side = "white" if is_white_ply else "black"

        if not is_white_ply:
            # Black reply. Match in current_node.responses.
            responses = current_node.get("responses") or {}
            resp_keys_norm = { _san_norm(k): k for k in responses.keys() }
            match = resp_keys_norm.get(played_n)
            if match is None:
                expected_black = next(iter(responses.keys()), None)
                out.append({
                    "ply": i,
                    "side": "black",
                    "played": played,
                    "expected": expected_black,
                    "in_theory": False,
                    "guidance": {
                        "idea": current_node.get("idea"),
                    },
                })
                return out
            opp_node = responses[match]
            out.append({
                "ply": i,
                "side": "black",
                "played": played,
                "expected": match,
                "in_theory": True,
                "guidance": {
                    "name": opp_node.get("name"),
                    "idea_opponent": opp_node.get("idea_opponent"),
                },
            })
            current_node = opp_node
        else:
            # White follow-up. Expected = current_node.next
            expected = current_node.get("next")
            if not expected:
                # Our tree runs out of guidance here — we simply don't
                # know what theory wants. This is NOT a deviation; it's
                # honest end-of-book. Stop walking.
                return out
            expected_n = _san_norm(expected)
            if played_n == expected_n:
                out.append({
                    "ply": i,
                    "side": "white",
                    "played": played,
                    "expected": expected,
                    "in_theory": True,
                    "guidance": {
                        "right_feedback": current_node.get("right_feedback"),
                        "hint": current_node.get("hint"),
                    },
                })
                # current_node stays — .responses still holds black's next.
            else:
                out.append({
                    "ply": i,
                    "side": "white",
                    "played": played,
                    "expected": expected,
                    "in_theory": False,
                    "guidance": {
                        "right_feedback": current_node.get("right_feedback"),
                        "hint": current_node.get("hint"),
                        "wrong_feedback": current_node.get("wrong_feedback"),
                        "name": current_node.get("name"),
                    },
                })
                return out

    return out


def build_mistake_commentary(
    opening_key: str,
    ply_record: Dict[str, Any],
    played_san: str,
) -> Dict[str, Any]:
    """Build coach-voice commentary for a theory deviation. Pulls the
    *expected* move, the right_feedback text the JSON already has (which
    explains why the theory move is good), and a principle from
    golden_rules. No LLM, no invention.
    """
    curriculum = get_opening_curriculum(opening_key) or {}
    opening_name = curriculum.get("name") or "this opening"
    summary = curriculum.get("summary") or ""
    golden_rules = curriculum.get("golden_rules") or []

    guidance = (ply_record or {}).get("guidance") or {}
    expected = (ply_record or {}).get("expected")
    right_fb = guidance.get("right_feedback") or ""
    hint = guidance.get("hint") or ""
    wrong_fb = guidance.get("wrong_feedback") or ""
    idea = guidance.get("idea") or guidance.get("idea_opponent") or ""

    # Headline: what the book wanted.
    if expected and right_fb:
        # right_feedback is typically written as "Nf3 — develops AND attacks e5..."
        # Keep it as-is; it already names the move.
        book_line = f"Book here is {expected}. {right_fb}"
    elif expected:
        book_line = f"Book here is {expected}."
    elif right_fb:
        book_line = right_fb
    else:
        book_line = ""

    # Principle: draw one golden rule if we have any.
    principle = None
    if golden_rules:
        # Pick a rule that mentions a square/piece in the context, else first.
        picked = None
        if expected:
            for r in golden_rules:
                if any(tok and tok in r for tok in [expected, played_san]):
                    picked = r
                    break
        principle = picked or golden_rules[0]

    return {
        "opening_name": opening_name,
        "summary": summary,
        "book_move": expected,
        "book_line": book_line.strip(),
        "why_your_move_falls_short": wrong_fb or hint or "",
        "principle": principle,
    }
