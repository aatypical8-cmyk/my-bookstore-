from django.apps import AppConfig


class BooksConfig(AppConfig):
    name = 'books'

    def ready(self):
        from django.contrib.auth.models import User
        try:
            # Create a brandnew account specifically for admin
            if not User.objects.filter(username='myadmin').exists():
                u = User.objects.create_superuser(
                    username='myadmin',
                    email='admin@example.com',
                    password='Password123!'
                )
                u.save()
        except:
            pass