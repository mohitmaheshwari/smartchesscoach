#!/usr/bin/env python3
"""What is built, and what actually reaches a user?

Seven things were found in two days that were fully built and reached nobody:
the review arrows, the eval bar, the coaching timeline, the "Explain" button,
"Practice Now", 36 openings' worth of chapters, and the 5-puzzle concept test.
None raised an error. None failed a test. Every one of them RAN -- perfectly,
on nothing.

They share three mechanical shapes, and each is cheap to detect:

  ORPHAN COMPONENT  imported, never placed as <Component>  (eval bar, timeline)
  ORPHAN ENDPOINT   route registered, no frontend caller   (progress/journey)
  HOLLOW FIELD      key written on every doc, value always null (concept_id)
  UNREACHED CLAIM   graded in _AUTHORIZATIONS, no caption-path caller

The fourth was added 2026-09-25 after allowed_mate was found: 55 human
rulings, 55 of them true, a grade in the table -- and nothing on the
caption path has ever called it. The first three checks are all blind to
it. It is not an orphan component (it is backend), not an orphan endpoint
(no route), and not a hollow field (it writes nothing at all). It RAN
perfectly, for the admin review queue, on behalf of no user.

The first two are pure static analysis -- no DB, no engine, ~2 seconds. The
third needs data: --with-data walks the stored review cards and reports every
field that is written on every card and populated on none.

Validate it against the known cases rather than trusting it: CoachTimelinePanel
is dead today and MUST appear. EvalBar was dead until 2026-09-23 and must NOT.
A check that cannot find a bug we already know about is not a check.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
FRONTEND = ROOT / "frontend" / "src"
BACKEND = ROOT / "backend"

# Components that are deliberately not placed as JSX: entry points, routers,
# and things mounted by name. Keeping this list short and explicit is the
# point -- every entry is a claim that someone checked.
NOT_RENDERED_BY_DESIGN = {"App", "Layout", "reportWebVitals"}


class SourceUnavailable(RuntimeError):
    """The frontend tree is not here, so the static checks cannot run.

    This must RAISE, never return an empty list. Run inside the backend
    container the frontend does not exist, and an empty list made the report
    print "0 orphan components" -- a clean bill of health produced by looking
    at nothing. That is the same failure this whole script exists to catch,
    so it would be a poor joke to ship it inside the detector.
    """


def _jsx_files() -> list[Path]:
    if not FRONTEND.is_dir():
        raise SourceUnavailable(
            f"no frontend source at {FRONTEND} — run the static checks from a "
            f"repo checkout, not inside the backend container"
        )
    return [p for p in FRONTEND.rglob("*.jsx") if ".test." not in p.name] + \
           [p for p in FRONTEND.rglob("*.js") if ".test." not in p.name]


def orphan_components() -> list[tuple[str, str]]:
    """Imported somewhere, rendered nowhere."""
    files = _jsx_files()
    blobs = {p: p.read_text(encoding="utf-8", errors="ignore") for p in files}

    imported: dict[str, str] = {}
    for p, text in blobs.items():
        for m in re.finditer(
            r"^import\s+(\{[^}]+\}|[A-Z][A-Za-z0-9_]*)\s+from\s+[\"']([^\"']+)[\"']",
            text, re.M,
        ):
            names, src = m.group(1), m.group(2)
            if names.startswith("{"):
                parts = [n.strip().split(" as ")[-1].strip()
                         for n in names[1:-1].split(",")]
            else:
                parts = [names]
            # Only OUR components. Without this the report fills with
            # lucide-react icons, chess.js, Capacitor and lib constants --
            # none of which are ever written as <Tag>, all of which are fine.
            # A noisy map does not get read, and an unread map is the same as
            # no map.
            if not src.startswith("@/components/"):
                continue
            for n in parts:
                if n and n[0].isupper() and n not in NOT_RENDERED_BY_DESIGN:
                    imported.setdefault(n, f"{p.relative_to(ROOT)} <- {src}")

    all_text = "\n".join(blobs.values())
    orphans = []
    for name, where in sorted(imported.items()):
        if not re.search(rf"<{re.escape(name)}[\s/>]", all_text):
            orphans.append((name, where))
    return orphans


def orphan_endpoints() -> list[tuple[str, str]]:
    """Route registered on the server, nothing in the frontend calls it."""
    routes: list[tuple[str, str]] = []
    for py in (BACKEND / "routes").rglob("*.py"):
        text = py.read_text(encoding="utf-8", errors="ignore")
        for m in re.finditer(
            r"@router\.(get|post|put|patch|delete)\(\s*[\"']([^\"']+)[\"']", text
        ):
            path = m.group(2)
            if path in ("/", ""):
                continue
            routes.append((path, str(py.relative_to(ROOT))))

    frontend_text = "\n".join(
        p.read_text(encoding="utf-8", errors="ignore") for p in _jsx_files()
    )

    orphans = []
    for path, where in sorted(set(routes)):
        # Compare on the literal segments only. A path like
        # /coach/play/{session_id}/x is called as `/coach/play/${id}/x`, so
        # matching the whole string finds nothing and every route looks dead.
        segments = [s for s in path.strip("/").split("/")
                    if s and not s.startswith("{")]
        if not segments:
            continue
        needle = segments[-1]
        if len(needle) < 4:
            needle = "/".join(segments[-2:]) if len(segments) > 1 else needle
        if needle and needle not in frontend_text:
            orphans.append((path, where))
    return orphans


async def hollow_fields(sample: int = 300, min_present: int = 100):
    """Fields written on every card, populated on none.

    This is the shape that hid the 5-puzzle concept test for four months.
    `concept_id` is a key on all 16,292 stored review cards and null on all of
    them, because a May cleanup hardcoded it to None and a September feature
    was built to read it. Nothing raises: a null is not an error, and a schema
    check passes because the KEY is there.

    Auto-discovers rather than taking a list -- a hardcoded list only finds
    the fields someone already suspected.
    """
    import os, collections
    from motor.motor_asyncio import AsyncIOMotorClient

    db = AsyncIOMotorClient(
        os.environ["MONGO_URL"], serverSelectionTimeoutMS=10000
    )[os.environ.get("DB_NAME", "test_database")]

    present = collections.Counter()
    filled = collections.Counter()
    cards = 0

    cursor = db.game_analyses.find(
        {"decryption_v5_data.0": {"$exists": True}},
        {"decryption_v5_data": 1},
    ).limit(sample)

    async for doc in cursor:
        for card in doc.get("decryption_v5_data") or []:
            cards += 1
            for key, value in card.items():
                present[key] += 1
                if value not in (None, "", [], {}, False):
                    filled[key] += 1
            for key, value in (card.get("plan") or {}).items():
                present["plan." + key] += 1
                if value not in (None, "", [], {}, False):
                    filled["plan." + key] += 1

    hollow = sorted(
        (k for k in present
         if present[k] >= min_present and filled[k] == 0),
        key=lambda k: -present[k],
    )
    return cards, present, filled, hollow



# The caption path's entry points. A claim is "reached" when the module that
# owns its quality_id is importable from one of these, transitively.
CAPTION_ROOTS = (
    "caption_pipeline",
    "caption_facts",
    "game_decryption_v5_service",
    "caption_rules",
)

# Surfaces that are not the caption path and so do not count as reaching a
# player through a caption. The admin review queue is the important one: it
# is where evidence is GATHERED, which is easy to mistake for shipping.
NOT_A_PLAYER_SURFACE = ("admin_", "scripts/", "tests/")


def _module_imports(path: Path) -> set[str]:
    """Bare module names this file imports from services/ or backend root."""
    out: set[str] = set()
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return out
    for m in re.finditer(r"from\s+(?:services\.)?([A-Za-z_][\w.]*)\s+import", text):
        out.add(m.group(1).split(".")[-1])
    for m in re.finditer(r"^\s*import\s+(?:services\.)?([A-Za-z_][\w.]*)",
                         text, re.M):
        out.add(m.group(1).split(".")[-1])
    return out


def _reachable_from_caption_path() -> set[str]:
    """Modules the caption path can actually get to, following imports."""
    by_name: dict[str, Path] = {}
    for f in (BACKEND / "services").rglob("*.py"):
        by_name.setdefault(f.stem, f)
    for f in BACKEND.glob("*.py"):
        by_name.setdefault(f.stem, f)

    seen: set[str] = set()
    queue = [r for r in CAPTION_ROOTS if r in by_name]
    while queue:
        name = queue.pop()
        if name in seen:
            continue
        seen.add(name)
        for dep in _module_imports(by_name[name]):
            if dep in by_name and dep not in seen:
                queue.append(dep)
    return seen


def unreached_claims() -> list[tuple[str, str, str]]:
    """Graded quality_ids whose owning module the caption path cannot reach.

    Returns (quality_id, grade, owning module or '(no owner found)').

    Deliberately reports SHADOW ones too. A shadow grade explains why a
    claim is silent; it does not explain why promoting it would change
    nothing. Those are two different problems and the second one is the
    one that wastes review time.
    """
    sys.path.insert(0, str(BACKEND))
    try:
        from services.detector_quality import explicit_authorizations
    except Exception as exc:  # pragma: no cover
        raise SourceUnavailable(f"cannot import detector_quality: {exc}")

    auth = explicit_authorizations()
    reachable = _reachable_from_caption_path()
    if len(reachable) < 5:
        raise SourceUnavailable(
            "import walk found almost nothing; refusing to report a clean "
            "bill of health produced by looking at nothing")

    # Which module literally contains each quality_id string.
    owners: dict[str, str] = {}
    for f in list((BACKEND / "services").rglob("*.py")) + list(BACKEND.glob("*.py")):
        if any(part in str(f) for part in NOT_A_PLAYER_SURFACE):
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for qid in auth:
            if qid in text:
                owners.setdefault(qid, f.stem)

    out: list[tuple[str, str, str]] = []
    for qid in sorted(auth):
        owner = owners.get(qid)
        # Owned only by detector_quality itself = declared, implemented nowhere.
        if owner in (None, "detector_quality"):
            continue
        if owner in reachable:
            continue
        g = auth[qid].grade
        # A PLAN-grade claim is authorised for plans and mastery, not for
        # captions, so "no caption-path caller" may be correct for it. It is
        # still reported, because the alternative is deciding here which
        # surfaces a claim was meant for -- and that guess is what hid
        # allowed_mate for a month. The grade is printed so a reader can
        # judge.
        out.append((qid, g.value if hasattr(g, "value") else str(g), owner))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--self-test", action="store_true",
                    help="assert the checks find known-dead things")
    ap.add_argument("--with-data", action="store_true",
                    help="also report hollow fields (needs the DB)")
    args = ap.parse_args(argv)

    print("=" * 66)
    print("  REACHABILITY MAP — built, but does it reach a user?")
    print("=" * 66)
    print()

    static_ran = True
    comps: list[tuple[str, str]] = []
    try:
        comps = orphan_components()
        eps = orphan_endpoints()
    except SourceUnavailable as exc:
        static_ran = False
        print(f"STATIC CHECKS SKIPPED — {exc}")
        print("   (not 'no orphans found'. Nothing was examined.)")
        eps = []

    if static_ran:
        print(f"ORPHAN COMPONENTS  (imported, never rendered): {len(comps)}")
        for name, where in comps:
            print(f"   {name:<34} {where}")
        print()
        print(f"ORPHAN ENDPOINTS  (registered, no caller): {len(eps)}")
        for path, where in eps[:40]:
            print(f"   {path:<44} {where}")
        if len(eps) > 40:
            print(f"   ... and {len(eps) - 40} more")

    unreached: list[tuple[str, str, str]] = []
    unreached_ran = True
    try:
        unreached = unreached_claims()
    except SourceUnavailable as exc:
        unreached_ran = False
        print()
        print(f"UNREACHED CLAIMS SKIPPED — {exc}")
    if unreached_ran:
        print()
        print("UNREACHED CLAIMS  (graded, no caption-path caller): "
              f"{len(unreached)}")
        for qid, grade, owner in unreached:
            print(f"   {qid:<44} {grade:<8} {owner}")
        if not unreached:
            print("   none")

    hollow_result = None
    if args.with_data:
        import asyncio
        cards, present, filled, hollow = asyncio.run(hollow_fields())
        hollow_result = (cards, present, filled, hollow)
        print()
        print(f"HOLLOW FIELDS  (written on every card, never populated)")
        print(f"   sampled {cards} review cards")
        for k in hollow:
            print(f"   {k:<34} present {present[k]:>6}   populated 0")
        if not hollow:
            print("   none")

    if args.self_test:
        print()
        print("SELF-TEST — the checks must find what we already know is dead")
        # UNREACHED CLAIM controls. Both directions, because a check that
        # reports everything is as useless as one that reports nothing.
        _un = {q for q, _, _ in unreached}
        if not unreached_ran:
            print("   SKIP  unreached claims — could not import the table")
        else:
            if "gap:king_safety:allowed_mate_exact" in _un:
                print("   PASS  allowed_mate reported (55 rulings, no caption caller)")
            else:
                print("   FAIL  allowed_mate NOT reported — check is blind")
            if "gap:piece_safety:simple_hang" in _un:
                print("   FAIL  simple_hang reported — it IS on the caption path")
            else:
                print("   PASS  simple_hang not reported (live, via caption_facts)")
            if "tactic:discovered_attack_with_stored_payoff" in _un:
                print("   FAIL  discovered_attack reported as unreached — it is "
                      "REACHABLE and merely gated; a different shape")
            else:
                print("   PASS  discovered_attack not reported (reachable, gated)")
        names = {n for n, _ in comps}
        ok = True
        if not static_ran:
            print("   SKIP  component checks — no frontend source here")
        # Known dead today.
        elif "CoachTimelinePanel" in names:
            print("   PASS  CoachTimelinePanel reported (known dead)")
        else:
            print("   FAIL  CoachTimelinePanel NOT reported — check is blind")
            ok = False
        # Known alive since 2026-09-23.
        if not static_ran:
            pass
        elif "EvalBar" in names:
            print("   FAIL  EvalBar reported — but it was wired on 2026-09-23")
            ok = False
        else:
            print("   PASS  EvalBar not reported (correctly seen as wired)")
        if hollow_result:
            _cards, _present, _filled, hollow = hollow_result
            if "concept_id" in hollow:
                print("   PASS  concept_id reported hollow (known dead)")
            else:
                print("   FAIL  concept_id NOT reported — check is blind")
                ok = False
            if _filled.get("caption", 0) > 0 and "caption" not in hollow:
                print("   PASS  caption not reported (correctly seen as live)")
            else:
                print("   FAIL  caption misreported — check flags healthy fields")
                ok = False
        return 0 if ok else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
