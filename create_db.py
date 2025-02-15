# create_db.py
from app import create_app
from extensions import db

app = create_app()
with app.app_context():  # This creates the necessary application context.
    db.drop_all()      # (Optional) Drops all existing tables.
    db.create_all()    # Recreates all tables based on your current models.
    print("Database has been recreated!")
