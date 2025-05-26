import os, logging, smtplib
from email.message import EmailMessage

logger = logging.getLogger(__name__)

SMTP_HOST = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
SMTP_USER = os.environ.get('SMTP_USER')
SMTP_PASS = os.environ.get('SMTP_PASS')

def send_email(to: str, subject: str, body: str):
    if not SMTP_USER or not SMTP_PASS:
        logger.error("SMTP credentials not configured")
        raise RuntimeError("SMTP config missing")

    msg = EmailMessage()
    msg["From"] = SMTP_USER
    msg["To"]   = to
    msg["Subject"] = subject
    msg.set_content(body)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
        smtp.starttls()
        smtp.login(SMTP_USER, SMTP_PASS)
        smtp.send_message(msg)
