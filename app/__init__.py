from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS
from celery import Celery
import os

db = SQLAlchemy()
migrate = Migrate()
celery = Celery()

def create_app():
    app = Flask(__name__)
    
    # Configuration
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Connection pooling configuration
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_size': 10,           # Number of connections to maintain in pool
        'max_overflow': 20,        # Additional connections beyond pool_size
        'pool_timeout': 30,        # Timeout when getting connection from pool
        'pool_recycle': 3600,      # Recycle connections after 1 hour
        'pool_pre_ping': True,     # Validate connections before use
        'echo': False              # Set to True for SQL debugging
    }
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    CORS(app)
    
    # Configure Celery
    celery.conf.update(
        broker_url=os.getenv('CELERY_BROKER_URL'),
        result_backend=os.getenv('CELERY_RESULT_BACKEND'),
        task_serializer='json',
        accept_content=['json'],
        result_serializer='json',
        timezone='UTC',
        enable_utc=True,
    )
    
    # Register blueprints
    from app.api.accounts import accounts_bp
    from app.api.emails import emails_bp
    from app.api.analytics import analytics_bp
    from app.api.oauth import oauth_bp
    
    app.register_blueprint(accounts_bp, url_prefix='/api/accounts')
    app.register_blueprint(emails_bp, url_prefix='/api/emails')
    app.register_blueprint(analytics_bp, url_prefix='/api/analytics')
    app.register_blueprint(oauth_bp, url_prefix='/api/oauth')
    
    return app
