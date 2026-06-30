#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys

import django.utils.encoding
if not hasattr(django.utils.encoding, 'python_2_unicode_compatible'):
    django.utils.encoding.python_2_unicode_compatible = lambda x: x

import django.utils.translation
if not hasattr(django.utils.translation, 'ugettext_lazy'):
    from django.utils.translation import gettext_lazy as ugettext_lazy
    django.utils.translation.ugettext_lazy = ugettext_lazy


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bookstore.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
