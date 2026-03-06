<#
Interactive helper to start the app with Gmail SMTP environment variables.
This script prompts for Gmail credentials for the current session only and does
not store them on disk.

Run: .\start-app.ps1 from PowerShell. You may need to adjust execution policy:
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#>

<#
NOTE: This project now uses Gmail SMTP with:
    EMAIL_USER (Gmail address)
    EMAIL_PASS (Gmail App Password)
#>

Write-Host "Start app helper - configure Gmail SMTP (App Password) for this session." -ForegroundColor Cyan

function Set-DotEnvVar {
    param(
        [string]$Path,
        [string]$Key,
        [string]$Value
    )
    if ([string]::IsNullOrWhiteSpace($Key)) { return }

    $lines = @()
    if (Test-Path $Path) {
        try { $lines = Get-Content -Path $Path -ErrorAction Stop }
        catch { $lines = @() }
    }

    $escapedKey = [regex]::Escape($Key)
    $pattern = "^\s*$escapedKey\s*=.*$"
    $newLine = "$Key=$Value"

    $found = $false
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match $pattern) {
            $lines[$i] = $newLine
            $found = $true
            break
        }
    }
    if (-not $found) { $lines += $newLine }

    Set-Content -Path $Path -Value ($lines -join "`n") -Encoding UTF8
}

$emailUser = Read-Host "EMAIL_USER (Gmail address, or leave empty to skip email sending)"
if ([string]::IsNullOrWhiteSpace($emailUser)) {
    Write-Host "No email configured. App may fail to send OTP emails." -ForegroundColor Yellow
} else {
    $securePass = Read-Host "EMAIL_PASS (Gmail App Password)" -AsSecureString
    $bstr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePass)
    $plainPass = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)
    [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)

    $env:EMAIL_USER = $emailUser
    $env:EMAIL_PASS = $plainPass

    Write-Host "Email configured for session: $env:EMAIL_USER (Gmail SMTP TLS 587)" -ForegroundColor Green
}

# Optional Flask secret
$flaskSecret = Read-Host "FLASK_SECRET (optional, leave blank to use default)"
if (-not [string]::IsNullOrWhiteSpace($flaskSecret)) { $env:FLASK_SECRET = $flaskSecret }

# Optional MongoDB Atlas
$mongoUri = Read-Host "MONGODB_URI (optional: paste Atlas connection string, leave blank to use JSON files)"
if (-not [string]::IsNullOrWhiteSpace($mongoUri)) {
    $env:MONGODB_URI = $mongoUri
    $mongoDb = Read-Host "MONGODB_DB (optional: database name, leave blank for default/agri)"
    if (-not [string]::IsNullOrWhiteSpace($mongoDb)) { $env:MONGODB_DB = $mongoDb }
}

Write-Host "Starting Flask app... Press Ctrl+C to stop." -ForegroundColor Cyan
# Offer to persist configuration so it survives restarts/deploys
try{
    $saveEnv = Read-Host "Save these settings to a local .env file for future runs? (y/N)"
    if(-not [string]::IsNullOrWhiteSpace($saveEnv) -and $saveEnv.Trim().ToLower().StartsWith('y')){
        $envFilePath = Join-Path (Get-Location) '.env'
        try{
            if($env:EMAIL_USER){ Set-DotEnvVar -Path $envFilePath -Key 'EMAIL_USER' -Value $env:EMAIL_USER }
            if($env:EMAIL_PASS){ Set-DotEnvVar -Path $envFilePath -Key 'EMAIL_PASS' -Value $env:EMAIL_PASS }
            if($env:FLASK_SECRET){ Set-DotEnvVar -Path $envFilePath -Key 'FLASK_SECRET' -Value $env:FLASK_SECRET }
            if($env:MONGODB_URI){ Set-DotEnvVar -Path $envFilePath -Key 'MONGODB_URI' -Value $env:MONGODB_URI }
            if($env:MONGODB_DB){ Set-DotEnvVar -Path $envFilePath -Key 'MONGODB_DB' -Value $env:MONGODB_DB }
            Write-Host "Updated .env at $envFilePath" -ForegroundColor Green
        }catch{
            Write-Host "Failed to update .env: $_" -ForegroundColor Yellow
        }
    }

    $persist = Read-Host "Also persist these values as user environment variables? (y/N)"
    if(-not [string]::IsNullOrWhiteSpace($persist) -and $persist.Trim().ToLower().StartsWith('y')){
        try{
            if($env:EMAIL_USER){ [Environment]::SetEnvironmentVariable('EMAIL_USER',$env:EMAIL_USER,'User') }
            if($env:EMAIL_PASS){ [Environment]::SetEnvironmentVariable('EMAIL_PASS',$env:EMAIL_PASS,'User') }
            if($env:FLASK_SECRET){ [Environment]::SetEnvironmentVariable('FLASK_SECRET',$env:FLASK_SECRET,'User') }
            if($env:MONGODB_URI){ [Environment]::SetEnvironmentVariable('MONGODB_URI',$env:MONGODB_URI,'User') }
            if($env:MONGODB_DB){ [Environment]::SetEnvironmentVariable('MONGODB_DB',$env:MONGODB_DB,'User') }
            Write-Host "Persisted variables to user environment. Open a new terminal to see them." -ForegroundColor Green
        }catch{
            Write-Host "Failed to persist env vars: $_" -ForegroundColor Yellow
        }
    }
}catch{
    # non-interactive or if something goes wrong, ignore and continue
}

$venvPy = Join-Path (Get-Location) ".venv\Scripts\python.exe"
if (Test-Path $venvPy) {
    & $venvPy .\app.py
} else {
    python .\app.py
}


