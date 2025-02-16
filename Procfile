web: gunicorn app:app
worker: celery -A celery_app.celery worker --loglevel=info
beat: celery -A celery_app.celery beat --loglevel=info
