from flask_sqlalchemy import SQLAlchemy
import json
from app import app

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///cta_tracker.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    phone_number = db.Column(db.String(20), unique=True, nullable=False)
    carrier = db.Column(db.String(20))
    home_lat = db.Column(db.Float)
    home_lng = db.Column(db.Float)
    favorite_lines = db.Column(db.Text)  # JSON encoded list
    notification_settings = db.Column(db.Text)  # JSON encoded settings

    def set_favorites(self, fav_list):
        self.favorite_lines = json.dumps(fav_list)
    def get_favorites(self):
        return json.loads(self.favorite_lines or '[]')
