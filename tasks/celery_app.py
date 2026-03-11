"""Celery application configuration."""
from celery import Celery


def make_celery(app=None):
    """Create Celery instance with Flask app context."""
    celery = Celery(
        'tasks',
        broker='redis://localhost:6379/0',
        backend='redis://localhost:6379/0',
        include=['tasks.jobs']
    )
    
    celery.conf.update(
        task_serializer='json',
        accept_content=['json'],
        result_serializer='json',
        timezone='UTC',
        enable_utc=True,
        task_track_started=True,
        task_time_limit=30 * 60,  # 30 minutes
        worker_prefetch_multiplier=1,
    )
    
    if app:
        celery.conf.update(
            broker_url=app.config.get('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
            result_backend=app.config.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0'),
        )
        
        class ContextTask(celery.Task):
            """Task with Flask app context."""
            def __call__(self, *args, **kwargs):
                with app.app_context():
                    return self.run(*args, **kwargs)
        
        celery.Task = ContextTask
    
    return celery


# Create celery instance
celery = make_celery()
