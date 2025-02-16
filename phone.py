from twilio.rest import Client
import os

# Initialize Twilio client
account_sid = os.getenv('TWILIO_ACCOUNT_SID')
auth_token = os.getenv('TWILIO_AUTH_TOKEN')
verify_service_sid = os.getenv('TWILIO_VERIFY_SERVICE_SID')
client = Client(account_sid, auth_token)

def send_verification_code(phone_number):
    try:
        verification = client.verify.services(verify_service_sid).verifications.create(
            to=phone_number,
            channel='sms'  # Use 'call' for voice call verification
        )
        print(f"Sent verification code to {phone_number}")
    except Exception as e:
        print(f"Failed to send verification code: {e}")
        raise

def check_verification_code(phone_number, code):
    try:
        verification_check = client.verify.services(verify_service_sid).verification_checks.create(
            to=phone_number,
            code=code
        )
        return verification_check.status == 'approved'
    except Exception as e:
        print(f"Failed to verify code: {e}")
        return False
