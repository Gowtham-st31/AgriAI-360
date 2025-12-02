<#
Interactive helper to start the app with optional SMTP environment variables.
This script prompts for SMTP credentials for the current session only and does
not store them on disk. If you leave SMTP_USER empty the app will run in
development mode and print OTPs to the console instead of sending email.

Run: .\start-app.ps1 from PowerShell. You may need to adjust execution policy:
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#>

Write-Host "Start app helper - configure SMTP for this session or leave blank to use dev fallback." -ForegroundColor Cyan

$smtpUser = Read-Host "SMTP_USER (enter full email, or leave empty to skip SMTP)"
if ([string]::IsNullOrWhiteSpace($smtpUser)) {
    Write-Host "No SMTP configured. You can configure SendGrid API key instead, or app will print OTPs to console (dev fallback)." -ForegroundColor Yellow
} else {
    $securePass = Read-Host "SMTP_PASS (App Password)" -AsSecureString
    $bstr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePass)
    $plainPass = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)
    [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)

    $env:SMTP_USER = $smtpUser
    $env:SMTP_PASS = $plainPass

    $smtpHost = Read-Host "SMTP_HOST (default: smtp.gmail.com)"
    if ([string]::IsNullOrWhiteSpace($smtpHost)) { $smtpHost = "smtp.gmail.com" }
    $env:SMTP_HOST = $smtpHost

    $smtpPort = Read-Host "SMTP_PORT (default: 465)"
    if ([string]::IsNullOrWhiteSpace($smtpPort)) { $smtpPort = "465" }
    $env:SMTP_PORT = $smtpPort

    $smtpSsl = Read-Host "SMTP_USE_SSL? (1 for SSL, 0 for STARTTLS) [default:1]"
    if ([string]::IsNullOrWhiteSpace($smtpSsl)) { $smtpSsl = "1" }
    $env:SMTP_USE_SSL = $smtpSsl

    Write-Host "SMTP configured for session: $env:SMTP_USER via $env:SMTP_HOST:$env:SMTP_PORT (SSL=$env:SMTP_USE_SSL)" -ForegroundColor Green
}

# Prompt for SendGrid as an alternative (API-based) provider. If provided, we set SENDGRID_API_KEY and optional SENDGRID_FROM.
$sgKey = Read-Host "SendGrid API key (leave blank to skip)" -AsSecureString
if (-not [System.String]::IsNullOrWhiteSpace([Runtime.InteropServices.Marshal]::PtrToStringAuto([System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($sgKey)))) {
    $bstr2 = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($sgKey)
    $sgPlain = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr2)
    [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr2)
    $env:SENDGRID_API_KEY = $sgPlain
    $sgFrom = Read-Host "SENDGRID_FROM (the verified sender email in SendGrid, optional)"
    if (-not [string]::IsNullOrWhiteSpace($sgFrom)) { $env:SENDGRID_FROM = $sgFrom }
    Write-Host "SendGrid configured for session (SENDGRID_FROM: $env:SENDGRID_FROM)" -ForegroundColor Green
}

# Optional Flask secret
$flaskSecret = Read-Host "FLASK_SECRET (optional, leave blank to use default)"
if (-not [string]::IsNullOrWhiteSpace($flaskSecret)) { $env:FLASK_SECRET = $flaskSecret }

Write-Host "Starting Flask app... Press Ctrl+C to stop." -ForegroundColor Cyan
# Offer to persist configuration so it survives restarts/deploys
try{
    $saveEnv = Read-Host "Save these settings to a local .env file for future runs? (y/N)"
    if(-not [string]::IsNullOrWhiteSpace($saveEnv) -and $saveEnv.Trim().ToLower().StartsWith('y')){
        $envFilePath = Join-Path (Get-Location) '.env'
        $lines = @()
        if($env:SMTP_USER){ $lines += "SMTP_USER=$($env:SMTP_USER)" }
        if($env:SMTP_PASS){ $lines += "SMTP_PASS=$($env:SMTP_PASS)" }
        if($env:SMTP_HOST){ $lines += "SMTP_HOST=$($env:SMTP_HOST)" }
        if($env:SMTP_PORT){ $lines += "SMTP_PORT=$($env:SMTP_PORT)" }
        if($env:SMTP_USE_SSL){ $lines += "SMTP_USE_SSL=$($env:SMTP_USE_SSL)" }
        if($env:SENDGRID_API_KEY){ $lines += "SENDGRID_API_KEY=$($env:SENDGRID_API_KEY)" }
        if($env:SENDGRID_FROM){ $lines += "SENDGRID_FROM=$($env:SENDGRID_FROM)" }
        if($env:FLASK_SECRET){ $lines += "FLASK_SECRET=$($env:FLASK_SECRET)" }
        try{
            # write file with restricted permissions where possible
            $content = $lines -join "`n"
            Set-Content -Path $envFilePath -Value $content -Encoding UTF8
            Write-Host "Wrote .env to $envFilePath" -ForegroundColor Green
        }catch{
            Write-Host "Failed to write .env: $_" -ForegroundColor Yellow
        }
    }

    $persist = Read-Host "Also persist these values as user environment variables? (y/N)"
    if(-not [string]::IsNullOrWhiteSpace($persist) -and $persist.Trim().ToLower().StartsWith('y')){
        try{
            if($env:SMTP_USER){ [Environment]::SetEnvironmentVariable('SMTP_USER',$env:SMTP_USER,'User') }
            if($env:SMTP_PASS){ [Environment]::SetEnvironmentVariable('SMTP_PASS',$env:SMTP_PASS,'User') }
            if($env:SMTP_HOST){ [Environment]::SetEnvironmentVariable('SMTP_HOST',$env:SMTP_HOST,'User') }
            if($env:SMTP_PORT){ [Environment]::SetEnvironmentVariable('SMTP_PORT',$env:SMTP_PORT,'User') }
            if($env:SMTP_USE_SSL){ [Environment]::SetEnvironmentVariable('SMTP_USE_SSL',$env:SMTP_USE_SSL,'User') }
            if($env:SENDGRID_API_KEY){ [Environment]::SetEnvironmentVariable('SENDGRID_API_KEY',$env:SENDGRID_API_KEY,'User') }
            if($env:SENDGRID_FROM){ [Environment]::SetEnvironmentVariable('SENDGRID_FROM',$env:SENDGRID_FROM,'User') }
            if($env:FLASK_SECRET){ [Environment]::SetEnvironmentVariable('FLASK_SECRET',$env:FLASK_SECRET,'User') }
            Write-Host "Persisted variables to user environment. Open a new terminal to see them." -ForegroundColor Green
        }catch{
            Write-Host "Failed to persist env vars: $_" -ForegroundColor Yellow
        }
    }
}catch{
    # non-interactive or if something goes wrong, ignore and continue
}

python .\app.py


