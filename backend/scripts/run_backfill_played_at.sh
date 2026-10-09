#!/usr/bin/env bash
# shellcheck source=/root/scripts/chess_backend_container.sh
. /root/scripts/chess_backend_container.sh
# Keep `played_at_utc` typed on every game. Idempotent: writes 0 when clean.
#
# WHY THIS IS SCHEDULED AND NOT A ONE-OFF. This field is the ONLY date any
# before/after measurement reads. When it is absent the focus-outcome window
# falls back to comparing `date_played` as a STRING -- and "." sorts above "-",
# so chess.com's dotted dates land after every ISO timestamp whatever date they
# represent. Measured 2026-10-07 before the repair: 445 games sat in the
# after-window of 16 of 49 active focuses, having been played before the focus
# started.
#
# The importer does write the field -- Sep 27 to Oct 6 is 1,480 games at 100%.
# But on 2026-10-07, 11 of 92 imports slipped through without it. derive()
# returns a correct instant for all 11 when re-run, so the data was never lost;
# most likely the PGN arrived after the game row. One slip a day silently
# re-introduces the ordering bug, and a repair that decays is not a repair.
#
# WHY IT AUTO-CONFIRMS THE PLAN, AND WHEN IT REFUSES. --apply demands the
# fingerprint printed by the dry run, so that nobody applies a plan they have
# not seen. That guard is for a large migration; defeating it wholesale would
# be wrong, so this only auto-confirms a plan that is SMALL and CLEAN:
#
#     rows to write <= MAX_AUTO   and   disagreements with the PGN == 0
#
# Anything bigger or dirtier is left alone and the script exits non-zero with
# the plan printed, so a human looks. That is the case this must never
# silently handle: a large diff means something upstream changed.
set -uo pipefail

MAX_AUTO=200
LOG=$(docker exec "$CHESS_BACKEND" python3 scripts/backfill_played_at_utc.py 2>&1) || {
  echo "dry run failed:"; echo "$LOG"; exit 1; }

TO_WRITE=$(sed -n 's/.*would write played_at_utc *: *\([0-9]*\).*/\1/p' <<<"$LOG" | head -1)
DISAGREE=$(awk '/disagrees with PGN/{f=1;next} f&&/count:/{print $2;exit}' <<<"$LOG")
PLAN=$(sed -n 's/.*plan fingerprint: *\([0-9a-f]*\).*/\1/p' <<<"$LOG" | head -1)

: "${TO_WRITE:=}" "${DISAGREE:=}" "${PLAN:=}"
if [ -z "$TO_WRITE" ] || [ -z "$PLAN" ]; then
  echo "could not parse the dry-run plan; not applying."; echo "$LOG"; exit 1
fi

echo "played_at_utc top-up: ${TO_WRITE} to write, ${DISAGREE:-?} disagreeing, plan ${PLAN}"

if [ "$TO_WRITE" -eq 0 ]; then
  echo "nothing to do."; exit 0
fi
if [ "${DISAGREE:-1}" != "0" ] || [ "$TO_WRITE" -gt "$MAX_AUTO" ]; then
  echo "REFUSING to auto-apply: plan is large or disagrees with the PGN."
  echo "Someone should look, then run:"
  echo "  docker exec "$CHESS_BACKEND" python3 scripts/backfill_played_at_utc.py --apply --confirm-plan ${PLAN}"
  echo "$LOG"; exit 2
fi

docker exec "$CHESS_BACKEND" python3 scripts/backfill_played_at_utc.py \
  --apply --confirm-plan "$PLAN"
