from app import db
from datetime import datetime
import json

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone_number = db.Column(db.String(20))
    carrier = db.Column(db.String(50))
    notification_settings = db.Column(db.Text)
    favorite_lines = db.Column(db.Text)  # New: stores favorite transit lines as JSON
    home_lat = db.Column(db.Float)         # New: user’s home latitude
    home_lng = db.Column(db.Float)         # New: user’s home longitude

    def __repr__(self):
        return f'<User {self.email}>'


# Example TransitData model for storing historical data
class TransitData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    transit_id = db.Column(db.String(50))
    transit_type = db.Column(db.String(20))  # bus or train
    line = db.Column(db.String(20))
    lat = db.Column(db.Float)
    lng = db.Column(db.Float)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return '<TransitData {}>'.format(self.transit_id)
