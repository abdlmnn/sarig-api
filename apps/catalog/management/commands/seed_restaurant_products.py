from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils.text import slugify

from apps.catalog.models import Category, InventoryMode, Product, ProductType, UnitType
from apps.vendors.models import Store


RESTAURANT_CATEGORIES = [
    ("Rice Meals", "rice-meals"),
    ("Sandwiches", "sandwiches"),
    ("Pasta", "pasta"),
    ("Snacks", "snacks"),
    ("Drinks", "drinks"),
    ("Desserts", "desserts"),
]

RESTAURANT_PRODUCTS = [
    ("Chicken Biryani", "Rice Meals", "Spiced rice meal with chicken", "120.00", True),
    ("Beef Rendang Rice", "Rice Meals", "Slow-cooked beef with steamed rice", "145.00", True),
    ("Chicken Pastil", "Rice Meals", "Rice meal wrapped with shredded chicken", "45.00", True),
    ("Tuna Pastil", "Rice Meals", "Rice meal with tuna flakes", "42.00", True),
    ("Beef Burger", "Sandwiches", "Beef patty with cheese and house sauce", "95.00", True),
    ("Chicken Sandwich", "Sandwiches", "Grilled chicken sandwich with lettuce", "85.00", True),
    ("Beef Shawarma", "Sandwiches", "Beef wrap with garlic sauce", "85.00", False),
    ("Chicken Alfredo", "Pasta", "Cream pasta with grilled chicken", "130.00", True),
    ("Tuna Pasta", "Pasta", "Tomato pasta with tuna flakes", "110.00", True),
    ("Garlic Bread", "Snacks", "Toasted bread with garlic butter", "45.00", True),
    ("Cheese Fries", "Snacks", "Fries with cheese sauce", "75.00", True),
    ("Chicken Wings", "Snacks", "Six-piece wings with sauce", "140.00", False),
    ("Iced Tea", "Drinks", "House blend iced tea", "35.00", True),
    ("Mango Shake", "Drinks", "Cold mango shake", "75.00", True),
    ("Bottled Water", "Drinks", "500ml drinking water", "20.00", True),
    ("Leche Flan", "Desserts", "Caramel custard dessert", "50.00", True),
    ("Pastel Slice", "Desserts", "Soft bread dessert slice", "38.00", True),
    ("Chocolate Cake Slice", "Desserts", "Chocolate cake with frosting", "70.00", False),
]


class Command(BaseCommand):
    help = "Seed restaurant categories and products for merchant catalog testing."

    def add_arguments(self, parser):
        parser.add_argument("--store-id", dest="store_id", default="")
        parser.add_argument("--username", dest="username", default="")

    def handle(self, *args, **options):
        store = self.get_store(options)
        categories = self.seed_categories(store)
        created = self.seed_products(categories)
        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {created} restaurant products for {store.name}."
            )
        )

    def get_store(self, options):
        queryset = Store.objects.filter(is_active=True)
        if options["store_id"]:
            return queryset.get(id=options["store_id"])
        if options["username"]:
            return queryset.get(owner__username=options["username"])
        return queryset.filter(vertical__slug="restaurant").order_by("name").first()

    def seed_categories(self, store):
        categories = {}
        for index, (name, slug) in enumerate(RESTAURANT_CATEGORIES):
            category, _ = Category.objects.update_or_create(
                store=store,
                slug=slug,
                defaults={
                    "name": name,
                    "description": "",
                    "is_active": True,
                    "order": index,
                },
            )
            categories[name] = category
        return categories

    def seed_products(self, categories):
        created = 0
        for name, category_name, description, price, is_available in RESTAURANT_PRODUCTS:
            Product.objects.update_or_create(
                category=categories[category_name],
                slug=slugify(name),
                defaults={
                    "name": name,
                    "description": description,
                    "price": Decimal(price),
                    "product_type": ProductType.FOOD,
                    "brand_name": "",
                    "generic_name": "",
                    "dosage": "",
                    "medicine_form": "",
                    "requires_prescription": False,
                    "unit_type": UnitType.PIECE,
                    "inventory_mode": InventoryMode.NONE,
                    "preparation_time_minutes": 15,
                    "is_available": is_available,
                    "track_inventory": False,
                    "stock_quantity": None,
                    "is_active": True,
                },
            )
            created += 1
        return created
