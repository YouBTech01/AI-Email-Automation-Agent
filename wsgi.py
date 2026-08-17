"""
Standard WSGI Entry Point for Production (Gunicorn, uWSGI, Passenger).
"""
from app import create_app

application = create_app()

if __name__ == '__main__':
    application.run()
