"""
cPanel & Phusion Passenger WSGI Bridge.
This script initializes Python path, virtualenv (if present), and exposes the application object.
"""
import sys
import os

# Insert application root directory into sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# Switch working directory to base directory
os.chdir(BASE_DIR)

# Virtual environment auto-detection for cPanel Python App Manager
# If virtualenv python is used by passenger, standard imports will work.
# If virtualenv path needs manual activation:
virtualenv_path = os.path.join(BASE_DIR, 'venv')
if not os.path.exists(virtualenv_path):
    # Check parent directory virtualenv standard cPanel location
    parent_dir = os.path.dirname(BASE_DIR)
    alt_venv = os.path.join(parent_dir, 'virtualenv', os.path.basename(BASE_DIR))
    if os.path.exists(alt_venv):
        virtualenv_path = alt_venv

activate_this = os.path.join(virtualenv_path, 'bin', 'activate_this.py')
if os.path.exists(activate_this):
    with open(activate_this) as f:
        exec(f.read(), {'__file__': activate_this})

from app import create_app

# Passenger requires the callable to be named 'application'
application = create_app()
