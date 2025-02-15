# models.py
from extensions import db
from datetime import datetime
import json

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # email = db.Column(db.String(120), unique=True, nullable=True)  # Add this if missing
    phone_number = db.Column(db.String(15), unique=True, nullable=False)
    carrier = db.Column(db.String(50), nullable=True)
    notification_settings = db.Column(db.Text, nullable=True)
    favorite_lines = db.Column(db.Text, nullable=True)
    home_lat = db.Column(db.Float, nullable=True)
    home_lng = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<User {self.phone_number}>'

class TransitData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    transit_id = db.Column(db.String(50))
    transit_type = db.Column(db.String(20))  # bus or train
    line = db.Column(db.String(20))
    lat = db.Column(db.Float)
    lng = db.Column(db.Float)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<TransitData {self.transit_id}>'
