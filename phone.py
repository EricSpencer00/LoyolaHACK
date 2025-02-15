# phone.py
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

CARRIER_GATEWAYS = {
    "att": "@txt.att.net",
    "tmobile": "@tmomail.net",
    "verizon": "@vtext.com",
    "sprint": "@messaging.sprintpcs.com",
    "uscellular": "@email.uscc.net"
}

def send_sms_via_email(to_number, carrier, subject, body, app_config):
    """
    Sends an SMS via email-to-text.
    - to_number: User's phone number (e.g., "3125551234" or "312 555 1234")
    - carrier: The carrier identifier (e.g., "att")
    - subject: The email subject (often ignored by SMS gateways)
    - body: The text message body.
    - app_config: A dict containing mail configuration.
    """
    try:
        if carrier:
            gateway = CARRIER_GATEWAYS.get(carrier.lower())
            if not gateway:
                raise ValueError("Invalid carrier provided.")
            # Remove any non-digit characters
            clean_number = re.sub(r'\D', '', to_number)
            recipient = f"{clean_number}{gateway}"
        else:
            recipient = to_number

        # For debugging purposes, print the recipient address:
        print("Sending SMS to:", recipient)

        msg = MIMEMultipart()
        msg["From"] = app_config.get("MAIL_DEFAULT_SENDER")
        msg["To"] = recipient
        msg["Subject"] = subject
        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP(app_config.get("MAIL_SERVER"), app_config.get("MAIL_PORT"))
        server.starttls()
        server.login(app_config.get("MAIL_USERNAME"), app_config.get("MAIL_PASSWORD"))
        server.sendmail(app_config.get("MAIL_DEFAULT_SENDER"), recipient, msg.as_string())
        server.quit()
        print(f"SMS (via email) sent to {recipient}")
    except Exception as e:
        print(f"Failed to send SMS: {e}")
        raise
