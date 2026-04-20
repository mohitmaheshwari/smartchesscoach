#!/usr/bin/env bash
# ------------------------------------------------------------------
# ChessGuru SMTP setup — run this ONCE on your production server
# from the project root (the folder containing docker-compose.yml).
#
# Steps it does:
#   1. Writes SMTP_* vars to .env (at project root)
#   2. Verifies docker-compose.yml references the SMTP vars
#   3. Restarts the backend container
#   4. Shows you the env vars as seen inside the container
#
# Safe to run multiple times — updates only what's needed.
# ------------------------------------------------------------------

set -euo pipefail

# =================================================================
#         PASTE YOUR ZOHO APP PASSWORD BETWEEN THE QUOTES
# =================================================================
SMTP_PASSWORD="WgAGdUNsZWDk"
# =================================================================


# ---- Other SMTP config (change if you're on the US region) -------
SMTP_HOST="smtp.zoho.in"
SMTP_PORT="465"
SMTP_USER="mohit@chessguru.ai"
SMTP_FROM_NAME="Mohit from ChessGuru"


# ============ Guard clauses ======================================
if [ -z "$SMTP_PASSWORD" ] || [ "$SMTP_PASSWORD" = "PASTE_HERE" ]; then
  echo "ERROR: SMTP_PASSWORD is empty."
  echo "Open this script, paste your Zoho App Password between the quotes"
  echo "on the line marked 'PASTE YOUR ZOHO APP PASSWORD', save, and re-run."
  exit 1
fi

if [ ! -f "docker-compose.yml" ]; then
  echo "ERROR: Run this from the project root (where docker-compose.yml lives)."
  exit 1
fi


# ============ Back up .env if it exists ==========================
ENV_FILE=".env"
STAMP=$(date +%s)
if [ -f "$ENV_FILE" ]; then
  cp "$ENV_FILE" "${ENV_FILE}.backup.${STAMP}"
  echo "Backed up existing .env -> ${ENV_FILE}.backup.${STAMP}"
else
  touch "$ENV_FILE"
fi


# ============ Upsert each SMTP key in .env =======================
# awk handles both "key exists (update)" and "key missing (append)"
# portably across GNU/BSD systems (Linux + Mac).
upsert_env() {
  local key="$1"
  local value="$2"
  if grep -q "^${key}=" "$ENV_FILE" 2>/dev/null; then
    awk -v k="$key" -v v="$value" '
      BEGIN{FS=OFS="="}
      $1==k {print k"="v; next}
      {print}
    ' "$ENV_FILE" > "${ENV_FILE}.tmp" && mv "${ENV_FILE}.tmp" "$ENV_FILE"
  else
    echo "${key}=${value}" >> "$ENV_FILE"
  fi
}

upsert_env "SMTP_HOST" "$SMTP_HOST"
upsert_env "SMTP_PORT" "$SMTP_PORT"
upsert_env "SMTP_USER" "$SMTP_USER"
upsert_env "SMTP_PASSWORD" "$SMTP_PASSWORD"
upsert_env "SMTP_FROM_NAME" "$SMTP_FROM_NAME"

chmod 600 "$ENV_FILE"
echo "[ok] .env updated with SMTP_* vars (file permissions set to 600)"


# ============ Check .gitignore blocks .env =======================
if [ -f ".gitignore" ]; then
  if ! grep -qE '^\.env(\s|$)' .gitignore; then
    echo "" >> .gitignore
    echo "# Added by setup_smtp.sh — keep secrets out of git" >> .gitignore
    echo ".env" >> .gitignore
    echo "[ok] Added .env to .gitignore"
  fi
else
  echo ".env" > .gitignore
  echo "[ok] Created .gitignore with .env entry"
fi


# ============ Check docker-compose.yml has SMTP lines ============
if ! grep -q 'SMTP_PASSWORD' docker-compose.yml; then
  echo ""
  echo "!! docker-compose.yml does NOT reference SMTP_PASSWORD yet."
  echo ""
  echo "Open docker-compose.yml, find the 'backend:' service,"
  echo "and add these FIVE lines at the bottom of its 'environment:' block:"
  echo ""
  cat <<'EOF'
      - SMTP_HOST=${SMTP_HOST}
      - SMTP_PORT=${SMTP_PORT}
      - SMTP_USER=${SMTP_USER}
      - SMTP_PASSWORD=${SMTP_PASSWORD}
      - SMTP_FROM_NAME=${SMTP_FROM_NAME}
EOF
  echo ""
  echo "Then re-run this script."
  exit 0
fi

echo "[ok] docker-compose.yml already references SMTP_PASSWORD"


# ============ Restart backend container ==========================
echo ""
echo "Restarting backend container..."
docker compose up -d --force-recreate backend

# Give it a few seconds to come up
sleep 4


# ============ Verify vars landed inside the container ============
CONTAINER="chess-coach-backend"
if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}\$"; then
  echo ""
  echo "Verifying env vars in container:"
  echo "--------------------------------------"
  docker exec "$CONTAINER" env | grep '^SMTP_' | \
    sed 's/^SMTP_PASSWORD=.*/SMTP_PASSWORD=***[hidden]***/'
  echo "--------------------------------------"
else
  echo "WARN: container '$CONTAINER' not running. Check 'docker compose ps'."
fi


echo ""
echo "[done] SMTP is set up."
echo ""
echo "Next step — dry-run the email sender:"
echo "  docker exec chess-coach-backend python scripts/send_beta_feedback_email.py"
echo ""
echo "If the dry-run output looks right, send a test to yourself:"
echo "  docker exec chess-coach-backend python scripts/send_beta_feedback_email.py --send --only your.personal@gmail.com"
