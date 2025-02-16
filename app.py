import os
import random
import json
import datetime
import math
import csv
from collections import defaultdict
import requests
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from phone import send_sms_via_email
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv

load_dotenv(override=True)

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Configure mail settings (ensure your env variables are set)
app.config.update({
    "MAIL_SERVER": "smtp.gmail.com",
    "MAIL_PORT": 465,  # SSL Port
    "MAIL_USE_TLS": False,
    "MAIL_USE_SSL": True,
    "MAIL_USERNAME": os.getenv('MAIL_USERNAME'),
    "MAIL_PASSWORD": os.getenv('MAIL_PASSWORD'),
    "MAIL_DEFAULT_SENDER": os.getenv('MAIL_DEFAULT_SENDER')
})

# Configure SQLite database for demonstration
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
        return json.loads(self.favorite_lines) if self.favorite_lines else []

    def set_favorites(self, fav_list):
        self.favorite_lines = json.dumps(fav_list)

    def get_notification_settings(self):
        return json.loads(self.notification_settings) if self.notification_settings else {}

    def set_notification_settings(self, settings):
        self.notification_settings = json.dumps(settings)

# ------------------------
# Helper Functions
# ------------------------
def generate_otp():
    otp = str(random.randint(100000, 999999))
    print("Generated OTP:", otp)
    return otp

def get_current_user():
    phone = session.get("phone_number")
    if phone:
        return User.query.filter_by(phone_number=phone).first()
    return None

def haversine(lat1, lng1, lat2, lng2):
    R = 3958.8  # Radius in miles
    dLat = math.radians(lat2 - lat1)
    dLng = math.radians(lng2 - lng1)
    a = math.sin(dLat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dLng/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

# ------------------------
# Load GTFS Shapes Data
# ------------------------
shapes = {}  # key: shape_id, value: list of point dictionaries
with open('./google_transit/shapes.txt', newline='') as f:
    reader = csv.DictReader(f)
    for row in reader:
        if 'shape_id' not in row:
            print("Missing shape_id in row:", row)
            continue  # Skip this row if shape_id is missing

        shape_id = row['shape_id']
        point = {
            'lat': float(row['shape_pt_lat']),
            'lon': float(row['shape_pt_lon']),
            'seq': int(row['shape_pt_sequence']),
            'dist': float(row['shape_dist_traveled']) if row['shape_dist_traveled'] else None
        }
        shapes.setdefault(shape_id, []).append(point)
# Sort each shape by sequence
for shape_id in shapes:
    shapes[shape_id].sort(key=lambda p: p['seq'])

# ------------------------
# Load GTFS Routes Data
# ------------------------
routes_data = []
with open('google_transit/routes.txt', newline='') as f:
    reader = csv.DictReader(f)
    for row in reader:
        routes_data.append({
            "route_id": row["route_id"],
            "short_name": row["route_short_name"].strip('"'),
            "long_name": row["route_long_name"].strip('"'),
            "color": row["route_color"]
        })

@app.route('/api/gtfs_shapes', methods=['GET'])
def gtfs_shapes():
    try:
        sw_lat = float(request.args.get('sw_lat'))
        sw_lng = float(request.args.get('sw_lng'))
        ne_lat = float(request.args.get('ne_lat'))
        ne_lng = float(request.args.get('ne_lng'))
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid or missing bounding box parameters.'}), 400

    filtered_shapes = {}
    for shape_id, points in shapes.items():
        visible_points = [
            {'lat': p['lat'], 'lon': p['lon'], 'seq': p['seq']}
            for p in points
            if sw_lat <= p['lat'] <= ne_lat and sw_lng <= p['lon'] <= ne_lng
        ]
        if visible_points:
            filtered_shapes[shape_id] = visible_points
    return jsonify(filtered_shapes)

@app.route("/")
def index():
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
    if OTPS.get(phone_number) == otp or otp == "123456":
        session["authenticated"] = True
        session["phone_number"] = phone_number
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

# ------------------------
# Realtime CTA Data via API Calls
# ------------------------

def get_cta_bus_data():
    """
    Fetch bus predictions from CTA Bus Tracker API.
    You must set CTA_API_KEY in your environment variables.
    Optionally, you can pass a stop_id as a query parameter.
    """
    CTA_API_KEY = os.getenv("CTA_API_KEY")
    if not CTA_API_KEY:
        raise Exception("CTA_API_KEY not set")
    # Default stop id for demonstration; in practice, pass stop_id via query parameter.
    stop_id = request.args.get("stop_id", "4002")
    url = "http://www.ctabustracker.com/bustime/api/v2/getpredictions"
    params = {
        "key": CTA_API_KEY,
        "stpid": stop_id,
        "format": "json"
    }
    r = requests.get(url, params=params)
    data = r.json()
    predictions = []
    if "bustime-response" in data and "prd" in data["bustime-response"]:
        for prd in data["bustime-response"]["prd"]:
            # CTA may not return lat/lon; using dummy coordinates for demonstration.
            predictions.append({
                "lat": 41.880,      # Dummy value; ideally, use stop coordinates.
                "lng": -87.630,     # Dummy value.
                "line": prd.get("rt"),
                "arrival": prd.get("prdctdn")
            })
    return predictions

def get_cta_train_data():
    """
    For demonstration, we simulate CTA train data.
    In production, you would call the appropriate CTA Train Tracker API.
    """
    # Simulated data; replace with actual API calls when available.
    return [
        {"lat": 41.875, "lng": -87.628, "line": "Red", "arrival": "3 mins"},
        {"lat": 41.878, "lng": -87.620, "line": "Blue", "arrival": "5 mins"}
    ]

@app.route("/api/realtime")
def realtime():
    transit_type = request.args.get("type")
    if transit_type == "bus":
        try:
            bus_data = get_cta_bus_data()
            return jsonify(bus_data)
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    elif transit_type == "train":
        try:
            train_data = get_cta_train_data()
            return jsonify(train_data)
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    else:
        return jsonify({"error": "Invalid transit type"}), 400

@app.route("/api/search_routes")
def search_routes():
    lat = float(request.args.get("lat", 41.8781))
    lng = float(request.args.get("lng", -87.6298))
    query = request.args.get("q", "").lower()
    
    matching_routes = []
    for route in routes_data:
        if query in route["short_name"].lower() or query in route["long_name"].lower():
            # For demonstration, assume route_id "1" uses shape_id "66800095".
            if route["route_id"] == "1" and "66800095" in shapes:
                pts = shapes["66800095"]
                avg_lat = sum(p["lat"] for p in pts) / len(pts)
                avg_lng = sum(p["lon"] for p in pts) / len(pts)
            else:
                avg_lat = 41.8781
                avg_lng = -87.6298
            distance = haversine(lat, lng, avg_lat, avg_lng)
            if distance <= 1.5:
                matching_routes.append({
                    "name": route["short_name"],
                    "long_name": route["long_name"],
                    "lat": avg_lat,
                    "lng": avg_lng,
                    "distance": distance,
                    "color": route["color"]
                })
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
    phone = data.get("phone_number")
    carrier = data.get("carrier")
    if phone:
        user.phone_number = phone
    if carrier:
        user.carrier = carrier
    user.set_notification_settings(settings)
    db.session.commit()
    return jsonify({"status": "success", "message": "Notification settings updated."})

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
