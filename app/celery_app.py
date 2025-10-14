from celery import Celery
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def make_celery(app=None):
    celery = Celery(
        app.import_name if app else 'email_warmup_service',
        backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0'),
        broker=os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
    )
    
    # Configure Celery
    celery.conf.update(
        task_serializer='json',                                     
        accept_content=['json'],
        result_serializer='json',
        timezone='UTC',
        enable_utc=True,
        include=['app.tasks.email_tasks'],  # Include the tasks module
    )
    
    if app:
        celery.conf.update(app.config)
        
        class ContextTask(celery.Task):
            def __call__(self, *args, **kwargs):
                # Ensure each task runs within the Flask app context
                with app.app_context():
                    return self.run(*args, **kwargs)
        
        celery.Task = ContextTask
    
    return celery

# Create a single Flask app per worker and bind Celery to it
from app import create_app
_flask_app = create_app()
celery = make_celery(_flask_app)
