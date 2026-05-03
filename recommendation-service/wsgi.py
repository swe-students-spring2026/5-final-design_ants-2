"""WSGI entry point for production servers (gunicorn)."""
from app.main import create_app

application = create_app()
