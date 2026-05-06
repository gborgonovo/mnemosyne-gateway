import smtplib
import ssl
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def send_email(subject: str, body: str, to: str = None):
    sender    = os.environ["ALFRED_EMAIL"]
    password  = os.environ["ALFRED_EMAIL_PASSWORD"]
    host      = os.environ["ALFRED_SMTP_HOST"]
    port      = int(os.environ.get("ALFRED_SMTP_PORT", "465"))
    recipient = to or os.environ["ALFRED_EMAIL_TO"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"Alfred <{sender}>"
    msg["To"]      = recipient
    msg.attach(MIMEText(body, "plain", "utf-8"))

    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL(host, port, context=ctx) as server:
        server.login(sender, password)
        server.sendmail(sender, recipient, msg.as_string())
