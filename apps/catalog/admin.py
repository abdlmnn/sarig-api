from django.contrib import admin
from .models import Category, Product

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "store", "is_active", "order")
    list_filter = ("store", "is_active")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "price", "is_available", "is_active")
    list_filter = ("category__store", "category", "is_available", "is_active")
    search_fields = ("name", "description")
    prepopulated_fields = {"slug": ("name",)}
