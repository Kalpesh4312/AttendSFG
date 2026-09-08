"""
Email sending for OTP verification (registration) and password reset.

Configure real email delivery by setting these environment variables
before starting the app:
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM_EMAIL

If SMTP_USER / SMTP_PASSWORD are not set, the app runs in "dev mode":
the OTP is printed to the server's terminal (and also returned in the
API response as `dev_otp`) instead of being emailed, so the whole
project still works out of the box without any email account set up.
"""
import random
import smtplib
import ssl as ssl_lib
from email.mime.text import MIMEText

from flask import current_app


def generate_otp(length=6):
    return "".join(random.choices("0123456789", k=length))


def is_email_configured():
    cfg = current_app.config
    return bool(cfg.get("SMTP_USER") and cfg.get("SMTP_PASSWORD"))


def send_otp_email(to_email: str, purpose: str, otp: str) -> bool:
    """Send the OTP by email. Returns True if a real email was sent,
    False if it fell back to dev-mode (printed to console only)."""
    subject_map = {
        "register": "Verify your email — AttendAI",
        "reset": "Password reset code — AttendAI",
    }
    subject = subject_map.get(purpose, "Your verification code — AttendAI")

    body_map = {
        "register": (
            f"Your email verification code is: {otp}\n\n"
            f"Enter this code to finish creating your AttendAI account.\n"
            f"This code expires in {current_app.config['OTP_EXPIRY_MINUTES']} minutes.\n\n"
            f"If you didn't request this, you can ignore this email."
        ),
        "reset": (
            f"Your password reset code is: {otp}\n\n"
            f"Enter this code to reset your AttendAI password.\n"
            f"This code expires in {current_app.config['OTP_EXPIRY_MINUTES']} minutes.\n\n"
            f"If you didn't request this, you can ignore this email — your "
            f"password will not be changed."
        ),
    }
    body = body_map.get(purpose, f"Your verification code is: {otp}")

    if not is_email_configured():
        print("=" * 60)
        print(f" [DEV MODE - email not configured] OTP for {to_email}")
        print(f" Purpose: {purpose}")
        print(f" OTP CODE: {otp}")
        print(" Set SMTP_HOST/SMTP_USER/SMTP_PASSWORD env vars to send")
        print(" real emails instead of printing the code here.")
        print("=" * 60)
        return False

    cfg = current_app.config
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = cfg.get("SMTP_FROM_EMAIL") or cfg["SMTP_USER"]
    msg["To"] = to_email

    try:
        context = ssl_lib.create_default_context()
        with smtplib.SMTP(cfg["SMTP_HOST"], int(cfg["SMTP_PORT"])) as server:
            server.starttls(context=context)
            server.login(cfg["SMTP_USER"], cfg["SMTP_PASSWORD"])
            server.sendmail(msg["From"], [to_email], msg.as_string())
        return True
    except Exception as e:
        print(f"[email] Failed to send email to {to_email}: {e}")
        print(f"[email] Falling back to console — OTP CODE: {otp}")
        return False
