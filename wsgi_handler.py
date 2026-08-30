import os
import sys

# Force the current directory into Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mybookstore.settings')

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()