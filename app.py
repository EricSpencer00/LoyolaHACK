# app.py
import datetime
import random
import json
import os

from flask import Flask, render_template, jsonify, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail
from config import Config
from phone import send_sms_via_email

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = app.config.get("SECRET_KEY", "secret-key")
db = SQLAlchemy(app)
mail = Mail(app)

# ----------------------------
# Models
# ----------------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    phone_number = db.Column(db.String(20), unique=True, nullable=False)
    favorite_lines = db.Column(db.Text, default='[]')
    notification_settings = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def __repr__(self):
        return f"<User {self.phone_number}>"

# ----------------------------
# Routes and Endpoints
# ----------------------------

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/send_otp', methods=['POST'])
def send_otp():
    data = request.get_json()
    phone_number = data.get("phone_number")
    carrier = data.get("carrier")
    
    if not phone_number or not carrier:
        return jsonify({"status": "error", "message": "Phone number and carrier are required"}), 400

    # Generate a 6-digit OTP code.
    otp = random.randint(100000, 999999)
    session['otp'] = str(otp)
    session['phone_number'] = phone_number
    session['carrier'] = carrier

    subject = "Your OTP Code"
    body = f"Your verification code is: {otp}"

    try:
        send_sms_via_email(
            to_number=phone_number,
            carrier=carrier,
            subject=subject,
            body=body,
            app_config=app.config
        )
        return jsonify({"status": "success", "message": "OTP sent"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/verify_otp', methods=['POST'])
def verify_otp():
    data = request.get_json()
    phone_number = data.get("phone_number")
    otp_entered = data.get("otp")
    
    stored_otp = session.get('otp')
    stored_phone = session.get('phone_number')
    
    if not stored_otp or not stored_phone or phone_number != stored_phone:
        return jsonify({"status": "error", "message": "Session expired or invalid phone number"}), 400
    
    if otp_entered == stored_otp:
        user = User.query.filter_by(phone_number=phone_number).first()
        if not user:
            user = User(phone_number=phone_number, favorite_lines='[]')
            db.session.add(user)
            db.session.commit()
        session['user_phone'] = phone_number
        session.pop('otp', None)
        return jsonify({"status": "success"})
    else:
        return jsonify({"status": "error", "message": "Incorrect OTP"}), 400


# Main dashboard route – renders the dashboard template.
@app.route('/dashboard')
def dashboard():
    user_phone = session.get('user_phone')
    if not user_phone:
        return redirect(url_for('index'))
    user = User.query.filter_by(phone_number=user_phone).first()
    # Load favorites from a JSON string; default to an empty list.
    favorite_lines = json.loads(user.favorite_lines) if user.favorite_lines else []
    return render_template('dashboard.html', user=user, favorite_lines=favorite_lines)


@app.route('/api/set_home', methods=['POST'])
def set_home():
    data = request.get_json()
    lat = data.get("lat")
    lng = data.get("lng")
    user_phone = session.get('user_phone')
    if not user_phone:
        return jsonify({"status": "error", "message": "User not logged in"}), 403
    user = User.query.filter_by(phone_number=user_phone).first()
    if user:
        user.home_lat = lat
        user.home_lng = lng
        db.session.commit()
        return jsonify({"status": "success", "message": "Home location updated"})
    return jsonify({"status": "error", "message": "User not found"}), 404

@app.route('/api/add_favorite', methods=['POST'])
def add_favorite():
    data = request.get_json()
    line = data.get("line")
    if not line:
        return jsonify({"status": "error", "message": "No transit line provided"}), 400
    user_phone = session.get('user_phone')
    if not user_phone:
        return jsonify({"status": "error", "message": "User not logged in"}), 403
    user = User.query.filter_by(phone_number=user_phone).first()
    favorites = json.loads(user.favorite_lines) if user.favorite_lines else []
    if line in favorites:
        return jsonify({"status": "error", "message": "Transit line already in favorites"}), 400
    favorites.append(line)
    user.favorite_lines = json.dumps(favorites)
    db.session.commit()
    return jsonify({"status": "success", "message": "Favorite added", "favorites": favorites})

@app.route('/api/remove_favorite', methods=['POST'])
def remove_favorite():
    data = request.get_json()
    line = data.get("line")
    if not line:
        return jsonify({"status": "error", "message": "No transit line provided"}), 400
    user_phone = session.get('user_phone')
    if not user_phone:
        return jsonify({"status": "error", "message": "User not logged in"}), 403
    user = User.query.filter_by(phone_number=user_phone).first()
    favorites = json.loads(user.favorite_lines) if user.favorite_lines else []
    if line not in favorites:
        return jsonify({"status": "error", "message": "Transit line not found in favorites"}), 400
    favorites.remove(line)
    user.favorite_lines = json.dumps(favorites)
    db.session.commit()
    return jsonify({"status": "success", "message": "Favorite removed", "favorites": favorites})

@app.route('/api/set_notification', methods=['POST'])
def set_notification():
    data = request.get_json()
    phone_number = data.get("phone_number")
    user = User.query.filter_by(phone_number=phone_number).first()
    if user:
        user.notification_settings = json.dumps(data.get("notification_settings", {}))
        db.session.commit()
        return jsonify({"status": "success", "message": "Notification settings updated"})
    return jsonify({"status": "error", "message": "User not found"}), 404

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
