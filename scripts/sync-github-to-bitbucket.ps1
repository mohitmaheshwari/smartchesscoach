<#
.SYNOPSIS
    Sync GitHub repository to Bitbucket

.DESCRIPTION
    This script clones from GitHub and pushes to Bitbucket.
    Run this once to set up, then use GitHub Actions for auto-sync.

.EXAMPLE
    .\sync-github-to-bitbucket.ps1

.NOTES
    First time setup - run this script once to initialize the Bitbucket repo.
    After that, GitHub Actions will handle automatic syncing.
#>

# ============================================
# CONFIGURATION - Edit these values
# ============================================
$GITHUB_REPO = "https://github.com/YOUR_USERNAME/YOUR_REPO.git"
$BITBUCKET_USERNAME = "YOUR_BITBUCKET_USERNAME"
$BITBUCKET_WORKSPACE = "YOUR_WORKSPACE"  # Usually same as username for personal repos
$BITBUCKET_REPO_NAME = "chess-coach"     # Your Bitbucket repo name

# ============================================
# DO NOT EDIT BELOW THIS LINE
# ============================================

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  GitHub to Bitbucket Sync Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Prompt for Bitbucket App Password (secure input)
$BITBUCKET_APP_PASSWORD = Read-Host -Prompt "Enter your Bitbucket App Password" -AsSecureString
$BSTR = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($BITBUCKET_APP_PASSWORD)
$BITBUCKET_APP_PASSWORD_PLAIN = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)

# Create temp directory
$TEMP_DIR = Join-Path $env:TEMP "github-bitbucket-sync-$(Get-Date -Format 'yyyyMMddHHmmss')"
Write-Host "Creating temp directory: $TEMP_DIR" -ForegroundColor Yellow

try {
    # Clone from GitHub
    Write-Host ""
    Write-Host "[1/4] Cloning from GitHub..." -ForegroundColor Green
    git clone --mirror $GITHUB_REPO $TEMP_DIR
    
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to clone from GitHub"
    }
    
    # Change to temp directory
    Set-Location $TEMP_DIR
    
    # Add Bitbucket remote
    Write-Host ""
    Write-Host "[2/4] Adding Bitbucket remote..." -ForegroundColor Green
    $BITBUCKET_URL = "https://${BITBUCKET_USERNAME}:${BITBUCKET_APP_PASSWORD_PLAIN}@bitbucket.org/${BITBUCKET_WORKSPACE}/${BITBUCKET_REPO_NAME}.git"
    git remote add bitbucket $BITBUCKET_URL
    
    # Push to Bitbucket
    Write-Host ""
    Write-Host "[3/4] Pushing to Bitbucket..." -ForegroundColor Green
    git push bitbucket --mirror
    
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to push to Bitbucket. Make sure the repo exists!"
    }
    
    Write-Host ""
    Write-Host "[4/4] Cleaning up..." -ForegroundColor Green
    Set-Location $env:TEMP
    Remove-Item -Recurse -Force $TEMP_DIR
    
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  SUCCESS! Repo synced to Bitbucket" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Yellow
    Write-Host "1. Set up GitHub Secrets for automatic sync" -ForegroundColor White
    Write-Host "2. The GitHub Action will auto-sync on every push" -ForegroundColor White
    Write-Host ""
    
} catch {
    Write-Host ""
    Write-Host "ERROR: $_" -ForegroundColor Red
    Write-Host ""
    
    # Cleanup on error
    if (Test-Path $TEMP_DIR) {
        Set-Location $env:TEMP
        Remove-Item -Recurse -Force $TEMP_DIR -ErrorAction SilentlyContinue
    }
    
    exit 1
}
