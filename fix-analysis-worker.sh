#!/bin/bash
set -e

echo "================================================"
echo "Fixing Analysis Worker MongoDB Connection"
echo "================================================"

REPO_ROOT="/root/repos/smartchesscoach"
ENV_FILE="$REPO_ROOT/.env"

if [ ! -f "$ENV_FILE" ]; then
    echo "ERROR: .env file not found at $ENV_FILE"
    exit 1
fi

echo ""
echo "Current MONGO_URL in .env:"
grep "MONGO_URL=" "$ENV_FILE" || echo "(not found)"

echo ""
echo "Updating MONGO_URL to production address..."

# Backup the current .env
cp "$ENV_FILE" "$ENV_FILE.backup"
echo "  Backup created: $ENV_FILE.backup"

# Update MONGO_URL - remove old line and add new one
sed -i '/^MONGO_URL=/d' "$ENV_FILE"

# Add the correct production MONGO_URL
cat >> "$ENV_FILE" << 'EOF'
MONGO_URL=mongodb://<user>:<password-from-env>@72.60.204.176:27017/?authSource=admin
EOF

echo ""
echo "New MONGO_URL in .env:"
grep "MONGO_URL=" "$ENV_FILE"

echo ""
echo "Stopping analysis worker..."
cd "$REPO_ROOT"
docker compose down smartchesscoach-analysis-worker-1 2>/dev/null || true
sleep 2

echo "Rebuilding and starting analysis worker..."
docker compose up -d --build analysis-worker

echo ""
echo "Waiting for worker to start..."
sleep 5

echo ""
echo "Worker status:"
docker ps | grep analysis-worker || echo "ERROR: Worker not running"

echo ""
echo "Checking worker logs (last 20 lines)..."
docker logs smartchesscoach-analysis-worker-1 --tail 20 2>/dev/null || echo "No logs yet"

echo ""
echo "================================================"
echo "Fix complete!"
echo "================================================"
echo ""
echo "The worker should now connect to MongoDB and start"
echo "processing the 9,155 queued games."
echo ""
echo "Monitor progress with:"
echo "  docker logs -f smartchesscoach-analysis-worker-1"
echo ""
