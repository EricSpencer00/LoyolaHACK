from flask import Flask, render_template, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from config import Config
from celery import Celery
import datetime
import random

app = Flask(__name__)
app.config.from_object(Config)
db = SQLAlchemy(app)

# Initialize Celery
def make_celery(app):
    celery = Celery(app.import_name, broker=app.config['CELERY_BROKER_URL'])
    celery.conf.update(app.config)
    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)
    celery.Task = ContextTask
    return celery

celery = make_celery(app)

# Index route
@app.route('/')
def index():
    return render_template('index.html')

# API endpoint for real-time transit data (dummy implementation)
@app.route('/api/realtime', methods=['GET'])
def get_realtime():
    # Replace with real CTA API calls and data processing logic
    dummy_data = [
        {
            "id": 1,
            "lat": 41.8781 + random.uniform(-0.01, 0.01),
            "lng": -87.6298 + random.uniform(-0.01, 0.01),
            "type": "bus",
            "line": "22"
        },
        {
            "id": 2,
            "lat": 41.8781 + random.uniform(-0.01, 0.01),
            "lng": -87.6298 + random.uniform(-0.01, 0.01),
            "type": "train",
            "line": "Red"
        }
    ]
    return jsonify(dummy_data)

# API endpoint for predictive analytics (dummy ML predictions)
@app.route('/api/predictions', methods=['GET'])
def get_predictions():
    # Replace with your ML model prediction logic
    dummy_predictions = [
        {
            "id": 1,
            "predicted_arrival": (datetime.datetime.utcnow() + datetime.timedelta(minutes=5)).isoformat() + "Z",
            "confidence": 0.85,
            "line": "22"
        },
        {
            "id": 2,
            "predicted_arrival": (datetime.datetime.utcnow() + datetime.timedelta(minutes=7)).isoformat() + "Z",
            "confidence": 0.80,
            "line": "Red"
        }
    ]
    return jsonify(dummy_predictions)

# Example Celery task for periodic updates
@celery.task
def update_transit_data():
    # This task would pull data from CTA APIs and update your database
    print("Updating transit data...")
    return "Data updated"

# Route to trigger background update manually (for testing)
@app.route('/trigger-update', methods=['POST'])
def trigger_update():
    update_transit_data.delay()
    return jsonify({"status": "Update triggered"}), 202

if __name__ == '__main__':
    app.run(debug=True)
