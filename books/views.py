import time
import token
from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, HttpResponse
import json
from django.conf import settings
from django.contrib import messages
from .models import Book, Purchase, Profile, PaymentConfirmation
from django.contrib.auth.decorators import login_required
import requests
from .forms import BookForm
from django.http import HttpResponse
from .models import Profile

from django.shortcuts import render
from .models import Book


def book_list(view_self, request):
    category_filter = request.GET.get('category')

    if category_filter:
        books = Book.objects.filter(category__iexact=category_filter)
    else:
        books = Book.objects.all()

    # Get a unique list of all categories for the filter buttons/dropdown
    categories = Book.objects.values_list('category', flat=True).distinct()

    context = {
        'books': books,
        'categories': categories,
        'selected_category': category_filter,
    }
    return render(request, 'books/book_list.html', context)


def book_detail(request, pk):
    book = get_object_or_404(Book, pk=pk)

    # Fetch the author's profile
    # Replace 'AuthorProfile' with the actual name of your profile model
    author_profile = Profile.objects.filter(user=book.author).first()

    has_purchased = False
    if request.user.is_authenticated:
        has_purchased = Purchase.objects.filter(buyer=request.user, book=book).exists()

    return render(request, 'books/book_detail.html', {
        'book': book,
        'has_purchased': has_purchased,
        'author_profile': author_profile,  # Pass this to the template
    })


# ====================== AUTH ======================

def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f"Welcome {user.username}!")
            return redirect('book_list')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.capitalize()}: {error}")
    else:
        form = UserCreationForm()
    return render(request, 'books/register.html', {'form': form})


def user_logout(request):
    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect('book_list')


# ====================== PROFILE & AUTHOR ======================

@login_required
def profile(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    books_uploaded = Book.objects.filter(author=request.user)
    purchases = Purchase.objects.filter(buyer=request.user).select_related('book')

    context = {
        'profile': profile,
        'books_uploaded': books_uploaded,
        'purchases': purchases,
    }
    return render(request, 'books/profile.html', context)


@login_required
def author_dashboard(request):
    if not request.user.profile.is_author:
        messages.warning(request, "You need to be an approved author.")
        return redirect('profile')

    books = Book.objects.filter(author=request.user)
    total_books = books.count()
    sales = Purchase.objects.filter(book__author=request.user)
    total_sales = sales.count()
    total_earnings = sales.aggregate(total=models.Sum('amount_paid'))['total'] or 0

    context = {
        'books': books,
        'total_books': total_books,
        'total_sales': total_sales,
        'total_earnings': total_earnings,
    }
    return render(request, 'books/author_dashboard.html', context)


import cloudinary.uploader  # Make sure this import is present

@login_required
def upload_book(request):
    if not request.user.profile.is_author:
        messages.error(request, "Only approved authors can upload books.")
        return redirect('profile')

    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        price = request.POST.get('price')

        # 1. Grab files from the request payload safely
        cover_image_file = request.FILES.get('cover_image')
        ebook_file_obj = request.FILES.get('ebook_file')

        if title and description and price:
            uploaded_cover_url = None
            uploaded_ebook_url = None

            # 2. Upload the cover image to Cloudinary first
            if cover_image_file:
                cover_upload = cloudinary.uploader.upload(cover_image_file)
                uploaded_cover_url = cover_upload.get('secure_url')

            # 3. Stream the heavy PDF to Cloudinary securely using resource_type="auto"
            if ebook_file_obj:
                ebook_upload = cloudinary.uploader.upload(
                    ebook_file_obj,
                    resource_type="auto"  # <-- Prevents connection drops on large PDFs
                )
                uploaded_ebook_url = ebook_upload.get('secure_url')

            # 4. Save the string URLs to the database record instead of the raw data block
            Book.objects.create(
                title=title,
                description=description,
                price=price,
                author=request.user,
                cover_image=uploaded_cover_url,
                ebook_file=uploaded_ebook_url
            )

            messages.success(request, f"Book '{title}' uploaded successfully!")
            return redirect('author_dashboard')
        else:
            messages.error(request, "Please fill all required fields.")

    return render(request, 'books/upload_book.html')

import requests
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Book, Purchase

@login_required
def read_online(request, book_id):
    book = get_object_or_404(Book, pk=book_id)

    if not Purchase.objects.filter(buyer=request.user, book=book).exists():
        messages.error(request, "You must purchase this book to read it.")
        return redirect('book_detail', pk=book.pk)

    if book.ebook_file:
        # Get the initial URL
        raw_url = book.ebook_file.url if hasattr(book.ebook_file, 'url') else str(book.ebook_file)

        # If the URL contains a second 'https://res.cloudinary.com' inside it,
        # we extract only the part from the last occurrence of 'https'
        if raw_url.count('https://res.cloudinary.com') > 1:
            clean_url = 'https' + raw_url.split('https')[-1]
        else:
            clean_url = raw_url

        return redirect(clean_url)

    messages.error(request, "No ebook file available.")
    return redirect('book_detail', pk=book.pk)

@login_required
def my_library(request):
    purchases = Purchase.objects.filter(buyer=request.user).select_related('book')
    return render(request, 'books/my_library.html', {'purchases': purchases})

@login_required
def request_payment(request, pk):
    book = get_object_or_404(Book, pk=pk)

    if Purchase.objects.filter(buyer=request.user, book=book).exists():
        messages.info(request, "You already own this book!")
        return redirect('book_detail', pk=book.pk)

    if request.method == 'POST':
        phone_number = request.POST.get('phone_number')

        if phone_number:
            PaymentConfirmation.objects.create(
                buyer=request.user,
                book=book,
                phone_number=phone_number,
                amount=book.price,
                status='pending'
            )
            messages.success(request, "Payment request sent to author. They will confirm soon.")
            return redirect('book_detail', pk=book.pk)
        else:
            messages.error(request, "Please enter your phone number.")

    return render(request, 'books/request_payment.html', {'book': book})

@login_required
def confirm_payment(request, pk):
    confirmation = get_object_or_404(PaymentConfirmation, pk=pk)

    if request.user != confirmation.book.author:
        messages.error(request, "You can only confirm payments for your own books.")
        return redirect('profile')

    confirmation.status = 'confirmed'
    confirmation.save()

    # Automatically create Purchase record
    Purchase.objects.create(
        buyer=confirmation.buyer,
        book=confirmation.book,
        amount_paid=confirmation.amount,
        transaction_id="MANUAL_" + str(int(time.time()))
    )

    messages.success(request, f"Payment confirmed! {confirmation.buyer.username} can now access {confirmation.book.title}.")
    return redirect('pending_payments')


@login_required
def pending_payments(request):
    if not request.user.profile.is_author:
        messages.error(request, "Only authors can view pending payments.")
        return redirect('profile')

    pending = PaymentConfirmation.objects.filter(
        book__author=request.user,
        status='pending'
    ).select_related('buyer', 'book').order_by('-created_at')

    return render(request, 'books/pending_payments.html', {'pending': pending})

def edit_book(request, pk):
    book = get_object_or_404(Book, pk=pk)
    if request.method == 'POST':
        # You MUST include request.FILES here
        form = BookForm(request.POST, request.FILES, instance=book)
        if form.is_valid():
            form.save()
            return redirect('book_list')
    else:
        form = BookForm(instance=book)
    return render(request, 'books/edit_book.html', {'form': form})


from django.db import transaction  # Add this import
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages


@login_required
def delete_book(request, pk):
    book = get_object_or_404(Book, pk=pk)

    if book.author != request.user:
        messages.error(request, "You can only delete your own books.")
        return redirect('author_dashboard')

    if request.method == 'POST':
        # Wrapping in transaction.atomic ensures the database operation is complete
        with transaction.atomic():
            book.delete()
        messages.success(request, "Book deleted successfully.")
        return redirect('author_dashboard')

    return render(request, 'books/delete_book.html', {'book': book})


def download_book(request, book_id):
    book = get_object_or_404(Book, pk=book_id)

    # Check purchase status
    if not Purchase.objects.filter(buyer=request.user, book=book).exists():
        messages.error(request, "You must purchase this to download.")
        return redirect('book_detail', pk=book.pk)

    # Get the value directly from the database field
    raw_file_value = str(book.ebook_file)

    # If the URL is "doubled," we extract the clean part
    if raw_file_value.count('https://res.cloudinary.com') > 1:
        # Splits the string and takes the last part, which is the correct URL
        final_url = 'https' + raw_file_value.split('https')[-1]
    else:
        final_url = raw_file_value

    return redirect(final_url)

@login_required
def edit_profile(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        profile.bio = request.POST.get('bio', profile.bio)
        profile.phone_number = request.POST.get('phone_number', profile.phone_number)
        profile.mpesa_number = request.POST.get('mpesa_number', profile.mpesa_number)

        if 'profile_picture' in request.FILES:
            profile.profile_picture = request.FILES['profile_picture']

        profile.save()
        messages.success(request, "Profile updated successfully!")
        return redirect('profile')

    return render(request, 'books/edit_profile.html', {'profile': profile})


def author_profile(request, username):
    author = get_object_or_404(User, username=username)
    profile = author.profile
    books = Book.objects.filter(author=author)

    context = {
        'author': author,
        'profile': profile,
        'books': books,
    }
    return render(request, 'books/author_profile.html', context)


from django.contrib.auth.models import User
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required


@login_required
def author_requests(request):
    if not request.user.is_superuser:
        return redirect('home')  # Only let you in if you are a superuser

    # Assuming you have a model 'AuthorRequest'
    requests = AuthorRequest.objects.filter(status='pending')
    return render(request, 'approve_authors.html', {'requests': requests})


from django.shortcuts import render, redirect, get_object_or_404
from .models import AuthorRequest  # Ensure you import your model


@login_required
def approve_author(request, request_id):
    if not request.user.is_superuser:
        return redirect('home')

    req = get_object_or_404(AuthorRequest, id=request_id)
    if request.method == 'POST':
        user = req.user
        user.is_author = True  # Adjust this to match your model field
        user.save()
        req.status = 'approved'
        req.save()
    return redirect('author_requests')

# In views.py
def request_author_status(request):
    if request.method == 'POST':
        # This creates the request record in the database
        AuthorRequest.objects.create(user=request.user, status='pending')
        return redirect('home') # Or a thankyou page
    return render(request, 'request_form.html')

def become_author(request):
    if request.method == 'POST':
        AuthorRequest.objects.get_or_create(user=request.user, status='pending')
        messages.success(request, "Your request to become an author has been sent!") # Success flash
        return redirect('book_list')
    return render(request, 'books/become_author.html')


def preview_book(request, book_id):
    book = get_object_or_404(Book, pk=book_id)

    if not book.ebook_file:
        messages.error(request, "Preview not available.")
        return redirect('book_detail', pk=book.pk)

    # Use the clean URL logic we established
    raw_url = str(book.ebook_file)
    if raw_url.count('https://res.cloudinary.com') > 1:
        clean_url = 'https' + raw_url.split('https')[-1]
    else:
        clean_url = raw_url

    # We append #page=1 to the URL to tell the browser to start at the first page
    # You can also tell them in the UI that they can read up to 5 pages
    preview_url = f"{clean_url}#page=1"

    return render(request, 'books/preview.html', {'book': book, 'preview_url': preview_url})


