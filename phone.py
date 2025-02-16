# phone.py
import os
from twilio.rest import Client

def send_sms_via_twilio(to_number, body):
    """Send SMS using Twilio."""
    # Make sure these environment variables are set in your .env or hosting environment
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_PHONE_NUMBER")

    if not (account_sid and auth_token and from_number):
        raise ValueError("Twilio environment variables are not set properly.")

    client = Client(account_sid, auth_token)
    message = client.messages.create(
        to=to_number,
        from_=from_number,
        body=body
    )
    return message.sid
