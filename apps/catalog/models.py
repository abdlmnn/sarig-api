import uuid
from django.db import models
from apps.vendors.models import Store


class Category(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    store = models.ForeignKey(
        Store, on_delete=models.CASCADE, related_name="categories"
    )
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, blank=True)
    description = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to="categories/", null=True, blank=True)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ["order", "name"]
        unique_together = ("store", "slug")

    def __str__(self):
        return f"{self.name} ({self.store.name})"


class Product(models.Model):
    class ProductType(models.TextChoices):
        FOOD = "FOOD", "Food"
        MEDICINE = "MEDICINE", "Medicine"
        GROCERY = "GROCERY", "Grocery"
        GENERAL = "GENERAL", "General"

    class InventoryMode(models.TextChoices):
        NONE = "NONE", "None"
        TRACKED = "TRACKED", "Tracked"

    class UnitType(models.TextChoices):
        ITEM = "ITEM", "Item"
        SERVING = "SERVING", "Serving"
        PACK = "PACK", "Pack"
        BOTTLE = "BOTTLE", "Bottle"

    class MedicineForm(models.TextChoices):
        NONE = "NONE", "None"
        TABLET = "TABLET", "Tablet"
        CAPSULE = "CAPSULE", "Capsule"
        SYRUP = "SYRUP", "Syrup"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, related_name="products"
    )
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=280, blank=True)
    description = models.TextField(blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to="products/", null=True, blank=True)
    product_type = models.CharField(max_length=20, choices=ProductType.choices, default=ProductType.FOOD)
    brand_name = models.CharField(max_length=120, blank=True, default="")
    generic_name = models.CharField(max_length=120, blank=True, default="")
    dosage = models.CharField(max_length=80, blank=True, default="")
    medicine_form = models.CharField(max_length=20, choices=MedicineForm.choices, default=MedicineForm.NONE)
    medicine_reference_id = models.UUIDField(null=True, blank=True)
    requires_prescription = models.BooleanField(default=False)
    unit_type = models.CharField(max_length=20, choices=UnitType.choices, default=UnitType.ITEM)
    inventory_mode = models.CharField(max_length=20, choices=InventoryMode.choices, default=InventoryMode.NONE)
    preparation_time_minutes = models.PositiveIntegerField(null=True, blank=True)
    # --- The Super-App Inventory Upgrades ---
    is_available = models.BooleanField(default=True) # Manual override (e.g., "Kitchen closed")
    track_inventory = models.BooleanField(default=False) # False for coffee/food, True for groceries
    stock_quantity = models.PositiveIntegerField(default=0, blank=True, null=True) # The actual count

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} - ₱{self.price}"

    @property
    def in_stock(self):
        """A smart helper to check if a customer can actually buy this right now."""
        if not self.is_available or not self.is_active:
            return False
        if self.track_inventory and self.stock_quantity <= 0:
            return False
        return True


class ModifierGroup(models.Model):
    """Groups options together. Example: 'Choose your Size', 'Add Extra Toppings'"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="modifier_groups")
    name = models.CharField(max_length=100)
    is_required = models.BooleanField(default=False) # Must they pick a size? True.
    max_selections = models.PositiveIntegerField(default=1) # Limit how many toppings they can pick

    def __str__(self):
        return f"{self.name} (for {self.product.name})"


class ModifierItem(models.Model):
    """The actual options. Example: 'Large', 'Extra Cheese'"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(ModifierGroup, on_delete=models.CASCADE, related_name="items")
    name = models.CharField(max_length=100)
    extra_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00) # Adds ₱15 for extra cheese
    is_available = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} (+₱{self.extra_price})"
