# OTP Email (Gmail SMTP / Resend)

This project can send OTP emails via:
- Gmail SMTP (TLS 587) using an App Password
- Resend (HTTPS API) (recommended on Render if SMTP is blocked/slow)

1) Enable Gmail App Password

- Ensure 2-Step Verification is enabled on the Google account.
- Create an App Password (Google Account -> Security -> 2-Step Verification -> App passwords).
- Copy the 16-character app password — this will be used as `EMAIL_PASS`.

2) Provide environment variables

Option A — temporary in PowerShell (session only):
```
cd C:\Users\gowth\agriAI360
#$env:EMAIL_USER = "yourgmail@gmail.com"
#$env:EMAIL_PASS = "your_app_password_here"
$env:EMAIL_PROVIDER = "smtp"
$env:SMTP_TIMEOUT = "8"
python .\app.py
```

Option B — use a `.env` file (convenient)

- Copy `.env.example` to `.env` and fill values. Do NOT commit `.env` to version control.
- Install `python-dotenv` (already referenced in `requirements.txt`):
```
pip install -r requirements.txt
```
- Then run:
```
python .\app.py
```

3) Troubleshooting
- If you see `535` / `SMTPAuthenticationError`: verify `EMAIL_USER` and `EMAIL_PASS` (must be an App Password, not your normal Gmail password).
- If Render logs show timeouts/hangs connecting to `smtp.gmail.com:587`, SMTP may be blocked or too slow. Set `SMTP_TIMEOUT` (default is 8s) and consider Resend.
- Check recipient spam folder.

## Resend (recommended on Render)

Set:
- `EMAIL_PROVIDER=resend`
- `RESEND_API_KEY=...`
- `RESEND_FROM=...` (a verified sender email in Resend)

Then OTP emails will be sent via HTTPS instead of SMTP.