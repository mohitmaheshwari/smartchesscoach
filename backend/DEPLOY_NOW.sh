#!/bin/bash
# PATTERN #2 DEPLOYMENT — Run this once Docker is running

set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " PATTERN #2 DEPLOYMENT SCRIPT"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Step 1: Verify Docker is running
echo "[1/5] Verifying Docker is running..."
if ! docker ps > /dev/null 2>&1; then
    echo "❌ Docker is not running. Start Docker Desktop and try again."
    exit 1
fi
echo "✓ Docker is running"
echo ""

# Step 2: Check if container exists
echo "[2/5] Checking for chess-coach-backend container..."
if ! docker ps -a | grep -q "chess-coach-backend"; then
    echo "❌ Container 'chess-coach-backend' not found."
    echo "   Please ensure the backend is set up via docker-compose."
    exit 1
fi
echo "✓ Container exists"
echo ""

# Step 3: Copy updated file
echo "[3/5] Copying updated caption_pipeline.py to container..."
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
docker cp "$SCRIPT_DIR/services/caption_pipeline.py" chess-coach-backend:/app/backend/services/
echo "✓ File copied"
echo ""

# Step 4: Verify import
echo "[4/5] Verifying Python import..."
docker exec chess-coach-backend python3 -c "
import sys
sys.path.insert(0, '/app/backend')
try:
    from services.caption_pipeline import build_move_teaching_decision
    print('✓ Import successful')
except Exception as e:
    print(f'❌ Import failed: {e}')
    sys.exit(1)
" || exit 1
echo ""

# Step 5: Restart backend
echo "[5/5] Restarting backend service..."
docker exec chess-coach-backend supervisorctl restart backend
echo "✓ Backend restarted"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " ✅ DEPLOYMENT COMPLETE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "NEXT: Test the 6 assessment conflict positions:"
echo ""
echo "  # Test position 1: fb_f901258f7831 (Qd8, 10cp)"
echo "  curl -s http://127.0.0.1:8001/api/game/game_ef9f422a062d -b 'dev_mode=true' | python3 -m json.tool"
echo ""
echo "  # Should see: empty caption for Qd8 (assessed as 'good', below rating threshold)"
echo ""
