"""One-shot patcher: add trap mastery tracker hook to analysis_worker.py."""
import sys
PATH = "/app/backend/analysis_worker.py"
OLD = (
    '        except Exception as _mast_err:\n'
    '            logger.warning(f"[mastery-tracker] update failed (non-fatal): {_mast_err}")\n'
    '\n'
    '        # Update game status'
)
NEW = (
    '        except Exception as _mast_err:\n'
    '            logger.warning(f"[mastery-tracker] update failed (non-fatal): {_mast_err}")\n'
    '\n'
    '        # Engine 2 — trap mastery tracker. Mirrors concept_mastery_tracker\n'
    '        # but for traps: walks game.trap_fires and updates\n'
    '        # user_opening_mastery.traps_encountered / traps_handled /\n'
    '        # traps_fallen_for. Idempotent. Non-fatal on failure.\n'
    '        try:\n'
    '            import asyncio as _asyncio\n'
    '            from motor.motor_asyncio import AsyncIOMotorClient as _AsyncMotor\n'
    '            from services.trap_mastery_tracker import update_trap_mastery_for_game\n'
    '            _mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")\n'
    '            _db_name = os.environ.get("DB_NAME", "chess_coach")\n'
    '\n'
    '            async def _update_trap_mastery():\n'
    '                _client = _AsyncMotor(_mongo_url)\n'
    '                _db = _client[_db_name]\n'
    '                try:\n'
    '                    return await update_trap_mastery_for_game(_db, user_id, game_id)\n'
    '                finally:\n'
    '                    _client.close()\n'
    '\n'
    '            _trap_summary = _asyncio.run(_update_trap_mastery())\n'
    '            if _trap_summary.get("fires_seen"):\n'
    '                logger.info(\n'
    '                    f"[trap-mastery] user {user_id[-12:]} game {game_id[-8:]}: "\n'
    '                    f"fires={_trap_summary[\'fires_seen\']} "\n'
    '                    f"newly_handled={_trap_summary[\'newly_handled\']} "\n'
    '                    f"newly_fallen={_trap_summary[\'newly_fallen_for\']}"\n'
    '                )\n'
    '        except Exception as _trap_mast_err:\n'
    '            logger.warning(f"[trap-mastery] update failed (non-fatal): {_trap_mast_err}")\n'
    '\n'
    '        # Update game status'
)


def main():
    with open(PATH) as f:
        content = f.read()
    if "trap_mastery_tracker" in content:
        print("ALREADY PATCHED")
        return 0
    if content.count(OLD) != 1:
        print(f"ERROR: anchor count = {content.count(OLD)}, expected 1")
        return 1
    with open(PATH, "w") as f:
        f.write(content.replace(OLD, NEW, 1))
    print(f"PATCHED. trap_mastery_tracker refs: {content.count('trap_mastery_tracker')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
