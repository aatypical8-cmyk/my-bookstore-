from django import forms
from .models import Book

class BookForm(forms.ModelForm):
    class Meta:
        model = Book
        fields = ['title', 'description', 'price', 'cover_image', 'ebook_file'] # Make sure these fields match your models.py