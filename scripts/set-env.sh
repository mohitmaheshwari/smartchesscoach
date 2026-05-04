#!/usr/bin/env bash
#
# set-env.sh — safely add or replace env vars in .env and restart Docker.
#
# Run from the repo root on the server. Idempotent: if a key exists,
# the line is replaced; if not, it's appended. No nano, no editor.
#
# Usage:
#   ./scripts/set-env.sh KEY=VALUE [KEY=VALUE ...]
#
# Example:
#   ./scripts/set-env.sh \
#       RAZORPAY_KEY_ID=rzp_test_xxxxxxxxxxxx \
#       RAZORPAY_KEY_SECRET=your_secret_here
#
# After updating .env, the script restarts the Docker stack so the new
# values reach the running container.

set -euo pipefail

ENV_FILE=".env"

if [ "$#" -eq 0 ]; then
    cat <<EOF
Usage: $0 KEY=VALUE [KEY=VALUE ...]

Adds or replaces KEY=VALUE pairs in .env (idempotent), then restarts
the Docker stack so the new env vars reach the running app.

Example:
  $0 RAZORPAY_KEY_ID=rzp_test_xxx RAZORPAY_KEY_SECRET=yyy
EOF
    exit 1
fi

# Sanity: must be run from the repo root where docker-compose.prod.yml lives.
if [ ! -f "docker-compose.prod.yml" ]; then
    echo "Error: docker-compose.prod.yml not found in current directory." >&2
    echo "Run this script from the repo root (cd ~/repos/smartchesscoach)." >&2
    exit 1
fi

# Create .env with safe perms if missing.
if [ ! -f "$ENV_FILE" ]; then
    touch "$ENV_FILE"
    chmod 600 "$ENV_FILE"
fi

for pair in "$@"; do
    if [[ "$pair" != *"="* ]]; then
        echo "Skip (no '=' in arg): $pair" >&2
        continue
    fi
    key="${pair%%=*}"
    value="${pair#*=}"

    if [ -z "$key" ]; then
        echo "Skip (empty key): $pair" >&2
        continue
    fi

    # Use awk for safe rewrite — sed escaping breaks on /, |, & in values.
    tmp=$(mktemp)
    awk -v key="$key" -v value="$value" '
        BEGIN { replaced = 0 }
        {
            line = $0
            # Extract leading KEY= portion if present
            if (match(line, /^[[:space:]]*[A-Za-z_][A-Za-z0-9_]*=/)) {
                line_key = substr(line, RSTART, RLENGTH - 1)
                gsub(/[[:space:]]/, "", line_key)
                if (line_key == key && !replaced) {
                    print key "=" value
                    replaced = 1
                    next
                }
            }
            print
        }
        END {
            if (!replaced) print key "=" value
        }
    ' "$ENV_FILE" > "$tmp"

    mv "$tmp" "$ENV_FILE"
    chmod 600 "$ENV_FILE"
    echo "Set: $key"
done

echo
echo "Restarting Docker stack so new env vars take effect..."
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

echo
echo "Done. Verify with:"
echo "  docker compose -f docker-compose.yml -f docker-compose.prod.yml exec app env | grep -E 'RAZORPAY|OPENAI|GOOGLE'"
