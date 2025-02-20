# wsgi_handler.py
from app import app  # Ensure 'app' is your Flask instance in app.py
from serverless_wsgi import handle_request

def handler(event, context):
    return handle_request(app, event, context)
