# celery_worker.py
from app import app, db
from celery import Celery

def make_celery(app):
    celery = Celery(app.import_name, broker=app.config.get("CELERY_BROKER_URL", "redis://localhost:6379/0"))
    celery.conf.update(app.config)
    TaskBase = celery.Task
    class ContextTask(TaskBase):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return TaskBase.__call__(self, *args, **kwargs)
    celery.Task = ContextTask
    return celery

celery = make_celery(app)

if __name__ == '__main__':
    with app.app_context():
        celery.start()
