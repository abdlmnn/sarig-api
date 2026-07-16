import uuid
from django.db import models
from apps.vendors.models import BusinessVertical, Store


class ProductType(models.TextChoices):
    FOOD = "food", "Food"
    MEDICINE = "medicine", "Medicine"
    GROCERY = "grocery", "Grocery"
    GENERAL = "general", "General"


class InventoryMode(models.TextChoices):
    NONE = "none", "No stock tracking"
    SIMPLE_STOCK = "simple_stock", "Simple stock"


class UnitType(models.TextChoices):
    PIECE = "piece", "Piece"
    PACK = "pack", "Pack"
    BOTTLE = "bottle", "Bottle"
    CAN = "can", "Can"
    KILO = "kilo", "Kilo"
    GRAM = "gram", "Gram"
    LITER = "liter", "Liter"
    SACHET = "sachet", "Sachet"
    BOX = "box", "Box"
    DOZEN = "dozen", "Dozen"
    TABLET = "tablet", "Tablet"
    CAPSULE = "capsule", "Capsule"


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


class CategoryTemplate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vertical = models.ForeignKey(
        BusinessVertical, on_delete=models.CASCADE, related_name="category_templates"
    )
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["vertical__slug", "order", "name"]
        unique_together = ("vertical", "slug")

    def __str__(self):
        return f"{self.name} ({self.vertical.slug})"


class ProductReference(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vertical = models.ForeignKey(
        BusinessVertical,
        on_delete=models.CASCADE,
        related_name="product_references",
    )
    name = models.CharField(max_length=255)
    brand_name = models.CharField(max_length=255, blank=True)
    barcode = models.CharField(max_length=80, blank=True, db_index=True)
    description = models.TextField(blank=True)
    product_type = models.CharField(
        max_length=20,
        choices=ProductType.choices,
        default=ProductType.GROCERY,
        db_index=True,
    )
    unit_type = models.CharField(max_length=20, choices=UnitType.choices, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    source = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["vertical__slug", "name", "brand_name"]
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["brand_name"]),
            models.Index(fields=["barcode"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.vertical.slug})"


class Product(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, related_name="products"
    )
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=280, blank=True)
    sku = models.CharField(max_length=80, blank=True, db_index=True)
    description = models.TextField(blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to="products/", null=True, blank=True)
    product_type = models.CharField(max_length=20, choices=ProductType.choices, default=ProductType.GENERAL, db_index=True)
    medicine_reference = models.ForeignKey(
        "MedicineReference",
        on_delete=models.SET_NULL,
        related_name="products",
        null=True,
        blank=True,
    )
    unit_type = models.CharField(max_length=20, choices=UnitType.choices, blank=True)
    requires_prescription = models.BooleanField(default=False)
    generic_name = models.CharField(max_length=255, blank=True)
    brand_name = models.CharField(max_length=255, blank=True)
    dosage = models.CharField(max_length=100, blank=True)
    medicine_form = models.CharField(max_length=100, blank=True)
    preparation_time_minutes = models.PositiveIntegerField(null=True, blank=True)
    inventory_mode = models.CharField(max_length=20, choices=InventoryMode.choices, default=InventoryMode.NONE)
    is_available = models.BooleanField(default=True)
    track_inventory = models.BooleanField(default=False)
    stock_quantity = models.PositiveIntegerField(default=None, blank=True, null=True)
    low_stock_threshold = models.PositiveIntegerField(default=5)

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
        if self.track_inventory and (self.stock_quantity is None or self.stock_quantity <= 0):
            return False
        return True

    def save(self, *args, **kwargs):
        if self.track_inventory and self.inventory_mode == InventoryMode.NONE and self.stock_quantity is not None:
            self.inventory_mode = InventoryMode.SIMPLE_STOCK
        self.track_inventory = self.inventory_mode == InventoryMode.SIMPLE_STOCK
        if self.inventory_mode == InventoryMode.NONE:
            self.stock_quantity = None
        if self.product_type != ProductType.MEDICINE:
            self.requires_prescription = False
        super().save(*args, **kwargs)


class MedicineReference(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    registration_number = models.CharField(max_length=80, unique=True, db_index=True)
    product_information = models.CharField(max_length=255, blank=True)
    generic_name = models.CharField(max_length=255)
    brand_name = models.CharField(max_length=255, blank=True)
    dosage_strength = models.CharField(max_length=255, blank=True)
    dosage_form = models.CharField(max_length=255, blank=True)
    classification = models.CharField(max_length=255, blank=True)
    pharmacologic_category = models.CharField(max_length=255, blank=True)
    packaging = models.TextField(blank=True)
    manufacturer = models.CharField(max_length=255, blank=True)
    country_of_origin = models.CharField(max_length=120, blank=True)
    trader = models.CharField(max_length=255, blank=True)
    importer = models.CharField(max_length=255, blank=True)
    distributor = models.CharField(max_length=255, blank=True)
    expiry_date = models.DateField(null=True, blank=True, db_index=True)
    requires_prescription = models.BooleanField(default=False, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    source = models.CharField(max_length=80, default="FDA Philippines")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["generic_name", "brand_name", "registration_number"]
        indexes = [
            models.Index(fields=["generic_name"]),
            models.Index(fields=["brand_name"]),
            models.Index(fields=["classification"]),
        ]

    def __str__(self):
        display_name = self.brand_name or self.generic_name
        return f"{display_name} ({self.registration_number})"


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
