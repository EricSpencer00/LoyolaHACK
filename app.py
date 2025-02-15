import json
from flask import Flask, render_template, session, redirect, url_for
from flask_mail import Mail
from config import Config
from api import api_bp
from extensions import db  # Import db from extensions

mail = Mail()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.secret_key = app.config.get("SECRET_KEY", "secret-key")

    db.init_app(app)  # Initialize db with app
    mail.init_app(app)  # Initialize mail with app

    app.register_blueprint(api_bp, url_prefix='/api')

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/dashboard')
    def dashboard():
        from models import User  # Import here to avoid circular import
        user_phone = session.get('user_phone')
        if not user_phone:
            return redirect(url_for('index'))
        user = User.query.filter_by(phone_number=user_phone).first()
        favorites = json.loads(user.favorite_lines) if user.favorite_lines else []
        return render_template('dashboard.html', user=user, favorite_lines=favorites)

    return app


if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        db.drop_all()   # optional: drops any existing tables
        db.create_all() # creates tables based on the current models
    app.run(debug=True)
