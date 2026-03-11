"""HR/Manager dashboard blueprint."""
from flask import Blueprint

hr_bp = Blueprint('hr', __name__)

from app.hr import routes
