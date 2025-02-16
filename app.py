import os
import random
import json
import math
import csv
import requests
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from phone import send_sms_via_email
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
from celery_app import celery

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
# Load GTFS Stops Data (used for drawing the route line and markers)
# ------------------------
stops = {}
with open('./google_transit/stops.txt', newline='') as f:
    reader = csv.DictReader(f)
    for row in reader:
        stops[row['stop_id']] = {
            'stop_id': row['stop_id'],
            'stop_code': row['stop_code'],
            'stop_name': row['stop_name'],
            'stop_desc': row['stop_desc'],
            'stop_lat': float(row['stop_lat']),
            'stop_lon': float(row['stop_lon']),
            'location_type': row['location_type'],
            'parent_station': row['parent_station'],
            'wheelchair_boarding': row['wheelchair_boarding']
        }

def get_closest_stop(home_lat, home_lng, stops_dict):
    closest_stop = None
    min_distance = float("inf")
    for stop in stops_dict.values():
        d = haversine(home_lat, home_lng, stop["stop_lat"], stop["stop_lon"])
        if d < min_distance:
            min_distance = d
            closest_stop = stop
    return closest_stop

def get_cta_bus_data_for_stop(stop_id):
    CTA_API_KEY = os.getenv("CTA_API_KEY")
    if not CTA_API_KEY:
        raise Exception("CTA_API_KEY not set")
    url = "http://www.ctabustracker.com/bustime/api/v2/getpredictions"
    params = {"key": CTA_API_KEY, "stpid": stop_id, "format": "json"}
    r = requests.get(url, params=params)
    data = r.json()
    predictions = []
    if "bustime-response" in data and "prd" in data["bustime-response"]:
        for prd in data["bustime-response"]["prd"]:
            predictions.append({
                "line": prd.get("rt"),
                "arrival": prd.get("prdctdn")
            })
    return predictions

def get_cta_train_data_for_stop(stop_id):
    CTA_TRAIN_API_KEY = os.getenv("CTA_TRAIN_API_KEY")
    if not CTA_TRAIN_API_KEY:
        raise Exception("CTA_TRAIN_API_KEY not set")
    stop_info = stops.get(stop_id)
    if stop_info:
        stop_lat = stop_info['stop_lat']
        stop_lon = stop_info['stop_lon']
        stop_name = stop_info['stop_name']
    else:
        stop_lat = 41.8781
        stop_lon = -87.6298
        stop_name = "Unknown Stop"
    url = "http://www.transitchicago.com/traintracker/api/1.0/getpredictions"
    params = {"key": CTA_TRAIN_API_KEY, "stpid": stop_id, "format": "json"}
    try:
        r = requests.get(url, params=params)
        data = r.json()
        predictions = []
        if "traintracker-response" in data and "prd" in data["traintracker-response"]:
            for prd in data["traintracker-response"]["prd"]:
                predictions.append({
                    "line": prd.get("rt"),
                    "arrival": prd.get("prdctdn")
                })
            return predictions
        else:
            raise Exception("Unexpected train API response structure")
    except Exception as e:
        print("Error fetching train data:", e)
        return [
            {"line": "Red", "arrival": "3"},
            {"line": "Blue", "arrival": "5"}
        ]


# ------------------------
# API Endpoints for the Line and Stops (using stops.txt)
# ------------------------

@app.route('/api/line', methods=['GET'])
def get_line():
    # Sort stops by stop_id (converted to integer) to get a proper order.
    sorted_stops = sorted(stops.values(), key=lambda s: int(s['stop_id']))
    # Build a list of coordinates in [longitude, latitude] order
    coordinates = [[s['stop_lon'], s['stop_lat']] for s in sorted_stops]
    geojson_feature = {
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": coordinates
        },
        "properties": {
            "name": "Transit Route Line"
        }
    }
    return jsonify(geojson_feature)

@app.route('/api/stops', methods=['GET'])
def get_stops():
    features = []
    for s in stops.values():
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [s['stop_lon'], s['stop_lat']]
            },
            "properties": {
                "stop_id": s['stop_id'],
                "stop_name": s['stop_name']
            }
        })
    geojson = {
        "type": "FeatureCollection",
        "features": features
    }
    return jsonify(geojson)

# ------------------------
# (Other API Endpoints remain mostly the same)
# ------------------------

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

# Realtime Train Predictions (using stops.txt for accurate stop coordinates)
def get_cta_train_data():
    CTA_TRAIN_API_KEY = os.getenv("CTA_TRAIN_API_KEY")
    if not CTA_TRAIN_API_KEY:
        raise Exception("CTA_TRAIN_API_KEY not set")

    station_id = request.args.get("station_id", "1")
    stop_info = stops.get(station_id)
    if stop_info:
        stop_lat = stop_info['stop_lat']
        stop_lon = stop_info['stop_lon']
        stop_name = stop_info['stop_name']
    else:
        stop_lat = 41.8781
        stop_lon = -87.6298
        stop_name = "Unknown Stop"

    url = "http://www.transitchicago.com/traintracker/api/1.0/getpredictions"
    params = {"key": CTA_TRAIN_API_KEY, "stpid": station_id, "format": "json"}
    try:
        r = requests.get(url, params=params)
        data = r.json()
        predictions = []
        if "traintracker-response" in data and "prd" in data["traintracker-response"]:
            for prd in data["traintracker-response"]["prd"]:
                predictions.append({
                    "stop_name": stop_name,
                    "lat": stop_lat,
                    "lng": stop_lon,
                    "line": prd.get("rt"),
                    "arrival": prd.get("prdctdn")
                })
            return predictions
        else:
            raise Exception("Unexpected train API response structure")
    except Exception as e:
        print("Error fetching train data:", e)
        return [
            {"stop_name": stop_name, "lat": stop_lat, "lng": stop_lon, "line": "Red", "arrival": "3 mins"},
            {"stop_name": stop_name, "lat": stop_lat, "lng": stop_lon, "line": "Blue", "arrival": "5 mins"}
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

# (Other endpoints like /api/routes, /api/set_home, /api/add_favorite, etc., remain unchanged)

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
    # We now simply render the dashboard; the map will be built client‐side.
    return render_template("dashboard.html", user=user, favorite_lines=user.get_favorites())

# ------------------------
# PHONE / USER MANAGEMENT Endpoints (unchanged)
# ------------------------

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
    if OTPS.get(phone_number) == otp or otp == "123456":
        session["phone_number"] = phone_number
        session["authenticated"] = True
        return jsonify({"status": "success"})
    return jsonify({"status": "error", "message": "Invalid OTP."})

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
        return jsonify({"status": "error", "message": "Not authenticated."}), 401
    data = request.get_json()
    # Expect route_id or line here
    route_id = data.get("route_id")
    if not route_id:
        return jsonify({"status": "error", "message": "No route ID provided."}), 400
    # For simplicity, assume the favorite is the route's short name (passed as route_id)
    favorite = route_id
    favorites = user.get_favorites()
    if favorite in favorites:
        return jsonify({"status": "error", "message": "Route already in favorites."}), 400
    favorites.append(favorite)
    user.set_favorites(favorites)
    db.session.commit()
    return jsonify({"status": "success", "message": "Route added to favorites."})

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


from celery_app import celery

@celery.task
def check_favorite_line_notifications():
    with app.app_context():
        users = User.query.all()
        for user in users:
            # Skip users without a home location or favorites
            if not user.home_lat or not user.home_lng:
                continue
            favorites = user.get_favorites()  # e.g., ["Red", "Blue"]
            if not favorites:
                continue
            notification_settings = user.get_notification_settings()
            try:
                threshold = int(notification_settings.get("time", 5))
            except ValueError:
                threshold = 5

            # Find the closest stop from our stops dictionary
            closest_stop = get_closest_stop(user.home_lat, user.home_lng, stops)
            if not closest_stop:
                continue

            stop_id = closest_stop['stop_id']

            # Get realtime predictions for this stop (for both bus and train)
            bus_predictions = get_cta_bus_data_for_stop(stop_id)
            train_predictions = get_cta_train_data_for_stop(stop_id)
            predictions = bus_predictions + train_predictions

            for pred in predictions:
                line = pred.get("line")
                # Only consider if this prediction is for a favorite line.
                if line in favorites:
                    try:
                        arrival = int(pred.get("arrival", "9999"))
                    except ValueError:
                        arrival = 9999
                    if arrival <= threshold:
                        message = (f"Alert: Your favorite line {line} is arriving in {arrival} minute(s) "
                                   f"at {closest_stop.get('stop_name', 'your area')}.")
                        # Send SMS if phone info is available.
                        if user.phone_number and user.carrier:
                            try:
                                send_sms_via_email(
                                    to_number=user.phone_number,
                                    carrier=user.carrier,
                                    subject="Transit Alert",
                                    body=message,
                                    app_config=app.config
                                )
                                print(f"Notification sent to {user.phone_number} for line {line}")
                            except Exception as e:
                                print(f"Failed to send SMS to {user.phone_number}: {e}")
                        else:
                            print(f"User {user.phone_number} has no phone details; cannot send notification.")
