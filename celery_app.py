import os
from celery import Celery

celery = Celery(__name__,
                broker=os.getenv("CELERY_BROKER_URL"),
                backend=os.getenv("CELERY_RESULT_BACKEND"))

celery.conf.update({
    "broker_url": os.getenv("CELERY_BROKER_URL"),
    "result_backend": os.getenv("CELERY_RESULT_BACKEND")
})
