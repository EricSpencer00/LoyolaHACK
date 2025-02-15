from flask import Flask, render_template, jsonify, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from config import Config
from celery import Celery
import datetime
import random
import json
import firebase_admin
from firebase_admin import auth as firebase_auth, credentials
from flask_bootstrap import Bootstrap
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

# Example User model - ensure this is defined/imported correctly
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    favorite_lines = db.Column(db.Text, default='[]')
    home_lat = db.Column(db.Float, nullable=True)
    home_lng = db.Column(db.Float, nullable=True)
    notification_settings = db.Column(db.Text, nullable=True)
    phone_number = db.Column(db.String(20), nullable=True)
    carrier = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def __repr__(self):
        return f"<User {self.email}>"

# Initialize Firebase only if it hasn't been initialized yet
if not firebase_admin._apps:
    service_account_json = os.getenv("FIREBASE_CREDENTIALS_PATH")
    if not service_account_json:
        raise Exception("FIREBASE_CREDENTIALS_PATH not found in environment variables")
    cred_data = json.loads(service_account_json)
    cred = credentials.Certificate(cred_data)
    firebase_admin.initialize_app(cred)

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
    print("Received data from frontend:", data)
    if not data:
        return jsonify({"status": "error", "message": "No JSON payload received"}), 400

    token = data.get("token")
    if not token:
        return jsonify({"status": "error", "message": "Missing token"}), 400

    try:
        decoded_token = firebase_auth.verify_id_token(token)
        email = decoded_token.get("email")
        print("Decoded token email:", email)  # Debugging line

        user = User.query.filter_by(email=email).first()
        if not user:
            user = User(email=email, favorite_lines=json.dumps([]))
            db.session.add(user)
            db.session.commit()

        session['user_email'] = email
        return jsonify({"status": "success", "email": email})

    except firebase_auth.ExpiredIdTokenError:
        return jsonify({"status": "error", "message": "Token expired"}), 400
    except firebase_auth.InvalidIdTokenError:
        return jsonify({"status": "error", "message": "Invalid token"}), 400
    except Exception as e:
        print(f"Error verifying token: {e}")
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/dashboard')
def dashboard():
    user_email = session.get('user_email')
    if not user_email:
        # If no user is logged in, redirect to the home page
        return redirect(url_for('index'))
    user = User.query.filter_by(email=user_email).first()
    # Parse the favorite_lines (if set) to pass to the template
    favorite_lines = json.loads(user.favorite_lines) if user.favorite_lines else []
    return render_template('dashboard.html', user=user, favorite_lines=favorite_lines)

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
