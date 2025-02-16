import os
import random
import json
import datetime
import math
import csv
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from phone import send_verification_code, check_verification_code
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv

load_dotenv(override=True)

app = Flask(__name__)
app.secret_key = os.urandom(24)

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
    R = 3958.8  
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

@app.route("/api/send_verification", methods=["POST"])
def send_verification():
    data = request.get_json()
    phone_number = data.get("phone_number")
    if not phone_number:
        return jsonify({"status": "error", "message": "Phone number is required."})
    
    try:
        send_verification_code(phone_number)
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route("/api/verify_code", methods=["POST"])
def verify_code():
    data = request.get_json()
    phone_number = data.get("phone_number")
    code = data.get("code")
    if not phone_number or not code:
        return jsonify({"status": "error", "message": "Phone number and code are required."})
    
    if check_verification_code(phone_number, code):
        session["authenticated"] = True
        session["phone_number"] = phone_number
        return jsonify({"status": "success"})
    else:
        return jsonify({"status": "error", "message": "Invalid verification code."})    
@app.route("/api/search_routes")
def search_routes():
    lat = float(request.args.get("lat", 41.8781))
    lng = float(request.args.get("lng", -87.6298))
    query = request.args.get("q", "").lower()
    
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
    phone = data.get("phone_number")
    if phone:
        user.phone_number = phone
    user.set_notification_settings(settings)
    db.session.commit()
    return jsonify({"status": "success", "message": "Notification settings updated."})

@app.route("/api/realtime")
def realtime():
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

if __name__ == "__main__":
    # Uncomment the lines below on first run to create the tables:
    # with app.app_context():
    #     db.create_all()
    app.run(debug=True)
