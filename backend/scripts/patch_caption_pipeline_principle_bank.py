"""One-shot patcher: add principle-bank loader + injection to caption_pipeline.py.

Use docker exec to run inside the container so the file edited matches the
running code.
"""
import sys

PATH = "/app/backend/services/caption_pipeline.py"

HELPER_CODE = '''logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────────────
# v104 (Mohit 2026-06-03) — FLOOR TEACHING PRINCIPLE INJECTION
# ────────────────────────────────────────────────────────────────────
# When R12 falls through to the bare "{played_san} is a mistake. {best} was
# better." shell (no failure_clause, no why_clause), append a transferable
# principle from data/captions/principle_bank.json. Selection is by
# (phase × severity bucket) and deterministic by FEN hash.

import json as _json_pb
import re as _re_pb
import zlib as _zlib_pb
from pathlib import Path as _Path_pb

_PRINCIPLE_BANK_PATH = (
    _Path_pb(__file__).resolve().parent.parent / "data" / "captions" / "principle_bank.json"
)
try:
    with open(_PRINCIPLE_BANK_PATH) as _fpb:
        _PRINCIPLE_BANK = _json_pb.load(_fpb).get("buckets", {})
    logger.info(f"[principle_bank] loaded {len(_PRINCIPLE_BANK)} buckets")
except Exception as _bank_exc:
    logger.warning(f"[principle_bank] load failed: {_bank_exc}")
    _PRINCIPLE_BANK = {}

_SHELL_RE = _re_pb.compile(
    r"^\\S+\\.?\\s+is\\s+an?\\s+"
    r"(?P<sev>mistake|serious mistake|major blunder|inaccuracy)\\.\\s+"
    r"\\S+\\s+was\\s+better\\.?\\s*$"
)


def _maybe_append_floor_principle(
    caption: str, full_move_number: int, mover_is_user: bool, fen_before: str,
) -> str:
    """Append a floor teaching principle when caption is the bare shell shape.

    Only fires on user moves (opp moves have their own variants).
    Returns the caption unchanged if shell doesn't match or bank is empty.
    """
    if not caption or not mover_is_user or not _PRINCIPLE_BANK:
        return caption
    m = _SHELL_RE.match(caption.strip())
    if not m:
        return caption
    sev = m.group("sev")
    sev_bucket = "blunder" if sev in ("serious mistake", "major blunder") else "mistake"
    mn = full_move_number or 1
    if mn <= 12:
        phase = "opening"
    elif mn <= 40:
        phase = "middlegame"
    else:
        phase = "endgame"
    bucket_key = f"{phase}_{sev_bucket}"
    bucket = _PRINCIPLE_BANK.get(bucket_key) or []
    if not bucket:
        return caption
    idx = _zlib_pb.crc32((fen_before or "").encode("utf-8")) % len(bucket)
    principle = bucket[idx]
    if not caption.endswith("."):
        caption = caption + "."
    return f"{caption} {principle}."


'''

OLD_INJECTION_ANCHOR = (
    "    # ─── 12. A8 caption tier classification ──────────────────────\n"
    "    tier = classify_caption_tier(\n"
    '        caption_text=caption_payload.get("caption") or "",\n'
    '        rule_name=caption_payload.get("rule_name") or "",\n'
    "    )"
)
NEW_INJECTION_ANCHOR = (
    "    # v104 (Mohit 2026-06-03) — floor teaching principle for bare shell.\n"
    "    # Runs BEFORE tier classification so the enriched caption gets the\n"
    "    # right tier assignment.\n"
    "    try:\n"
    '        caption_payload["caption"] = _maybe_append_floor_principle(\n'
    '            caption_payload.get("caption") or "",\n'
    "            inputs.full_move_number,\n"
    "            inputs.mover_is_user,\n"
    "            inputs.fen_before,\n"
    "        )\n"
    "    except Exception as _pb_exc:\n"
    '        logger.warning(f"[principle_bank] inject failed m{inputs.full_move_number}: {_pb_exc!r}")\n'
    "\n"
    + OLD_INJECTION_ANCHOR
)

OLD_HELPER_ANCHOR = "logger = logging.getLogger(__name__)\n"


def main():
    with open(PATH) as f:
        content = f.read()
    if "_PRINCIPLE_BANK" in content:
        print("ALREADY PATCHED — skipping")
        return 0
    helper_count = content.count(OLD_HELPER_ANCHOR)
    if helper_count != 1:
        print(f"ERROR: helper anchor occurs {helper_count} times, expected 1")
        return 1
    injection_count = content.count(OLD_INJECTION_ANCHOR)
    if injection_count != 1:
        print(f"ERROR: injection anchor occurs {injection_count} times, expected 1")
        return 1
    content = content.replace(OLD_HELPER_ANCHOR, HELPER_CODE, 1)
    content = content.replace(OLD_INJECTION_ANCHOR, NEW_INJECTION_ANCHOR, 1)
    with open(PATH, "w") as f:
        f.write(content)
    print("PATCHED OK")
    print(f"  _PRINCIPLE_BANK references: {content.count('_PRINCIPLE_BANK')}")
    print(f"  _maybe_append_floor_principle references: {content.count('_maybe_append_floor_principle')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
