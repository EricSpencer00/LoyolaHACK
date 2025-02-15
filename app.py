from flask import Flask, render_template, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from config import Config
from celery import Celery
import datetime
import random
import json
import firebase_admin
from firebase_admin import auth as firebase_auth

app = Flask(__name__)
app.config.from_object(Config)
db = SQLAlchemy(app)

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
    return render_template('index.html')

# API endpoint for real-time transit data (dummy implementation)
@app.route('/api/realtime', methods=['GET'])
def get_realtime():
    # Replace with real CTA API calls and data processing logic
    dummy_data = [
        {
            "id": 1,
            "lat": 41.8781 + random.uniform(-0.01, 0.01),
            "lng": -87.6298 + random.uniform(-0.01, 0.01),
            "type": "bus",
            "line": "22"
        },
        {
            "id": 2,
            "lat": 41.8781 + random.uniform(-0.01, 0.01),
            "lng": -87.6298 + random.uniform(-0.01, 0.01),
            "type": "train",
            "line": "Red"
        }
    ]
    return jsonify(dummy_data)

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

@app.route('/api/set_notification', methods=['POST'])
def set_notification():
    data = request.get_json()
    email = data.get("email")
    # Example: {"line": "22", "notify_before": 10, "time_range": {"start": "05:00", "end": "06:00"}}
    notif_pref = data.get("notification")
    user = User.query.filter_by(email=email).first()
    if user:
        # Here, you might store a list/dict of notification preferences as JSON
        user.notification_settings = data.get("notification_settings")
        db.session.commit()
        return jsonify({"status": "Notification settings updated"})
    return jsonify({"status": "User not found"}), 404

# API endpoint for predictive analytics (dummy ML predictions)
@app.route('/api/predictions', methods=['GET'])
def get_predictions():
    # Replace with your ML model prediction logic
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

# Example Celery task for periodic updates
@celery.task
def update_transit_data():
    # This task would pull data from CTA APIs and update your database
    print("Updating transit data...")
    return "Data updated"

@celery.task
def check_and_notify():
    # Query users with notification settings, check current time vs. user preference
    # If criteria match (e.g., a bus is predicted to arrive in 10 mins within the time range),
    # send a notification via Firebase Admin SDK:
    from firebase_admin import messaging

    # Example pseudo-code:
    users = User.query.all()
    for user in users:
        if user.notification_settings:
            # Parse settings and compare with live data (implement your logic here)
            # Once a notification condition is met:
            message = messaging.Message(
                notification=messaging.Notification(
                    title="Transit Alert",
                    body="Bus 22 will arrive in 10 minutes!",
                ),
                token="USER_FCM_DEVICE_TOKEN"  # You must store and retrieve device tokens per user
            )
            response = messaging.send(message)
            print("Sent notification:", response)

# Route to trigger background update manually (for testing)
@app.route('/trigger-update', methods=['POST'])
def trigger_update():
    update_transit_data.delay()
    return jsonify({"status": "Update triggered"}), 202

if __name__ == '__main__':
    app.run(debug=True)
