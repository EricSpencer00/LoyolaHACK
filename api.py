from flask import Blueprint, jsonify, request
from extensions import db
from flask import current_app, session
import random
import json

api_bp = Blueprint('api', __name__)

@api_bp.route('/send_otp', methods=['POST'])
def send_otp():
    from phone import send_sms_via_email
    data = request.get_json()
    phone_number = data.get("phone_number")
    carrier = data.get("carrier")
    if not phone_number or not carrier:
        return jsonify({"status": "error", "message": "Phone number and carrier are required"}), 400

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
            app_config=current_app.config
        )
        return jsonify({"status": "success", "message": "OTP sent"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@api_bp.route('/verify_otp', methods=['POST'])
def verify_otp():
    from models import User
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

@api_bp.route('/set_home', methods=['POST'])
def set_home():
    from models import User
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

@api_bp.route('/add_favorite', methods=['POST'])
def add_favorite():
    from models import User
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

@api_bp.route('/remove_favorite', methods=['POST'])
def remove_favorite():
    from models import User
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

@api_bp.route('/set_notification', methods=['POST'])
def set_notification():
    from models import User
    data = request.get_json()
    phone_number = data.get("phone_number")
    user = User.query.filter_by(phone_number=phone_number).first()
    if user:
        user.notification_settings = json.dumps(data.get("notification_settings", {}))
        db.session.commit()
        return jsonify({"status": "success", "message": "Notification settings updated"})
    return jsonify({"status": "error", "message": "User not found"}), 404

@api_bp.route('/realtime', methods=['GET'])
def realtime():
    from models import TransitData
    """Return transit data (bus or train) filtered by proximity to the user’s home."""
    transit_type = request.args.get('type')
    user_phone = session.get('user_phone')
    if user_phone:
        from models import TransitData  # ensure TransitData is imported
        # Get user's home location
        from models import User
        user = User.query.filter_by(phone_number=user_phone).first()
        if user and user.home_lat and user.home_lng:
            lat, lng = user.home_lat, user.home_lng
            # Define a bounding box (e.g., ±0.05 degrees)
            delta = 0.05
            transit_data = TransitData.query.filter(
                TransitData.transit_type == transit_type,
                TransitData.lat.between(lat - delta, lat + delta),
                TransitData.lng.between(lng - delta, lng + delta)
            ).all()
            result = [{'lat': d.lat, 'lng': d.lng, 'line': d.line} for d in transit_data]
            return jsonify(result)
    # If no home is set or no data found, return an empty list.
    return jsonify([])
