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

# Configure mail settings (for OTPs)
app.config.update({
    "MAIL_SERVER": "smtp.gmail.com",
    "MAIL_PORT": 465,  # SSL Port
    "MAIL_USE_TLS": False,
    "MAIL_USE_SSL": True,
    "MAIL_USERNAME": os.getenv('MAIL_USERNAME'),
    "MAIL_PASSWORD": os.getenv('MAIL_PASSWORD'),
    "MAIL_DEFAULT_SENDER": os.getenv('MAIL_DEFAULT_SENDER')
})

# Configure SQLite database
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
    R = 3958.8  # Radius in miles
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
def load_routes():
    routes = []
    with open('google_transit/routes.txt', newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            routes.append({
                "route_id": row["route_id"],
                "short_name": row["route_short_name"].strip('"'),
                "long_name": row["route_long_name"].strip('"'),
                "color": row["route_color"]
            })
    return routes

routes_data = load_routes()

# ------------------------
# API Endpoints
# ------------------------

# Endpoint: Return GTFS shapes as GeoJSON with attached route info
def build_route_by_shape():
    # For demonstration, assume route_id "1" is mapped to shape_id "66800095"
    mapping = {}
    for route in routes_data:
        if route["route_id"] == "1":
            mapping["66800095"] = route
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
            "geometry": {"type": "LineString", "coordinates": coordinates},
            "properties": {
                "shape_id": shape_id,
                "route": route_by_shape.get(shape_id, {})
            }
        }
        features.append(feature)
    geojson = {"type": "FeatureCollection", "features": features}
    return jsonify(geojson)

# Endpoint: Realtime Bus Predictions via CTA Bus Tracker API
def get_cta_bus_data():
    CTA_API_KEY = os.getenv("CTA_API_KEY")
    if not CTA_API_KEY:
        raise Exception("CTA_API_KEY not set")
    stop_id = request.args.get("stop_id", "4002")
    url = "http://www.ctabustracker.com/bustime/api/v2/getpredictions"
    params = {"key": CTA_API_KEY, "stpid": stop_id, "format": "json"}
    r = requests.get(url, params=params)
    data = r.json()

    # Use user's home coordinates if available; otherwise, default values.
    user = get_current_user()
    if user and user.home_lat is not None and user.home_lng is not None:
        home_lat = user.home_lat
        home_lng = user.home_lng
    else:
        home_lat = 41.880
        home_lng = -87.630

    predictions = []
    if "bustime-response" in data and "prd" in data["bustime-response"]:
        for prd in data["bustime-response"]["prd"]:
            predictions.append({
                "lat": home_lat,
                "lng": home_lng,
                "line": prd.get("rt"),
                "arrival": prd.get("prdctdn")
            })
    return predictions

# Endpoint: Realtime Train Predictions (using CTA_TRAIN_API_KEY)
def get_cta_train_data():
    CTA_TRAIN_API_KEY = os.getenv("CTA_TRAIN_API_KEY")
    if not CTA_TRAIN_API_KEY:
        raise Exception("CTA_TRAIN_API_KEY not set")

    # Use user's home coordinates if available; otherwise, default values.
    user = get_current_user()
    if user and user.home_lat is not None and user.home_lng is not None:
        home_lat = user.home_lat
        home_lng = user.home_lng
    else:
        home_lat = 41.880
        home_lng = -87.630

    station_id = request.args.get("station_id", "301")
    url = "http://www.transitchicago.com/traintracker/api/1.0/getpredictions"
    params = {"key": CTA_TRAIN_API_KEY, "stpid": station_id, "format": "json"}
    try:
        r = requests.get(url, params=params)
        data = r.json()
        predictions = []
        if "traintracker-response" in data and "prd" in data["traintracker-response"]:
            for prd in data["traintracker-response"]["prd"]:
                predictions.append({
                    "lat": home_lat,
                    "lng": home_lng,
                    "line": prd.get("rt"),
                    "arrival": prd.get("prdctdn")
                })
            return predictions
        else:
            raise Exception("Unexpected train API response structure")
    except Exception as e:
        print("Error fetching train data:", e)
        # Return simulated data using home coordinates
        return [
            {"lat": home_lat, "lng": home_lng, "line": "Red", "arrival": "3 mins"},
            {"lat": home_lat, "lng": home_lng, "line": "Blue", "arrival": "5 mins"}
        ]

@app.route("/api/realtime")
def realtime():
    transit_type = request.args.get("type")
    if transit_type == "bus":
        try:
            return jsonify(get_cta_bus_data())
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    elif transit_type == "train":
        try:
            return jsonify(get_cta_train_data())
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    else:
        return jsonify({"error": "Invalid transit type"}), 400

# Endpoint: Search Routes based on location and query
@app.route("/api/routes")
def search_routes():
    lat = float(request.args.get("lat", 41.8781))
    lng = float(request.args.get("lng", -87.6298))
    query = request.args.get("q", "").lower()
    matching_routes = []
    for route in routes_data:
        if query in route["short_name"].lower() or query in route["long_name"].lower():
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
                    "color": route["color"],
                    "route_id": route["route_id"]
                })
    return jsonify(matching_routes)

# Endpoint: Get Next Stops for a Route based on User Location
@app.route("/api/route_stops", methods=["GET"])
def route_stops():
    route_id = request.args.get("route_id")
    try:
        user_lat = float(request.args.get("lat"))
        user_lng = float(request.args.get("lng"))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid or missing home coordinates."}), 400

    # For demonstration, use route_id "1" -> shape_id "66800095"
    shape_id = "66800095" if route_id == "1" else None
    if not shape_id or shape_id not in shapes:
        return jsonify({"error": "No shape found for this route."}), 404

    pts = shapes[shape_id]
    min_index = 0
    min_dist = float("inf")
    for i, p in enumerate(pts):
        d = haversine(user_lat, user_lng, p["lat"], p["lon"])
        if d < min_dist:
            min_dist = d
            min_index = i
    stops_to_show = pts[min_index:min_index+4]
    return jsonify(stops_to_show)

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
    if not phone_number or not otp:
        return jsonify({"status": "error", "message": "Phone number and OTP required."})
    if OTPS.get(phone_number) == otp:
        session["phone_number"] = phone_number
        session["authenticated"] = True
        return jsonify({"status": "success"})
    return jsonify({"status": "error", "message": "Invalid OTP."})

# Endpoint: Set Home Location
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

# Endpoint: Add Favorite Route
@app.route("/api/add_favorite", methods=["POST"])
def add_favorite():
    user = get_current_user()
    if not user:
        return jsonify({"status": "error", "message": "Not authenticated."}), 401
    data = request.get_json()
    route_id = data.get("route_id")
    if not route_id:
        return jsonify({"status": "error", "message": "No route ID provided."}), 400
    route = next((r for r in routes_data if r["route_id"] == route_id), None)
    if not route:
        return jsonify({"status": "error", "message": "Route not found."}), 404
    favorite = route["short_name"]
    favorites = user.get_favorites()
    if favorite in favorites:
        return jsonify({"status": "error", "message": "Route already in favorites."}), 400
    favorites.append(favorite)
    user.set_favorites(favorites)
    db.session.commit()
    return jsonify({"status": "success", "message": "Route added to favorites."})

# Endpoint: Remove Favorite
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

# Endpoint: Set Notification Settings
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

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
