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

def send_sms_via_email(to_contact, carrier, subject, body, app_config):
    """
    If a valid carrier is provided, build the recipient as phone_number@gateway.
    Otherwise, assume 'to_contact' is already an email address.
    """
    try:
        if carrier:
            gateway = CARRIER_GATEWAYS.get(carrier.lower())
            if not gateway:
                raise ValueError("Invalid carrier provided.")
            recipient = f"{to_contact}{gateway}"
        else:
            # Fallback to using the provided contact as an email address.
            recipient = to_contact

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
