from flask import Blueprint

emails_bp = Blueprint('emails', __name__)

from . import routes
