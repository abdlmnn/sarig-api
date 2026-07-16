from django.contrib import admin
from .models import Category, MedicineReference, Product, ProductReference

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


@admin.register(MedicineReference)
class MedicineReferenceAdmin(admin.ModelAdmin):
    list_display = ("registration_number", "generic_name", "brand_name", "dosage_strength", "classification", "expiry_date", "is_active")
    list_filter = ("classification", "requires_prescription", "is_active", "expiry_date")
    search_fields = ("registration_number", "generic_name", "brand_name", "pharmacologic_category")


@admin.register(ProductReference)
class ProductReferenceAdmin(admin.ModelAdmin):
    list_display = ("name", "brand_name", "barcode", "vertical", "product_type", "unit_type", "is_active")
    list_filter = ("vertical", "product_type", "unit_type", "is_active")
    search_fields = ("name", "brand_name", "barcode", "description")
