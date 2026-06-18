# PATTERN #2 DEPLOYMENT — Run this once Docker is running
# PowerShell version for Windows

Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host " PATTERN #2 DEPLOYMENT SCRIPT" -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host ""

# Step 1: Verify Docker is running
Write-Host "[1/5] Verifying Docker is running..." -ForegroundColor Yellow
$dockerTest = docker ps 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Docker is not running. Start Docker Desktop and try again." -ForegroundColor Red
    exit 1
}
Write-Host "✓ Docker is running" -ForegroundColor Green
Write-Host ""

# Step 2: Check if container exists
Write-Host "[2/5] Checking for chess-coach-backend container..." -ForegroundColor Yellow
$container = docker ps -a 2>$null | Select-String "chess-coach-backend"
if (-not $container) {
    Write-Host "❌ Container 'chess-coach-backend' not found." -ForegroundColor Red
    Write-Host "   Please ensure the backend is set up via docker-compose." -ForegroundColor Red
    exit 1
}
Write-Host "✓ Container exists" -ForegroundColor Green
Write-Host ""

# Step 3: Copy updated file
Write-Host "[3/5] Copying updated caption_pipeline.py to container..." -ForegroundColor Yellow
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
docker cp "$scriptDir/services/caption_pipeline.py" chess-coach-backend:/app/backend/services/
Write-Host "✓ File copied" -ForegroundColor Green
Write-Host ""

# Step 4: Verify import
Write-Host "[4/5] Verifying Python import..." -ForegroundColor Yellow
$importTest = docker exec chess-coach-backend python3 -c @"
import sys
sys.path.insert(0, '/app/backend')
try:
    from services.caption_pipeline import build_move_teaching_decision
    print('✓ Import successful')
except Exception as e:
    print(f'❌ Import failed: {e}')
    sys.exit(1)
"@
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Import verification failed" -ForegroundColor Red
    exit 1
}
Write-Host "✓ Import successful" -ForegroundColor Green
Write-Host ""

# Step 5: Restart backend
Write-Host "[5/5] Restarting backend service..." -ForegroundColor Yellow
docker exec chess-coach-backend supervisorctl restart backend
Write-Host "✓ Backend restarted" -ForegroundColor Green
Write-Host ""

Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Green
Write-Host " ✅ DEPLOYMENT COMPLETE" -ForegroundColor Green
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Green
Write-Host ""
Write-Host "NEXT: Test the 6 assessment conflict positions:" -ForegroundColor Yellow
Write-Host ""
Write-Host "  # Test position 1: fb_f901258f7831 (Qd8, 10cp)" -ForegroundColor Gray
Write-Host "  curl -s http://127.0.0.1:8001/api/game/game_ef9f422a062d -b 'dev_mode=true' | python3 -m json.tool" -ForegroundColor Gray
Write-Host ""
Write-Host "  # Should see: empty caption for Qd8 (assessed as 'good', below rating threshold)" -ForegroundColor Gray
Write-Host ""
