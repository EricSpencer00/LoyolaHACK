from flask import Flask, render_template, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from config import Config
from celery import Celery
import datetime
import random
import json
import firebase_admin
from firebase_admin import auth as firebase_auth
from flask_bootstrap import Bootstrap
from twilio.rest import Client
import dotenv
from phone import send_sms_via_email
import os
from flask_mail import Mail, Message

dotenv.load_dotenv()

app = Flask(__name__)
Bootstrap(app)
app.config.from_object(Config)
db = SQLAlchemy(app)
mail = Mail(app)

# Initialize Firebase Admin if not already initialized
# firebase_admin.initialize_app()

# Initialize Celery
def make_celery(app):
    celery = Celery(app.import_name, broker=app.config['CELERY_BROKER_URL'])
    celery.conf.update(app.config)
    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)
    celery.Task = ContextTask
    return celery

celery = make_celery(app)

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    token = data.get("token")
    try:
        decoded_token = firebase_auth.verify_id_token(token)
        email = decoded_token.get("email")
        # Retrieve or create user record
        user = User.query.filter_by(email=email).first()
        if not user:
            user = User(email=email, favorite_routes=json.dumps([]))
            db.session.add(user)
            db.session.commit()
        # (Set session or return a JWT for your app as needed)
        return jsonify({"status": "success", "email": email})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

# Index route
@app.route('/')
def index():
    firebase_config = {
        'apiKey': os.getenv('FB_API_KEY'),
        'authDomain': f"{os.getenv('FB_PROJECT_ID')}.firebaseapp.com",
        'projectId': os.getenv('FB_PROJECT_ID'),
        'storageBucket': f"{os.getenv('FB_PROJECT_ID')}.appspot.com",
        'messagingSenderId': os.getenv('FB_SENDER_ID'),
        'appId': os.getenv('FB_APP_ID')
    }
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    user = User
    return render_template('dashboard.html')

# API endpoint for real-time transit data (dummy implementation)
@app.route('/api/realtime', methods=['GET'])
def get_realtime():
    type_filter = request.args.get('type')
    user_lat = request.args.get('lat', type=float, default=41.8781)
    user_lng = request.args.get('lng', type=float, default=-87.6298)
    
    dummy_data = [
        {
            "id": 1,
            "lat": user_lat + random.uniform(-0.01, 0.01),
            "lng": user_lng + random.uniform(-0.01, 0.01),
            "type": "bus",
            "line": "22"
        },
        {
            "id": 2,
            "lat": user_lat + random.uniform(-0.01, 0.01),
            "lng": user_lng + random.uniform(-0.01, 0.01),
            "type": "train",
            "line": "Red"
        }
    ]
    if type_filter:
        dummy_data = [d for d in dummy_data if d["type"] == type_filter]
    return jsonify(dummy_data)

# Set user's home location (latitude and longitude)
@app.route('/api/set_home', methods=['POST'])
def set_home():
    data = request.get_json()
    email = data.get("email")
    lat = data.get("lat")
    lng = data.get("lng")
    user = User.query.filter_by(email=email).first()
    if user:
        user.home_lat = lat
        user.home_lng = lng
        db.session.commit()
        return jsonify({"status": "Home location updated"})
    return jsonify({"status": "User not found"}), 404

# Update user's notification settings (e.g., line notifications, time frames, phone number)
@app.route('/api/set_notification', methods=['POST'])
def set_notification():
    data = request.get_json()
    email = data.get("email")
    # Expected payload example:
    # {
    #    "notification_settings": {"line": "22", "notify_before": 10, "time_range": {"start": "05:00", "end": "06:00"}},
    #    "phone_number": "+1234567890"
    # }
    user = User.query.filter_by(email=email).first()
    if user:
        user.notification_settings = json.dumps(data.get("notification_settings"))
        if "phone_number" in data:
            user.phone_number = data.get("phone_number")
        db.session.commit()
        return jsonify({"status": "Notification settings updated"})
    return jsonify({"status": "User not found"}), 404

# API endpoint for predictive analytics (dummy predictions)
@app.route('/api/predictions', methods=['GET'])
def get_predictions():
    dummy_predictions = [
        {
            "id": 1,
            "predicted_arrival": (datetime.datetime.utcnow() + datetime.timedelta(minutes=5)).isoformat() + "Z",
            "confidence": 0.85,
            "line": "22"
        },
        {
            "id": 2,
            "predicted_arrival": (datetime.datetime.utcnow() + datetime.timedelta(minutes=7)).isoformat() + "Z",
            "confidence": 0.80,
            "line": "Red"
        }
    ]
    return jsonify(dummy_predictions)

# Example Celery task to update transit data (e.g., pull from CTA API)
@celery.task
def update_transit_data():
    print("Updating transit data...")
    return "Data updated"

# Celery task that checks for notifications and sends an SMS if a train is close (10 mins away)
@celery.task
def check_and_notify():
    users = User.query.all()
    for user in users:
        if user.notification_settings and user.phone_number and user.carrier:
            notif_settings = json.loads(user.notification_settings)
            # Check your conditions (like train arrival in 10 minutes)
            if notif_settings.get("line") == "Red":  # Example condition
                send_sms_via_email(
                    to_number=user.phone_number,
                    carrier=user.carrier,
                    subject="CTA Transit Alert",
                    body="Your train (Red Line) is arriving in 10 minutes!"
                )

# Route to trigger a manual update (for testing purposes)
@app.route('/trigger-update', methods=['POST'])
def trigger_update():
    update_transit_data.delay()
    return jsonify({"status": "Update triggered"}), 202

@app.route('/send_test_email')
def send_test_email():
    msg = Message('Hello from CTA Tracker!',
                  sender=app.config['MAIL_DEFAULT_SENDER'],
                  recipients=['yourphonenumber@vtext.com'])  # Replace with your phone number and carrier email
    msg.body = 'This is a test email from your CTA Transit Tracker app!'
    mail.send(msg)
    return 'Email sent!'

if __name__ == '__main__':
    app.run(debug=True)
