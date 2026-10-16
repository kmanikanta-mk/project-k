Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = $PSScriptRoot
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
$previousAppPassword = $env:APP_PASSWORD
$previousSecretKey = $env:SECRET_KEY
$previousPublicTunnel = $env:PUBLIC_TUNNEL
$cloudflaredCommand = Get-Command cloudflared -ErrorAction SilentlyContinue
$cloudflaredPath = if ($cloudflaredCommand) { $cloudflaredCommand.Source }
if (-not $cloudflaredPath) {
    $wingetLink = Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Links\cloudflared.exe"
    if (Test-Path -LiteralPath $wingetLink) {
        $cloudflaredPath = $wingetLink
    }
}
if (-not $cloudflaredPath) {
    $wingetPackages = Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Packages"
    $cloudflaredPackage = Get-ChildItem `
        -LiteralPath $wingetPackages `
        -Directory `
        -Filter "Cloudflare.cloudflared_*" `
        -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($cloudflaredPackage) {
        $packageExecutable = Join-Path $cloudflaredPackage.FullName "cloudflared.exe"
        if (Test-Path -LiteralPath $packageExecutable) {
            $cloudflaredPath = $packageExecutable
        }
    }
}

if (-not (Test-Path -LiteralPath $python)) {
    throw "Project virtual environment not found: $python"
}

if (-not $cloudflaredPath) {
    Write-Error @"
cloudflared is not installed or is not on PATH.
Install it from PowerShell with:
  winget install --id Cloudflare.cloudflared --exact
Then close and reopen PowerShell and run this script again.
Alternatively, use Cloudflare's Windows installation guide:
  https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
"@
    exit 1
}

if (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue) {
    throw "Port 8000 is already in use. Stop the existing app before starting an authenticated public tunnel."
}

$securePassword = Read-Host "Choose a password for public access" -AsSecureString
$credential = New-Object System.Management.Automation.PSCredential(
    "Stillroom",
    $securePassword
)
$env:APP_PASSWORD = $credential.GetNetworkCredential().Password
if ([string]::IsNullOrWhiteSpace($env:APP_PASSWORD)) {
    throw "A non-empty public access password is required."
}

$keyBytes = New-Object byte[] 32
[System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($keyBytes)
$env:SECRET_KEY = [System.BitConverter]::ToString($keyBytes).Replace("-", "").ToLowerInvariant()
$env:PUBLIC_TUNNEL = "1"

$server = $null
$tunnel = $null
$stdoutPath = Join-Path $env:TEMP ("stillroom-cloudflared-{0}.out" -f [guid]::NewGuid())
$stderrPath = Join-Path $env:TEMP ("stillroom-cloudflared-{0}.err" -f [guid]::NewGuid())

try {
    $server = Start-Process `
        -FilePath $python `
        -ArgumentList @("-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", "8000") `
        -WorkingDirectory $projectRoot `
        -PassThru `
        -WindowStyle Hidden

    $localReady = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        if ($server.HasExited) {
            throw "Uvicorn exited before the local health check succeeded."
        }
        try {
            $health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -TimeoutSec 2
            if ($health.status -eq "ok") {
                $localReady = $true
                break
            }
        }
        catch {
            Start-Sleep -Seconds 1
        }
    }
    if (-not $localReady) {
        throw "The local FastAPI health check did not succeed on port 8000."
    }

    $tunnel = Start-Process `
        -FilePath $cloudflaredPath `
        -ArgumentList @("tunnel", "--no-autoupdate", "--url", "http://127.0.0.1:8000") `
        -WorkingDirectory $projectRoot `
        -PassThru `
        -WindowStyle Hidden `
        -RedirectStandardOutput $stdoutPath `
        -RedirectStandardError $stderrPath

    $publicUrl = $null
    for ($attempt = 0; $attempt -lt 90; $attempt++) {
        if ($tunnel.HasExited) {
            throw "cloudflared exited before establishing a Quick Tunnel."
        }

        foreach ($logPath in @($stdoutPath, $stderrPath)) {
            if (Test-Path -LiteralPath $logPath) {
                $logContent = Get-Content -LiteralPath $logPath -Raw
                if ($logContent -match "https://[a-z0-9-]+\.trycloudflare\.com") {
                    $publicUrl = $Matches[0]
                    break
                }
            }
        }
        if ($publicUrl) {
            break
        }
        Start-Sleep -Seconds 1
    }
    if (-not $publicUrl) {
        throw "cloudflared did not report a Quick Tunnel HTTPS URL."
    }

    $publicReady = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        try {
            $health = Invoke-RestMethod -Uri "$publicUrl/health" -TimeoutSec 5
            if ($health.status -eq "ok") {
                $publicReady = $true
                break
            }
        }
        catch {
            Start-Sleep -Seconds 1
        }
    }
    if (-not $publicReady) {
        throw "The Quick Tunnel URL was created, but its public HTTPS health check failed."
    }

    Write-Host ""
    Write-Host "Public HTTPS URL: $publicUrl" -ForegroundColor Green
    Write-Host "Sign in using the password you just entered."
    Write-Host "Press Ctrl+C to stop the tunnel and local server."

    while (-not $tunnel.HasExited -and -not $server.HasExited) {
        Start-Sleep -Seconds 1
        $tunnel.Refresh()
        $server.Refresh()
    }

    if ($tunnel.HasExited) {
        throw "cloudflared stopped."
    }
    throw "The local FastAPI server stopped."
}
finally {
    foreach ($process in @($tunnel, $server)) {
        if ($null -ne $process) {
            $process.Refresh()
            if (-not $process.HasExited) {
                Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
            }
        }
    }
    Remove-Item -LiteralPath $stdoutPath, $stderrPath -Force -ErrorAction SilentlyContinue
    if ($null -eq $previousAppPassword) {
        Remove-Item Env:\APP_PASSWORD -ErrorAction SilentlyContinue
    }
    else {
        $env:APP_PASSWORD = $previousAppPassword
    }
    if ($null -eq $previousSecretKey) {
        Remove-Item Env:\SECRET_KEY -ErrorAction SilentlyContinue
    }
    else {
        $env:SECRET_KEY = $previousSecretKey
    }
    if ($null -eq $previousPublicTunnel) {
        Remove-Item Env:\PUBLIC_TUNNEL -ErrorAction SilentlyContinue
    }
    else {
        $env:PUBLIC_TUNNEL = $previousPublicTunnel
    }
}
