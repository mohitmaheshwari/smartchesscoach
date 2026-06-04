"""One-shot patcher: add opening-accuracy (engine-aware) hook to analysis_worker.py.
Sits right after the trap-mastery hook."""
import sys
PATH = "/app/backend/analysis_worker.py"

OLD = (
    '        except Exception as _trap_mast_err:\n'
    '            logger.warning(f"[trap-mastery] update failed (non-fatal): {_trap_mast_err}")\n'
    '\n'
    '        # Update game status'
)
NEW = (
    '        except Exception as _trap_mast_err:\n'
    '            logger.warning(f"[trap-mastery] update failed (non-fatal): {_trap_mast_err}")\n'
    '\n'
    '        # Engine-aware opening accuracy (Mohit 2026-06-04). Computes\n'
    '        # accuracy from cp_loss-graded user opening moves rather than\n'
    '        # the prior curriculum-exact-match measure (which punished\n'
    '        # any reasonable book alternative). Writes one new\n'
    '        # accuracy_history entry per game. Idempotent. Non-fatal.\n'
    '        try:\n'
    '            import asyncio as _asyncio\n'
    '            from motor.motor_asyncio import AsyncIOMotorClient as _AsyncMotor\n'
    '            from services.opening_mastery_tracker import update_mastery_from_analyzed_game\n'
    '            _mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")\n'
    '            _db_name = os.environ.get("DB_NAME", "chess_coach")\n'
    '\n'
    '            async def _update_opening_acc():\n'
    '                _client = _AsyncMotor(_mongo_url)\n'
    '                _db = _client[_db_name]\n'
    '                try:\n'
    '                    return await update_mastery_from_analyzed_game(_db, user_id, game_id)\n'
    '                finally:\n'
    '                    _client.close()\n'
    '\n'
    '            _acc_result = _asyncio.run(_update_opening_acc())\n'
    '            if _acc_result:\n'
    '                logger.info(\n'
    '                    f"[opening-accuracy] user {user_id[-12:]} game {game_id[-8:]} "\n'
    '                    f"opening={_acc_result.get(\'opening_key\')} "\n'
    '                    f"acc={_acc_result.get(\'accuracy\', 0):.2f} "\n'
    '                    f"moves={_acc_result.get(\'n_moves_evaluated\', 0)}"\n'
    '                )\n'
    '        except Exception as _acc_err:\n'
    '            logger.warning(f"[opening-accuracy] update failed (non-fatal): {_acc_err}")\n'
    '\n'
    '        # Update game status'
)


def main():
    with open(PATH) as f:
        content = f.read()
    if "[opening-accuracy]" in content:
        print("ALREADY PATCHED")
        return 0
    if content.count(OLD) != 1:
        print(f"ERROR: anchor count = {content.count(OLD)}")
        return 1
    with open(PATH, "w") as f:
        f.write(content.replace(OLD, NEW, 1))
    print("PATCHED.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
