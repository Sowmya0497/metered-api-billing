# Register Celery app so Django picks it up on startup
from .celery import app as celery_app

__all__ = ('celery_app',)
