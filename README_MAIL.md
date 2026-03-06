# OTP Email (Gmail SMTP)

This project sends OTP emails using Gmail SMTP with an App Password (works on Render free plan).

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
- Check recipient spam folder.