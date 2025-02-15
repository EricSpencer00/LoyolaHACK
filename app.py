import os
import random
import json
import datetime
import math
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from phone import send_sms_via_email
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Configure mail settings (ensure you have these env variables set)
app.config.update({
    "MAIL_SERVER": "smtp.gmail.com",
    "MAIL_PORT": 587,
    "MAIL_USERNAME": os.getenv('MAIL_USERNAME'),
    "MAIL_PASSWORD": os.getenv('MAIL_PASSWORD'),
    "MAIL_DEFAULT_SENDER": os.getenv('MAIL_DEFAULT_SENDER')
})

# Configure your database (here we use SQLite for demonstration)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///cta_tracker.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# In-memory storage for OTPs.
OTPS = {}   # keyed by phone number

# ------------------------
# Database Model
# ------------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    phone_number = db.Column(db.String(20), unique=True, nullable=False)
    carrier = db.Column(db.String(20))
    home_lat = db.Column(db.Float)
    home_lng = db.Column(db.Float)
    favorite_lines = db.Column(db.Text)  # Stored as JSON list
    notification_settings = db.Column(db.Text)  # Stored as JSON object

    def get_favorites(self):
        if self.favorite_lines:
            return json.loads(self.favorite_lines)
        return []

    def set_favorites(self, fav_list):
        self.favorite_lines = json.dumps(fav_list)

    def get_notification_settings(self):
        if self.notification_settings:
            return json.loads(self.notification_settings)
        return {}

    def set_notification_settings(self, settings):
        self.notification_settings = json.dumps(settings)

# ------------------------
# Helper Functions
# ------------------------
def generate_otp():
    """Generate a random 6-digit OTP."""
    return str(random.randint(100000, 999999))

def get_current_user():
    phone = session.get("phone_number")
    if phone:
        return User.query.filter_by(phone_number=phone).first()
    return None

def haversine(lat1, lng1, lat2, lng2):
    # approximate radius of earth in miles
    R = 3958.8  
    dLat = math.radians(lat2 - lat1)
    dLng = math.radians(lng2 - lng1)
    a = math.sin(dLat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dLng/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

# ------------------------
# Routes & API Endpoints
# ------------------------
@app.route("/")
def index():
    """
    The landing page shows the map first.
    If the user is logged in, display the dashboard.
    Otherwise, show the sign in page.
    """
    if session.get("authenticated"):
        return redirect(url_for("dashboard"))
    return render_template("signin.html")

@app.route("/dashboard")
def dashboard():
    user = get_current_user()
    if not user:
        return redirect(url_for("index"))
    return render_template("dashboard.html", user=user, favorite_lines=user.get_favorites())

@app.route("/api/send_otp", methods=["POST"])
def send_otp():
    data = request.get_json()
    phone_number = data.get("phone_number")
    carrier = data.get("carrier")
    if not phone_number or not carrier:
        return jsonify({"status": "error", "message": "Phone number and carrier required."})
    
    otp = generate_otp()
    OTPS[phone_number] = otp

    try:
        send_sms_via_email(
            to_number=phone_number,
            carrier=carrier,
            subject="Your OTP Code",
            body=f"Your OTP is {otp}",
            app_config=app.config
        )
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route("/api/verify_otp", methods=["POST"])
def verify_otp():
    data = request.get_json()
    phone_number = data.get("phone_number")
    otp = data.get("otp")
    # Allow a test OTP ("123456") for debugging.
    if OTPS.get(phone_number) == otp or otp == "123456":
        session["authenticated"] = True
        session["phone_number"] = phone_number
        # Retrieve or create the user
        user = User.query.filter_by(phone_number=phone_number).first()
        if not user:
            user = User(
                phone_number=phone_number,
                carrier=data.get("carrier"),
                home_lat=None,
                home_lng=None,
                favorite_lines=json.dumps([]),
                notification_settings=json.dumps({"time": 10})
            )
            db.session.add(user)
            db.session.commit()
        return jsonify({"status": "success"})
    else:
        return jsonify({"status": "error", "message": "Incorrect OTP."})

@app.route("/api/search_routes")
def search_routes():
    lat = float(request.args.get("lat", 41.8781))
    lng = float(request.args.get("lng", -87.6298))
    query = request.args.get("q", "").lower()
    
    # Dummy list of routes with their approximate coordinates (for demonstration)
    routes = [
        {"name": "Blue Line", "lat": 41.881, "lng": -87.627},
        {"name": "Red Line", "lat": 41.875, "lng": -87.630},
        {"name": "Green Line", "lat": 41.883, "lng": -87.640},
        {"name": "Orange Line", "lat": 41.870, "lng": -87.620}
    ]
    
    matching_routes = []
    for route in routes:
        if query in route["name"].lower():
            distance = haversine(lat, lng, route["lat"], route["lng"])
            if distance <= 1.5:
                route["distance"] = distance
                matching_routes.append(route)
    
    return jsonify(matching_routes)

@app.route("/api/set_home", methods=["POST"])
def set_home():
    user = get_current_user()
    if not user:
        return jsonify({"status": "error", "message": "Not authenticated."})
    data = request.get_json()
    user.home_lat = data.get("lat")
    user.home_lng = data.get("lng")
    db.session.commit()
    return jsonify({"status": "success", "message": "Home location updated."})

@app.route("/api/add_favorite", methods=["POST"])
def add_favorite():
    user = get_current_user()
    if not user:
        return jsonify({"status": "error", "message": "Not authenticated."})
    data = request.get_json()
    line = data.get("line")
    if not line:
        return jsonify({"status": "error", "message": "No transit line provided."})
    
    favorites = user.get_favorites()
    if line in favorites:
        return jsonify({"status": "error", "message": "Already added."})
    
    favorites.append(line)
    user.set_favorites(favorites)
    db.session.commit()
    return jsonify({"status": "success", "message": "Favorite added."})

@app.route("/api/remove_favorite", methods=["POST"])
def remove_favorite():
    user = get_current_user()
    if not user:
        return jsonify({"status": "error", "message": "Not authenticated."})
    data = request.get_json()
    line = data.get("line")
    favorites = user.get_favorites()
    if line in favorites:
        favorites.remove(line)
        user.set_favorites(favorites)
        db.session.commit()
        return jsonify({"status": "success", "message": "Favorite removed."})
    return jsonify({"status": "error", "message": "Favorite not found."})

@app.route("/api/set_notification", methods=["POST"])
def set_notification():
    user = get_current_user()
    if not user:
        return jsonify({"status": "error", "message": "Not authenticated."})
    data = request.get_json()
    settings = user.get_notification_settings()
    time_val = data.get("notification_settings", {}).get("time")
    if time_val:
        settings["time"] = time_val
    # Update contact info if provided.
    phone = data.get("phone_number")
    carrier = data.get("carrier")
    if phone:
        user.phone_number = phone
    if carrier:
        user.carrier = carrier
    user.set_notification_settings(settings)
    db.session.commit()
    return jsonify({"status": "success", "message": "Notification settings updated."})

@app.route("/api/realtime")
def realtime():
    """
    Simulate returning real-time transit data.
    In a production app, query a transit API here.
    """
    transit_type = request.args.get("type")
    dummy_data = []
    if transit_type == "bus":
        dummy_data = [
            {"lat": 41.880, "lng": -87.630, "line": "22"},
            {"lat": 41.882, "lng": -87.627, "line": "36"}
        ]
    elif transit_type == "train":
        dummy_data = [
            {"lat": 41.875, "lng": -87.628, "line": "Red"},
            {"lat": 41.878, "lng": -87.620, "line": "Blue"}
        ]
    return jsonify(dummy_data)

# ------------------------
# Run the App
# ------------------------
if __name__ == "__main__":
    # Uncomment the next line to create the tables on first run.
    # with app.app_context():
    #     db.create_all()
    app.run(debug=True)
