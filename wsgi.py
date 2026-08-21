import sys
import os

# Set environment variables directly in WSGI file
os.environ['SECRET_KEY'] = 'c9192975ed9d231ca1605ded0afb6041b4d06a34044b0b771c2d9ab4d2a24ceb'
os.environ['FLASK_DEBUG'] = 'false'

# Add the current directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app as application

# For PythonAnywhere, this is the entry point
if __name__ == '__main__':
    application.run()
