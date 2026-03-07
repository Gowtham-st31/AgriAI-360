# OTP Email (SMTP + Brevo fallback)

This project can send OTP emails using:
- Gmail SMTP (TLS 587)
- Brevo (Sendinblue) Transactional Email API

By default (`EMAIL_PROVIDER=auto`) it tries SMTP first, and if SMTP fails it falls back to Brevo (if configured).

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

3) Brevo setup (recommended fallback)

- Create a Brevo API key (Transactional) and verify your sender.
- Set these variables:
	- `BREVO_API_KEY`
	- `BREVO_FROM` (must be a verified sender email in Brevo)
	- Optional: `BREVO_SENDER_NAME`

4) Provider selection

- `EMAIL_PROVIDER=auto` (default): SMTP → Brevo
- `EMAIL_PROVIDER=smtp`: only SMTP
- `EMAIL_PROVIDER=brevo`: only Brevo

5) Troubleshooting
- If you see `535` / `SMTPAuthenticationError`: verify `EMAIL_USER` and `EMAIL_PASS` (must be an App Password, not your normal Gmail password).
- If SMTP times out/blocks (common on some hosts): keep `EMAIL_PROVIDER=auto` and configure Brevo/Resend so it can fall back.
- Check recipient spam folder.
