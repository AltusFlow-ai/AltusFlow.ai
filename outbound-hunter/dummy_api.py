"""
dummy_api.py
Empty blueprint registered when NO_AUTH=true.
Auth bypass is handled by auth.py's request_loader — this module just needs to exist.
"""
from flask import Blueprint

dummy_api = Blueprint("dummy_api", __name__)
