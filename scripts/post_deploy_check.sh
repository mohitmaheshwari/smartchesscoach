#!/bin/bash
# post_deploy_check.sh — run ON THE SERVER after every deploy.
#
# Born 2026-07-14 after a deploy that passed health/auth/billing checks while
# every app-container DB connection was dead (MONGO_URL pointed at the public
# IP that the same deploy had just closed). Lesson: health endpoints lie —
# verification MUST include at least one endpoint that READS THE DATABASE.
#
# Usage:  bash scripts/post_deploy_check.sh          (on the server)
# Exit 0 = all checks pass; non-zero = deploy is NOT verified, investigate.

set -u
FAIL=0
say() { printf '%-58s %s\n' "$1" "$2"; }
check() { # name, expected, actual
  if [ "$2" = "$3" ]; then say "$1" "OK ($3)"; else say "$1" "FAIL (expected $2, got $3)"; FAIL=1; fi
}

BASE="http://localhost:8002/api"

# 0. Wait for boot — the backend takes 30-90s to start after `up -d --build`;
#    running the checks mid-boot produces false FAILs (2026-07-14 lesson).
printf 'waiting for backend boot'
for i in $(seq 1 40); do
  curl -sf "$BASE/health" >/dev/null 2>&1 && break
  printf '.'; sleep 3
done
echo

# 1. Liveness (necessary, NOT sufficient)
code=$(curl -s -o /dev/null -w '%{http_code}' "$BASE/health" || echo 000)
check "health endpoint" "200" "$code"

# 2. Auth posture: anonymous must be rejected (catches DEV_MODE=true in prod)
code=$(curl -s -o /dev/null -w '%{http_code}' "$BASE/auth/me" || echo 000)
check "anonymous auth/me rejected (DEV_MODE off)" "401" "$code"

# 3. THE DB-TOUCHING CHECK — a real read through the app's own Mongo client.
#    /public/openings serves opening content from the DB with no auth.
body=$(curl -s "$BASE/public/openings" || echo '')
if printf '%s' "$body" | grep -q '"slug"'; then
  say "DB-backed endpoint returns data" "OK"
else
  say "DB-backed endpoint returns data" "FAIL (empty/error: ${body:0:80})"
  FAIL=1
fi

# 4. Deep DB check from inside the container (catches wrong MONGO_URL directly)
users=$(docker exec chess-coach-backend python -c "
import os
from pymongo import MongoClient
db=MongoClient(os.environ['MONGO_URL'],serverSelectionTimeoutMS=8000)[os.environ.get('DB_NAME','chess_coach')]
print(db.users.count_documents({}))" 2>/dev/null || echo ERR)
if [ "$users" != "ERR" ] && [ "$users" -gt 0 ] 2>/dev/null; then
  say "container -> Mongo direct read" "OK ($users users)"
else
  say "container -> Mongo direct read" "FAIL ($users)"
  FAIL=1
fi

# 5. Billing config (price + keys wired)
amount=$(curl -s "$BASE/billing/config" | grep -o '"amount":[0-9]*' | cut -d: -f2)
check "billing amount (₹149)" "14900" "${amount:-none}"

# 6. Mongo NOT publicly bound
binding=$(docker port chess-coach-mongodb 2>/dev/null | head -1)
case "$binding" in
  *127.0.0.1*) say "mongo binding localhost-only" "OK" ;;
  *) say "mongo binding localhost-only" "FAIL ($binding)"; FAIL=1 ;;
esac

# 7. Analysis worker alive + connected (log heartbeat within 10 min)
if docker logs --since 10m "$(docker ps --format '{{.Names}}' | grep analysis-worker | head -1)" 2>&1 | grep -q "Connection refused\|ServerSelectionTimeout"; then
  say "analysis worker Mongo connectivity" "FAIL (connection errors in log)"
  FAIL=1
else
  say "analysis worker Mongo connectivity" "OK"
fi

# 8. Public site end-to-end through nginx/TLS
code=$(curl -s -o /dev/null -w '%{http_code}' "https://chessguru.ai/api/health" || echo 000)
check "public https health" "200" "$code"

echo
if [ "$FAIL" -eq 0 ]; then
  echo "ALL CHECKS PASSED — deploy verified."
else
  echo "DEPLOY NOT VERIFIED — fix before walking away."
fi
exit $FAIL
