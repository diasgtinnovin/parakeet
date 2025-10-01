from flask import Blueprint

accounts_bp = Blueprint('accounts', __name__)

from . import routes
