# ===== CONFIG =====
$Server = "72.60.204.176"
$User = "root"
$RemoteDir = "/var/www/html/SMART_CHESS_COACH"
$Port = 22
$BuildDir = "build"

# ===== DEPENDENCY CHECK =====
function Find-Executable($Name) {
    $found = Get-Command $Name -ErrorAction SilentlyContinue
    if ($found) { return $found.Source }
    
    $commonPaths = @(
        "$env:ProgramFiles\PuTTY\$Name",
        "${env:ProgramFiles(x86)}\PuTTY\$Name"
    )
    
    foreach ($path in $commonPaths) {
        if (Test-Path $path) { return $path }
    }
    return $null
}

$plinkPath = Find-Executable "plink.exe"
if (-not $plinkPath) {
    Write-Error "plink.exe not found. Install PuTTY and add it to PATH."
    exit 1
}

$pscpPath = Find-Executable "pscp.exe"
if (-not $pscpPath) {
    Write-Error "pscp.exe not found. Install PuTTY and add it to PATH."
    exit 1
}

# ===== BUILD REACT APP =====
Write-Host "Preparing to build React app..."

# A publish must be built from the repository's one dependency authority.
# Never reuse an unknown node_modules tree or a stale build directory.
yarn install --frozen-lockfile --ignore-engines --non-interactive
if ($LASTEXITCODE -ne 0) { exit 1 }

yarn build
if ($LASTEXITCODE -ne 0) { exit 1 }

# Check build folder
if (-Not (Test-Path $BuildDir)) {
    Write-Error "Build directory not found!"
    exit 1
}

# ===== PASSWORD PROMPT =====
$SecurePassword = Read-Host "Enter SSH password" -AsSecureString
$Password = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecurePassword)
)

# ===== UPLOAD FILES =====
Write-Host "Uploading files to server..."

& $plinkPath -ssh $User@$Server -P $Port -pw $Password `
    "mkdir -p $RemoteDir && rm -rf $RemoteDir/*"

if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to prepare remote directory"
    exit 1
}

& $pscpPath -r -P $Port -pw $Password "$BuildDir/*" "${User}@${Server}:${RemoteDir}"

if ($LASTEXITCODE -ne 0) {
    Write-Error "File upload failed"
    exit 1
}

# ===== CLEAN UP PASSWORD =====
$Password = $null
[System.GC]::Collect()

Write-Host "✅ Deployment completed successfully"
