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

def send_sms_via_email(to_number, carrier, subject, body):
    try:
        gateway = CARRIER_GATEWAYS.get(carrier.lower())
        if not gateway:
            raise ValueError("Invalid carrier")

        recipient = f"{to_number}{gateway}"
        msg = MIMEMultipart()
        msg["From"] = app.config.get("MAIL_DEFAULT_SENDER")
        msg["To"] = recipient
        msg["Subject"] = subject

        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP(app.config.get("MAIL_SERVER"), app.config.get("MAIL_PORT"))
        server.starttls()
        server.login(app.config.get("MAIL_USERNAME"), app.config.get("MAIL_PASSWORD"))
        server.sendmail(app.config.get("MAIL_DEFAULT_SENDER"), recipient, msg.as_string())
        server.quit()

        print(f"SMS sent to {recipient}")
    except Exception as e:
        print(f"Failed to send SMS: {e}")
