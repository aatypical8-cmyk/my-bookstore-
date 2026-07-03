from django.apps import AppConfig
from django.contrib.auth.models import User

class BooksConfig(AppConfig):
    name = 'books'

    def ready(self):
        try:
            if not User.objects.filter(username='Gerald').exists():
                User.objects.create_superuser(
                    username='Gerald',
                    email='aatypical8@gmail.com',
                    password='omwash1234'
                )
        except:
            pass