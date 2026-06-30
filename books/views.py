import time
import token

import order
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
import requests
from django.conf import settings

from .models import Book, Purchase, Profile, PaymentConfirmation


# ====================== MAIN VIEWS ======================

def book_list(request):
    books = Book.objects.all()
    return render(request, 'books/book_list.html', {'books': books})


def book_detail(request, pk):
    book = get_object_or_404(Book, pk=pk)

    has_purchased = False
    if request.user.is_authenticated:
        has_purchased = Purchase.objects.filter(buyer=request.user, book=book).exists()

    return render(request, 'books/book_detail.html', {
        'book': book,
        'has_purchased': has_purchased
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
def become_author(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        profile.author_request_pending = True
        profile.save()
        messages.success(request, "Your author request has been submitted.")
        return redirect('profile')
    return render(request, 'books/become_author.html', {'profile': profile})


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


@login_required
def upload_book(request):
    if not request.user.profile.is_author:
        messages.error(request, "Only approved authors can upload books.")
        return redirect('profile')

    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        price = request.POST.get('price')
        cover_image = request.FILES.get('cover_image')
        ebook_file = request.FILES.get('ebook_file')

        if title and description and price:
            Book.objects.create(
                title=title,
                author=request.user,
                description=description,
                price=price,
                cover_image=cover_image,
                ebook_file=ebook_file
            )
            messages.success(request, f"Book '{title}' uploaded successfully!")
            return redirect('author_dashboard')
        else:
            messages.error(request, "Please fill all required fields.")

    return render(request, 'books/upload_book.html')


# ====================== PESAPAL PAYMENT ======================

@login_required
def purchase_book(request, pk):
    book = get_object_or_404(Book, pk=pk)

    if Purchase.objects.filter(buyer=request.user, book=book).exists():
        messages.info(request, "You already own this book!")
        return redirect('book_detail', pk=book.pk)

    # 1. Authenticate and get a Token from Pesapal V3 Sandbox
    auth_url = "https://pesapal.com"
    auth_headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    auth_data = {
        "consumer_key": settings.PESAPAL_CONSUMER_KEY,
        "consumer_secret": settings.PESAPAL_CONSUMER_SECRET
    }

    auth_response = requests.post(auth_url, headers=auth_headers, json=auth_data)

    # Check if the token was successfully generated
    if auth_response.status_code != 200:
        return HttpResponse(f"Pesapal Auth Error: Status Code {auth_response.status_code}. Details: {auth_response.text}")

    auth_url = "https://cybapi.pesapal.com/v3/api/Auth/RequestToken"

    # 2. Register the IPN (Instant Payment Notification) URL
    # Pesapal needs an endpoint to tell your app when payment succeeds
    ipn_url = "https://pesapal.com"
    ipn_headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }
    ipn_data = {
        "url": f"https://{request.get_host()}/pesapal/callback/",
        "ipn_notification_type": "GET"
    }

    ipn_response = requests.post(ipn_url, headers=ipn_headers, json=ipn_data)
    ipn_result = ipn_response.json()
    ipn_id = ipn_result.get("ipn_id")

    # 3. Submit the Checkout Order
    order_url = "https://pesapal.com"
    order_headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }

    order_data = {
        "id": f"BOOK_{book.id}_{request.user.id}",
        "amount": float(book.price),
        "description": f"Payment for {book.title}",
        "callback_url": f"http://{request.get_host()}/pesapal/callback/",
        "notification_id": ipn_id,
        "billing_address": {
            "email_address": request.user.email if request.user.email else "guest@example.com",
            "first_name": request.user.first_name if request.user.first_name else "Guest",
            "last_name": request.user.last_name if request.user.last_name else "Buyer"
        }
    }

    order_response = requests.post(order_url, headers=order_headers, json=order_data)
    order_result = order_response.json()

    # 4. Extract the Redirect URL and Route the User
    if "redirect_url" in order_result:
        return redirect(order_result["redirect_url"])
    else:
        return HttpResponse(f"Pesapal Order Error: {order_result}")


# ====================== OTHER ======================
@login_required
def read_online(request, book_id):
    book = get_object_or_404(Book, pk=book_id)
    if not Purchase.objects.filter(buyer=request.user, book=book).exists():
        messages.error(request, "You must purchase this book to read it.")
        return redirect('book_detail', pk=book.pk)

    if not book.ebook_file:
        messages.error(request, "No ebook file available.")
        return redirect('book_detail', pk=book.pk)

    return redirect(book.ebook_file.url)


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


@login_required
def edit_book(request, pk):
    book = get_object_or_404(Book, pk=pk)

    if book.author != request.user:
        messages.error(request, "You can only edit your own books.")
        return redirect('author_dashboard')

    if request.method == 'POST':
        book.title = request.POST.get('title', book.title)
        book.description = request.POST.get('description', book.description)
        book.price = request.POST.get('price', book.price)

        if 'cover_image' in request.FILES:
            book.cover_image = request.FILES['cover_image']
        if 'ebook_file' in request.FILES:
            book.ebook_file = request.FILES['ebook_file']

        book.save()
        messages.success(request, f"Book '{book.title}' updated successfully!")
        return redirect('author_dashboard')

    return render(request, 'books/edit_book.html', {'book': book})

@login_required
def delete_book(request, pk):
    book = get_object_or_404(Book, pk=pk)

    if book.author != request.user:
        messages.error(request, "You can only delete your own books.")
        return redirect('author_dashboard')

    if request.method == 'POST':
        book.delete()
        messages.success(request, "Book deleted successfully.")
        return redirect('author_dashboard')

    return render(request, 'books/delete_book.html', {'book': book})


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
