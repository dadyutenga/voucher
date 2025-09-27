import random
import string
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.core.config import settings

def generate_voucher_code(length: int = 10) -> str:
    """
    Generate a secure 10-character alphanumeric voucher code.
    Uses uppercase letters and digits for better readability and security.
    Excludes confusing characters like 0, O, 1, I, L to prevent errors.
    """
    # Use clear characters only - exclude 0, O, 1, I, L for better readability
    clear_chars = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'
    return ''.join(random.choices(clear_chars, k=length))

def send_email(to_email: str, subject: str, message: str):
    """Send an email using SMTP."""
    msg = MIMEMultipart()
    msg['From'] = settings.SENDER_EMAIL
    msg['To'] = to_email
    msg['Subject'] = subject

    msg.attach(MIMEText(message, 'plain'))

    try:
        server = smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT)
        server.starttls()
        server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        text = msg.as_string()
        server.sendmail(settings.SENDER_EMAIL, to_email, text)
        server.quit()
        print(f"Email sent to {to_email}")
    except Exception as e:
        print(f"Failed to send email: {e}")
