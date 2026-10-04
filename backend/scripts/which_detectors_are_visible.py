"""Which detectors actually reach a screen, as opposed to being allowed to.

"Is it visible?" has two different answers and only one of them matters.

  AUTHORISED -- its grade in `detector_quality` permits it to surface. This is
  a line in a registry and it is what every previous answer to this question
  has reported.

  REACHING A PERSON -- it is present in something a user was actually served:
  the focus card on Home, or a teaching event in a game review.

The gap between the two is the whole subject. Measured 2026-10-04 on prod,
after a wire that was authorised, deployed, reported as shipped, and returned
null for every user because it sat below an early return.

A POSITIVE CONTROL IS PRINTED FIRST. If the probes cannot show at least one
detector reaching a screen, then a page of zeros means the probe is broken and
nothing can be concluded from it. Every false finding in this project came from
an unproven absence.
"""
from __future__ import annotations

import argparse
import asyncio
import collections
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

from services.detector_quality import _AUTHORIZATIONS  # noqa: E402


def by_grade():
    out = collections.defaultdict(list)
    for quality_id, auth in _AUTHORIZATIONS.items():
        out[str(getattr(auth, "grade", auth)).split(".")[-1]].append(quality_id)
    return out


def _root(quality_id: str) -> str:
    """The detector name inside a quality id like `gap:piece_safety:simple_hang`."""
    parts = str(quality_id).split(":")
    return parts[-1] if len(parts) > 1 and parts[-1] else str(quality_id)


async def main_async(days: int) -> int:
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[
        os.environ.get("DB_NAME", "chess_coach")]
    grades = by_grade()

    # ── what reached a focus card ──────────────────────────────────────
    focus_ids = collections.Counter()
    async for focus in db.user_active_focus.find(
            {"status": "active"},
            {"_id": 0, "detector_quality_id": 1, "topic_key": 1, "type": 1}):
        if focus.get("type") == "strength":
            continue
        if focus.get("detector_quality_id"):
            focus_ids[str(focus["detector_quality_id"])] += 1

    # ── what reached a game review ─────────────────────────────────────
    # `decryption_v5_data` is a FLAT LIST of move cards -- checked before
    # querying it, because the previous version of this probe assumed a dict
    # with a "moves" key and would have reported every detector as unseen.
    #
    # There is no `detector_quality_id` on a move card. A detector shows up
    # under whichever of these names its output travels as.
    IDENTITY_FIELDS = ("concept_id", "shape_pattern_id", "shape_pattern_name",
                       "principle_id_used", "rule_name", "teachable_event")
    review_ids = collections.Counter()
    seen_reviews = 0
    seen_cards = 0
    captioned_cards = 0
    async for doc in db.game_analyses.find(
            {"decryption_v5_data": {"$ne": None}},
            {"_id": 0, "decryption_v5_data": 1}).limit(4000):
        seen_reviews += 1
        cards = doc.get("decryption_v5_data") or []
        if not isinstance(cards, list):
            continue
        for move in cards:
            if not isinstance(move, dict):
                continue
            seen_cards += 1
            # A stored id on a card that renders no caption is not on a screen.
            if not str(move.get("caption") or "").strip():
                continue
            captioned_cards += 1
            for key in IDENTITY_FIELDS:
                value = move.get(key)
                if value and not isinstance(value, bool):
                    review_ids[str(value)] += 1

    reached = set(focus_ids) | set(review_ids)
    reached_roots = {_root(q) for q in reached}

    print("=" * 72)
    print("  POSITIVE CONTROL -- the probes must find something")
    print("=" * 72)
    print("  active focus cards carrying a detector id : %d" % sum(focus_ids.values()))
    print("  reviews scanned                           : %d" % seen_reviews)
    print("  move cards seen / with a caption          : %d / %d"
          % (seen_cards, captioned_cards))
    print("  distinct ids seen on a focus card         : %d" % len(focus_ids))
    print("  distinct ids seen in a review             : %d" % len(review_ids))
    if not reached:
        print("\n  CONTROL FAILED. The probes found nothing anywhere, so every")
        print("  zero below is a broken probe and not a finding. Stop here.")
        return 1
    print("  -> control passes; zeros below mean something")
    for quality_id, count in focus_ids.most_common(5):
        print("     e.g. focus: %-44s %d users" % (quality_id, count))
    for quality_id, count in review_ids.most_common(5):
        print("     e.g. review: %-43s %d moves" % (quality_id, count))

    print("\n" + "=" * 72)
    print("  BY GRADE: authorised to surface, against actually seen")
    print("=" * 72)
    for grade in ("PLAN", "CAPTION", "SHADOW", "DISABLED"):
        ids = sorted(grades.get(grade, ()))
        if not ids:
            continue
        hit = [q for q in ids if q in reached or _root(q) in reached_roots]
        print("\n  %-8s %2d entries, %d seen on a screen" % (grade, len(ids), len(hit)))
        for quality_id in ids:
            mark = ("SEEN" if (quality_id in reached
                               or _root(quality_id) in reached_roots) else "  --")
            print("     [%s] %s" % (mark, quality_id))

    total = len(_AUTHORIZATIONS)
    allowed = len(grades.get("PLAN", ())) + len(grades.get("CAPTION", ()))
    seen = len([q for q in _AUTHORIZATIONS
                if q in reached or _root(q) in reached_roots])
    print("\n" + "=" * 72)
    print("  %d detectors registered" % total)
    print("  %d authorised to surface (plan or caption)" % allowed)
    print("  %d actually seen on a focus card or in a review" % seen)
    print("=" * 72)
    print("""
  Authorised and not seen is the interesting column. It means the grade says
  yes and no user met it -- either nothing calls the detector, or what calls it
  never renders. That is not something a registry can tell you.""")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=0,
                        help="reserved; the stored focus and review are current")
    args = parser.parse_args()
    return asyncio.run(main_async(args.days))


if __name__ == "__main__":
    raise SystemExit(main())
