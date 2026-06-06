"""Pre-flight probe for the authoring-override ship sequence.

Built 2026-06-06. Mohit asked: 'create one single script to check
whatever you need and I paste you output so we can review together'.

This script gathers EVERYTHING I need to confidently green-light the
authoring_safe_subset.py + authoring_apply_safe_subset.py run:

  1. Schema check — does move_feedback store is_authoring_submission
     FLAT (at top level) or NESTED (under .authoring)? The existing
     audit script queries FLAT; if prod stores nested, the audit needs
     a one-line patch before it'll find anything.

  2. Pending authoring submission count — how many items overall have
     is_authoring_submission=true and are still pending review.

  3. Tonight's batch — for each of the 21 feedback_ids from the
     2026-06-06 batch, report current state in mongo (pending /
     valid / acknowledged / missing) + the key fields the audit
     gate consumes (fen, cp_loss, severity, best_move, original
     caption, suggested caption, lengths).

  4. Existing override state — how many rows in
     authored_caption_overrides, and which of tonight's 21
     (game_id, move_number, move_san) tuples already have an
     override (collision risk for the apply step).

  5. V5_COACHING_VERSION — what the live code says (helps decide
     the post-apply bump target).

Read-only. No writes. Safe to run on prod without --apply gating.

Usage in prod container:

    docker exec -it chess-coach-backend python /app/backend/scripts/probe_authoring_state.py
"""
import os
import asyncio
import json
import re
from pathlib import Path

from motor.motor_asyncio import AsyncIOMotorClient


# The 21 feedback_ids from Mohit's 2026-06-06 paste, in order.
# Items 1-20 visible in the paste; #21 was truncated.
TONIGHTS_BATCH = [
    ("fb_9f984e9753fc", "Mohit",  "Nxf7", False),
    ("fb_9c4ad043240b", "Parth",  "Nxg3", True),
    ("fb_0589638c6580", "Parth",  "g5",   True),
    ("fb_44ab295462d0", "Parth",  "cxd5", True),
    ("fb_2ad6a3fb208e", "Parth",  "Nxd5", True),
    ("fb_4d2363f0539b", "Parth",  "Qe2",  True),
    ("fb_4a281910cfa1", "Parth",  "e5",   True),
    ("fb_1cfd93561e46", "Parth",  "Bf4",  True),
    ("fb_530303f85fc8", "Parth",  "Nc3",  True),
    ("fb_582837f50d6d", "Parth",  "d6",   True),
    ("fb_6785172554ab", "Parth",  "d4",   False),
    ("fb_22528b6266b1", "Parth",  "Bxe5", True),
    ("fb_771714e55f1f", "Parth",  "c3",   True),
    ("fb_2c60b3989eed", "Parth",  "O-O",  False),
    ("fb_6609c44f669d", "Parth",  "Nf3",  False),
    ("fb_9d6b4ad725ae", "Parth",  "gxf4", True),
    ("fb_644107b00f68", "Parth",  "Rh4",  True),
    ("fb_538530c45efb", "Parth",  "f5",   True),
    ("fb_68adf27b28c1", "Parth",  "g3",   True),
    ("fb_96c28ed0b759", "Parth",  "Re4",  False),
    ("fb_afb6ebc3c0e2", "Parth",  "(truncated)", None),
]


async def main():
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "chess_coach")
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    print("=" * 72)
    print("AUTHORING-OVERRIDE PRE-FLIGHT PROBE")
    print("=" * 72)
    print()

    # ─── 1. SCHEMA CHECK ────────────────────────────────────────────────
    print("─── 1. SCHEMA CHECK ───")
    flat = await db.move_feedback.count_documents(
        {"is_authoring_submission": True}
    )
    nested = await db.move_feedback.count_documents(
        {"authoring.is_authoring_submission": True}
    )
    print(f"  is_authoring_submission=True at top level (flat):   {flat}")
    print(f"  authoring.is_authoring_submission=True (nested):    {nested}")
    if flat == 0 and nested > 0:
        print("  >>> SCHEMA IS NESTED. The existing audit script needs a")
        print("  >>> one-line patch before it'll find any submissions.")
    elif flat > 0 and nested == 0:
        print("  >>> SCHEMA IS FLAT. Audit script will work as-is.")
    elif flat > 0 and nested > 0:
        print("  >>> MIXED — some rows flat, some nested. Migration may")
        print("  >>> be incomplete. Audit script will only find FLAT rows.")
    else:
        print("  >>> ZERO authoring submissions found in either shape.")
        print("  >>> Check whether the move_feedback collection has any")
        print("  >>> documents at all.")
    total_fb = await db.move_feedback.count_documents({})
    print(f"  move_feedback total docs:                            {total_fb}")
    print()

    # ─── 2. PENDING AUTHORING SUBMISSIONS ─────────────────────────────────
    print("─── 2. PENDING AUTHORING SUBMISSIONS (top-level shape) ───")
    query_flat = {"is_authoring_submission": True}
    pending_flat = await db.move_feedback.count_documents(
        {**query_flat, "status": "pending"}
    )
    valid_flat = await db.move_feedback.count_documents(
        {**query_flat, "status": "valid"}
    )
    other_flat = await db.move_feedback.count_documents(
        {**query_flat, "status": {"$nin": ["pending", "valid"]}}
    )
    print(f"  pending: {pending_flat}")
    print(f"  valid:   {valid_flat}")
    print(f"  other:   {other_flat}")
    print()

    # ─── 3. TONIGHT'S BATCH — STATE PER FEEDBACK_ID ───────────────────────
    print("─── 3. TONIGHT'S BATCH — 21 FEEDBACK IDS ───")
    print(f"  {'fb_id':<22} {'user':<6} {'san':<6} {'auth':<5} {'status':<10} "
          f"{'sev':<8} {'cp':<5} {'orig':<5} {'sugg':<5}")
    for fb_id, user_name, san, expected_authoring in TONIGHTS_BATCH:
        doc = await db.move_feedback.find_one({"feedback_id": fb_id})
        if doc is None:
            print(f"  {fb_id:<22} {user_name:<6} {san:<6} {'?':<5} {'MISSING':<10}")
            continue
        # Try both shapes for is_authoring_submission
        is_auth = doc.get("is_authoring_submission")
        if is_auth is None:
            is_auth = (doc.get("authoring") or {}).get("is_authoring_submission")
        is_auth_str = str(bool(is_auth))
        status = doc.get("status", "?")
        d = doc.get("diagnostics") or {}
        sev = d.get("severity") or doc.get("severity") or "?"
        cp = d.get("cp_loss") or doc.get("cp_loss") or 0
        orig_len = len((doc.get("coaching_text") or doc.get("coaching_text_flagged") or "").strip())
        sugg_text = (
            doc.get("suggested_caption")
            or (doc.get("authoring") or {}).get("suggested_caption")
            or ""
        )
        sugg_len = len(sugg_text.strip())
        print(f"  {fb_id:<22} {user_name:<6} {san:<6} {is_auth_str:<5} "
              f"{status:<10} {sev:<8} {str(cp):<5} {str(orig_len):<5} {str(sugg_len):<5}")
    print()

    # ─── 4. EXISTING OVERRIDE STATE ──────────────────────────────────────
    print("─── 4. EXISTING AUTHORED_CAPTION_OVERRIDES ───")
    total_overrides = await db.authored_caption_overrides.count_documents({})
    print(f"  Total override rows: {total_overrides}")

    print()
    print("  Collisions with tonight's batch (game_id+move_number+move_san):")
    collision_count = 0
    for fb_id, user_name, san, _ in TONIGHTS_BATCH:
        if san == "(truncated)":
            continue
        doc = await db.move_feedback.find_one({"feedback_id": fb_id})
        if doc is None:
            continue
        gid = doc.get("game_id")
        # Try both shapes for move_number/move_san location
        mn = doc.get("move_number") or (doc.get("position") or {}).get("move_number")
        played_san = doc.get("move_san") or (doc.get("position") or {}).get("move_san")
        if not (gid and mn and played_san):
            continue
        existing = await db.authored_caption_overrides.find_one({
            "game_id": gid, "move_number": mn, "move_san": played_san,
        })
        if existing:
            collision_count += 1
            print(f"    {fb_id} ({played_san} m{mn} game={gid[:8]}...)  → ALREADY HAS OVERRIDE")
    if collision_count == 0:
        print("    (none — clean re-apply landscape)")
    print()

    # ─── 5. V5_COACHING_VERSION ──────────────────────────────────────────
    print("─── 5. V5_COACHING_VERSION ───")
    v5_path = Path("/app/backend/services/game_decryption_v5_service.py")
    if not v5_path.exists():
        # Fallback for local-dev
        v5_path = Path(__file__).resolve().parent.parent / "services" / "game_decryption_v5_service.py"
    if v5_path.exists():
        for line in v5_path.read_text(encoding="utf-8").splitlines()[:80]:
            m = re.match(r"^V5_COACHING_VERSION\s*=\s*(\d+)", line)
            if m:
                print(f"  Current V5_COACHING_VERSION = {m.group(1)}")
                print(f"  After --apply, bump to:       {int(m.group(1)) + 1}")
                break
    else:
        print(f"  v5 service file not found at {v5_path}")
    print()

    # ─── 6. SAMPLE: pick first PASSING-LOOKING item for sanity ────────────
    print("─── 6. SAMPLE ITEM (one full doc dump for sanity) ───")
    sample_fb_id = "fb_4d2363f0539b"  # Qe2 — looks high-quality authored
    doc = await db.move_feedback.find_one({"feedback_id": sample_fb_id})
    if doc:
        # Strip _id for cleaner output
        doc.pop("_id", None)
        # Cap large text fields for readability
        for key in ("suggested_caption", "coaching_text", "coaching_text_flagged",
                    "inaccuracy_reason"):
            v = doc.get(key)
            if isinstance(v, str) and len(v) > 200:
                doc[key] = v[:200] + f"... [TRUNCATED, total {len(v)} chars]"
        # Also check nested authoring block
        auth = doc.get("authoring")
        if isinstance(auth, dict):
            for key in ("suggested_caption", "inaccuracy_reason"):
                v = auth.get(key)
                if isinstance(v, str) and len(v) > 200:
                    auth[key] = v[:200] + f"... [TRUNCATED, total {len(v)} chars]"
        print(json.dumps(doc, indent=2, default=str))
    else:
        print(f"  Sample doc {sample_fb_id} not found in move_feedback.")
    print()

    print("=" * 72)
    print("PROBE COMPLETE — paste this output back to me and we'll decide.")
    print("=" * 72)
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
