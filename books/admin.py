from django.contrib import admin
from .models import Book, Purchase, Profile


# ====================== BOOK ADMIN ======================
@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ['title', 'author', 'price', 'created_at']
    list_filter = ['created_at', 'author']
    search_fields = ['title', 'description']

    # Auto-assign author when creating new book
    def save_model(self, request, obj, form, change):
        if not change:  # Only when creating new book
            obj.author = request.user
        super().save_model(request, obj, form, change)

    # Show only books belonging to current user (unless superuser)
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(author=request.user)


# ====================== OTHER MODELS ======================
@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ['buyer', 'book', 'amount_paid', 'purchased_at']
    list_filter = ['purchased_at']


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'is_author', 'author_request_pending', 'phone_number']
    list_filter = ['is_author', 'author_request_pending']
    search_fields = ['user__username', 'user__email']