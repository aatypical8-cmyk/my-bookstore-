from django.apps import AppConfig


class BooksConfig(AppConfig):
    name = 'books'

    def ready(self):
        # Move the import INSIDE the method
        from django.contrib.auth.models import User

        try:
            if not User.objects.filter(username='Gerald').exists():
                User.objects.create_superuser(
                    username='Titus',
                    email='aatypical8@gmail.com',
                    password='omwash1234'
                )
        except:
            pass