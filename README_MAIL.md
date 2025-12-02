# SMTP / OTP Setup

This project can send OTP emails via SMTP. Follow these steps to enable real delivery.

1) Recommended: use Gmail + App Password

- Ensure 2-Step Verification is enabled on the Google account.
- Create an App Password (Google Account -> Security -> 2-Step Verification -> App passwords).
- Copy the 16-character app password — this will be used as `SMTP_PASS`.

2) Provide environment variables

Option A — temporary in PowerShell (session only):
```
cd C:\Users\gowth\agriAI360
#$env:SMTP_USER = "yourgmail@gmail.com"
#$env:SMTP_PASS = "your_app_password_here"
#$env:SMTP_HOST = "smtp.gmail.com"
#$env:SMTP_PORT = "465"
#$env:SMTP_USE_SSL = "1"
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

3) Test using a local debug SMTP server (no external email required)

In a terminal run:
```
python -m smtpd -n -c DebuggingServer localhost:1025
```
Then run the app with these env vars set (PowerShell):
```
$env:SMTP_HOST = "localhost"
$env:SMTP_PORT = "1025"
$env:SMTP_USE_SSL = "0"
python .\app.py
```
The debug SMTP server will print the outgoing message including the OTP.

4) Troubleshooting
- If you see `535` or `SMTPAuthenticationError`: check `SMTP_USER` and `SMTP_PASS`. For Gmail use an App Password.
- Check the server console for either the dev-mode OTP print (`[DEV MODE] SMTP not configured. OTP for ...`) or the SMTP traceback.
- Check recipient spam folder.

If you want, I can also add a small PowerShell script to start the app with env vars pre-filled (not with your secrets). Let me know.