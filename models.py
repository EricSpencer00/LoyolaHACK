from app import db
from datetime import datetime

# Example User model (expand with Flask-Login as needed)
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    favorite_routes = db.Column(db.Text)

    def __repr__(self):
        return '<User {}>'.format(self.email)

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
