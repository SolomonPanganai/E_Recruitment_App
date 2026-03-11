"""Applicant portal blueprint."""
from flask import Blueprint

applicant_bp = Blueprint('applicant', __name__)

from app.applicant import routes
