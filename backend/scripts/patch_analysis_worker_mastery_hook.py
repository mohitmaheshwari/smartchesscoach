"""One-shot patcher: add the concept mastery tracker hook to analysis_worker.py.

Inserts the hook right after the opening-profile refresh block, before
the game-status update. Idempotent — checks for the hook first.
"""
import sys

PATH = "/app/backend/analysis_worker.py"

OLD = (
    '            _asyncio.run(_refresh_opening_profile())\n'
    '            logger.info(f"[opening-profile] refreshed for {user_id}")\n'
    '        except Exception as _op_err:\n'
    '            logger.warning(f"[opening-profile] refresh failed (non-fatal): {_op_err}")\n'
    '\n'
    '        # Update game status'
)

NEW = (
    '            _asyncio.run(_refresh_opening_profile())\n'
    '            logger.info(f"[opening-profile] refreshed for {user_id}")\n'
    '        except Exception as _op_err:\n'
    '            logger.warning(f"[opening-profile] refresh failed (non-fatal): {_op_err}")\n'
    '\n'
    '        # Engine 2 Phase 1 (Mohit 2026-06-04) — concept mastery tracker.\n'
    '        # After v5 data is written and the opening profile is refreshed,\n'
    '        # compute mastery streaks for this user × game and update\n'
    '        # user_concept_understanding (streak_clean / acknowledged /\n'
    '        # mastered_at). Idempotent via last_evaluated_game_id. See\n'
    '        # services/concept_mastery_tracker.py.\n'
    '        try:\n'
    '            import asyncio as _asyncio\n'
    '            from motor.motor_asyncio import AsyncIOMotorClient as _AsyncMotor\n'
    '            from services.concept_mastery_tracker import update_user_mastery_for_game\n'
    '            _mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")\n'
    '            _db_name = os.environ.get("DB_NAME", "chess_coach")\n'
    '\n'
    '            async def _update_mastery():\n'
    '                _client = _AsyncMotor(_mongo_url)\n'
    '                _db = _client[_db_name]\n'
    '                try:\n'
    '                    return await update_user_mastery_for_game(_db, user_id, game_id)\n'
    '                finally:\n'
    '                    _client.close()\n'
    '\n'
    '            _mastery_summary = _asyncio.run(_update_mastery())\n'
    '            logger.info(\n'
    '                f"[mastery-tracker] user {user_id[-12:]} game {game_id[-8:]}: "\n'
    '                f"clean={_mastery_summary[\'clean_count\']} "\n'
    '                f"violated={_mastery_summary[\'violated_count\']} "\n'
    '                f"mastered={_mastery_summary[\'mastered_count\']}"\n'
    '            )\n'
    '        except Exception as _mast_err:\n'
    '            logger.warning(f"[mastery-tracker] update failed (non-fatal): {_mast_err}")\n'
    '\n'
    '        # Update game status'
)


def main():
    with open(PATH) as f:
        content = f.read()
    if "concept_mastery_tracker" in content:
        print("ALREADY PATCHED — skipping")
        return 0
    if content.count(OLD) != 1:
        print(f"ERROR: anchor count = {content.count(OLD)}, expected 1")
        return 1
    content = content.replace(OLD, NEW, 1)
    with open(PATH, "w") as f:
        f.write(content)
    print(f"PATCHED. concept_mastery_tracker refs: {content.count('concept_mastery_tracker')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
