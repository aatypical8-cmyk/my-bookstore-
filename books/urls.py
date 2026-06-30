from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.book_list, name='book_list'),
    path('book/<int:pk>/', views.book_detail, name='book_detail'),
    path('register/', views.register, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('my-library/', views.my_library, name='my_library'),
    path('profile/', views.profile, name='profile'),
    path('become-author/', views.become_author, name='become_author'),
    path('author-dashboard/', views.author_dashboard, name='author_dashboard'),
    path('upload-book/', views.upload_book, name='upload_book'),

    path('purchase/<int:pk>/', views.purchase_book, name='purchase_book'),
    path('book/<int:book_id>/read/', views.read_online, name='read_online'),
    path('request-payment/<int:pk>/', views.request_payment, name='request_payment'),
    path('confirm-payment/<int:pk>/', views.confirm_payment, name='confirm_payment'),
    path('pending-payments/', views.pending_payments, name='pending_payments'),
    path('edit-book/<int:pk>/', views.edit_book, name='edit_book'),
    path('delete-book/<int:pk>/', views.delete_book, name='delete_book'),
    path('edit-profile/', views.edit_profile, name='edit_profile'),
    path('author/<str:username>/', views.author_profile, name='author_profile'),
]