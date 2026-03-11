"""Flask application factory and extension initialization."""
import os
from dotenv import load_dotenv
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_mail import Mail
from flask_wtf.csrf import CSRFProtect

# Load environment variables from .env file
load_dotenv()

from config import config

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
mail = Mail()
csrf = CSRFProtect()

login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'


def create_app(config_name=None):
    """Application factory."""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    
    # Get the root path (parent of app folder)
    root_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    app = Flask(__name__, 
                template_folder=os.path.join(root_path, 'templates'),
                static_folder=os.path.join(root_path, 'static'))
    app.config.from_object(config[config_name])
    
    # Ensure upload folder exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    mail.init_app(app)
    csrf.init_app(app)
    
    # Register blueprints
    from app.auth import auth_bp
    from app.applicant import applicant_bp
    from app.hr import hr_bp
    from app.api import api_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(applicant_bp, url_prefix='/applicant')
    app.register_blueprint(hr_bp, url_prefix='/hr')
    app.register_blueprint(api_bp, url_prefix='/api')
    
    # Register main routes
    from app import routes
    app.register_blueprint(routes.main_bp)
    
    # Shell context
    @app.shell_context_processor
    def make_shell_context():
        from app import models
        return {
            'db': db,
            'User': models.User,
            'JobPosting': models.JobPosting,
            'Application': models.Application,
            'Document': models.Document,
            'Shortlist': models.Shortlist,
            'Interview': models.Interview,
            'Offer': models.Offer,
            'AuditLog': models.AuditLog,
        }

    # Inject settings globally into all templates
    from app.models import SystemSettings
    @app.context_processor
    def inject_settings():
        settings = SystemSettings.query.first()
        return dict(settings=settings)

    return app


@login_manager.user_loader
def load_user(user_id):
    """Load user by ID for Flask-Login."""
    from app.models import User
    return User.query.get(int(user_id))
