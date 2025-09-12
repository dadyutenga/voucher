import random
import string
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.core.config import settings

def generate_voucher_code(length: int = 8) -> str:
    """Generate a random alphanumeric voucher code."""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

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
