"""ASGI entry point:  uvicorn bankchat.main:app --host 0.0.0.0 --port 8000

Settings come from the environment (and app/.env); see app/.env.example.
"""

from bankchat.app_factory import create_app

app = create_app()
