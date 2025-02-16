import os
import random
import json
import math
import csv
import requests
from collections import defaultdict
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from phone import send_sms_via_email
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv

load_dotenv(override=True)

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Configure mail settings (if still used for OTPs)
app.config.update({
    "MAIL_SERVER": "smtp.gmail.com",
    "MAIL_PORT": 465,
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
OTPS = {}

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
    R = 3958.8  # miles
    dLat = math.radians(lat2 - lat1)
    dLng = math.radians(lng2 - lng1)
    a = math.sin(dLat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dLng/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

# ------------------------
# Load GTFS Shapes Data
# ------------------------
shapes = {}
with open('./google_transit/shapes.txt', newline='') as f:
    reader = csv.DictReader(f)
    for row in reader:
        if 'shape_id' not in row:
            continue
        shape_id = row['shape_id']
        point = {
            'lat': float(row['shape_pt_lat']),
            'lon': float(row['shape_pt_lon']),
            'seq': int(row['shape_pt_sequence']),
            'dist': float(row['shape_dist_traveled']) if row['shape_dist_traveled'] else None
        }
        shapes.setdefault(shape_id, []).append(point)
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
            "route_type": row["route_type"],
            "route_url": row["route_url"],
            "color": row["route_color"],
            "text_color": row["route_text_color"]
        })

# For demonstration, simple mapping: route_id "1" -> shape_id "66800095"
route_to_shape = {
    "1": "66800095"
}

def build_route_by_shape():
    mapping = {}
    for route in routes_data:
        shape_id = route_to_shape.get(route["route_id"])
        if shape_id:
            mapping[shape_id] = route
    return mapping

@app.route('/api/gtfs_routes', methods=['GET'])
def gtfs_routes():
    route_by_shape = build_route_by_shape()
    features = []
    for shape_id, points in shapes.items():
        points.sort(key=lambda p: p['seq'])
        coordinates = [[p["lon"], p["lat"]] for p in points]
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": coordinates
            },
            "properties": {
                "shape_id": shape_id,
                "route": route_by_shape.get(shape_id, {})
            }
        }
        features.append(feature)
    geojson = {"type": "FeatureCollection", "features": features}
    return jsonify(geojson)

# ------------------------
# Realtime Predictions Endpoints
# ------------------------

def get_cta_bus_data():
    CTA_API_KEY = os.getenv("CTA_API_KEY")
    if not CTA_API_KEY:
        raise Exception("CTA_API_KEY not set")
    stop_id = request.args.get("stop_id", "4002")  # Default stop id
    url = "http://www.ctabustracker.com/bustime/api/v2/getpredictions"
    params = {"key": CTA_API_KEY, "stpid": stop_id, "format": "json"}
    r = requests.get(url, params=params)
    data = r.json()
    predictions = []
    if "bustime-response" in data and "prd" in data["bustime-response"]:
        for prd in data["bustime-response"]["prd"]:
            predictions.append({
                "lat": 41.880,      # Use actual stop coordinates if available
                "lng": -87.630,
                "line": prd.get("rt"),
                "arrival": prd.get("prdctdn")
            })
    return predictions

def get_cta_train_data():
    CTA_TRAIN_API_KEY = os.getenv("CTA_TRAIN_API_KEY")
    if not CTA_TRAIN_API_KEY:
        raise Exception("CTA_TRAIN_API_KEY not set")
    # Default station id for demonstration; replace with real station IDs as needed.
    station_id = request.args.get("station_id", "301")
    # Hypothetical CTA Train Tracker API endpoint (adjust as per actual docs)
    url = "http://www.transitchicago.com/traintracker/api/1.0/getpredictions"
    params = {"key": CTA_TRAIN_API_KEY, "stpid": station_id, "format": "json"}
    r = requests.get(url, params=params)
    data = r.json()
    predictions = []
    if "traintracker-response" in data and "prd" in data["traintracker-response"]:
        for prd in data["traintracker-response"]["prd"]:
            predictions.append({
                "lat": 41.880,      # Dummy values; ideally, use actual station coordinates
                "lng": -87.630,
                "line": prd.get("rt"),
                "arrival": prd.get("prdctdn")
            })
    return predictions

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

# ------------------------
# Other Endpoints (unchanged)
# ------------------------
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
    route_id = data.get("route_id")
    if route_id:
        route = next((r for r in routes_data if r["route_id"] == route_id), None)
        if not route:
            return jsonify({"status": "error", "message": "Route not found."})
        favorite = route["short_name"]
    else:
        favorite = data.get("line")
    if not favorite:
        return jsonify({"status": "error", "message": "No transit line provided."})
    favorites = user.get_favorites()
    if favorite in favorites:
        return jsonify({"status": "error", "message": "Already added."})
    favorites.append(favorite)
    user.set_favorites(favorites)
    db.session.commit()
    return jsonify({"status": "success", "message": "Favorite added."})

@app.route("/api/remove_favorite", methods=["POST"])
def remove_favorite():
    user = get_current_user()
    if not user:
        return jsonify({"status": "error", "message": "Not authenticated."})
    data = request.get_json()
    favorite = data.get("line")
    favorites = user.get_favorites()
    if favorite in favorites:
        favorites.remove(favorite)
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
