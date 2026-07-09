import random
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.catalog.models import Category, InventoryMode, Product, ProductType, UnitType
from apps.orders.models import DeliveryMethod, Order, OrderItem, OrderStatus
from apps.users.models import Role, User
from apps.vendors.models import BusinessVertical, Store, StoreDeliveryTime


DEMO_MERCHANT_USERNAME = "demo_merchant"
DEMO_PASSWORD = "Password123!"


class Command(BaseCommand):
    help = "Seed a realistic merchant dashboard demo store with products and many orders."

    def add_arguments(self, parser):
        parser.add_argument(
            "--append",
            action="store_true",
            help="Append orders instead of replacing the demo store orders.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        rng = random.Random(42)
        now = timezone.now()

        merchant = self._user(
            username=DEMO_MERCHANT_USERNAME,
            email="demo.merchant@sarig.local",
            password=DEMO_PASSWORD,
            role_name="Merchant",
            first_name="Sari",
            last_name="Merchant",
        )
        customer_role = Role.objects.get_or_create(name="Customer")[0]
        rider_role = Role.objects.get_or_create(name="Rider")[0]
        customers = [
            self._user(
                username=f"demo_customer_{index:02d}",
                email=f"demo.customer.{index:02d}@sarig.local",
                password=DEMO_PASSWORD,
                role_name=customer_role.name,
                first_name=first,
                last_name=last,
            )
            for index, (first, last) in enumerate(
                [
                    ("Amina", "Pangandaman"),
                    ("Jalal", "Macarambon"),
                    ("Fatima", "Usman"),
                    ("Omar", "Marohomsalic"),
                    ("Nor", "Dimaporo"),
                    ("Salma", "Abedin"),
                    ("Karim", "Sultan"),
                    ("Yasmin", "Ali"),
                    ("Ibrahim", "Musa"),
                    ("Hana", "Basman"),
                    ("Rashid", "Lanto"),
                    ("Mariam", "Malik"),
                ],
                start=1,
            )
        ]
        riders = [
            self._user(
                username=f"demo_rider_{index:02d}",
                email=f"demo.rider.{index:02d}@sarig.local",
                password=DEMO_PASSWORD,
                role_name=rider_role.name,
                first_name=first,
                last_name=last,
            )
            for index, (first, last) in enumerate(
                [("Nasser", "Rider"), ("Adnan", "Courier"), ("Samir", "Express")],
                start=1,
            )
        ]

        vertical = self._restaurant_vertical()
        store, _ = Store.objects.update_or_create(
            owner=merchant,
            name="Sari Sari Restaurant Demo",
            defaults={
                "vertical": vertical,
                "branch_name": "Banggolo",
                "company_email": "merchant.demo@sarig.local",
                "contact_number": "09170000001",
                "delivery_time": StoreDeliveryTime.ALL_DAY,
                "latitude": Decimal("8.003400"),
                "longitude": Decimal("124.283900"),
                "street_address": "Banggolo Poblacion, Marawi City, Lanao del Sur",
                "city": "Marawi City",
                "barangay": "Banggolo Poblacion",
                "province": "Lanao del Sur",
                "postal_code": "9700",
                "pinned_address": "Banggolo Poblacion, Marawi City, Lanao del Sur, Philippines",
                "commission_rate": Decimal("15.00"),
                "is_open": True,
                "is_active": True,
                "auto_accept_orders": False,
                "rating": Decimal("4.80"),
            },
        )

        if not options["append"]:
            Order.objects.filter(store=store).delete()
            Category.objects.filter(store=store).delete()

        products = self._seed_products(store)
        self._seed_orders(store, customers, riders, products, now, rng)

        today_orders = Order.objects.filter(store=store, created_at__date=now.date()).count()
        total_orders = Order.objects.filter(store=store).count()
        self.stdout.write(self.style.SUCCESS("Seeded merchant dashboard demo data."))
        self.stdout.write(f"Merchant login: {DEMO_MERCHANT_USERNAME} / {DEMO_PASSWORD}")
        self.stdout.write(f"Store: {store.name}")
        self.stdout.write(f"Products: {len(products)}")
        self.stdout.write(f"Orders today: {today_orders}")
        self.stdout.write(f"Total demo orders: {total_orders}")

    def _user(self, username, email, password, role_name, first_name, last_name):
        user, created = User.objects.update_or_create(
            username=username,
            defaults={
                "email": email,
                "first_name": first_name,
                "last_name": last_name,
                "is_active": True,
            },
        )
        if created or not user.has_usable_password():
            user.set_password(password)
            user.save(update_fields=["password"])
        role = Role.objects.get_or_create(name=role_name)[0]
        user.roles.add(role)
        return user

    def _restaurant_vertical(self):
        vertical, _ = BusinessVertical.objects.update_or_create(
            slug="restaurant",
            defaults={
                "name": "Restaurant",
                "allowed_product_types": [ProductType.FOOD],
                "requires_license": False,
                "required_documents": ["mayors_permit"],
                "is_active": True,
            },
        )
        return vertical

    def _seed_products(self, store):
        menu = {
            "Rice Meals": [
                ("Chicken Pastil", "Shredded chicken over rice with palapa.", "65.00", 12),
                ("Beef Rendang Rice", "Slow-cooked beef rendang with steamed rice.", "145.00", 18),
                ("Chicken Biryani", "Spiced rice with chicken and cucumber salad.", "160.00", 20),
                ("Tuna Pastil", "Tuna pastil with toasted garlic and palapa.", "75.00", 10),
                ("Palapa Fried Rice", "Fried rice with egg and Maranao palapa.", "95.00", 12),
            ],
            "Burgers and Snacks": [
                ("Beef Burger", "Grilled beef patty, lettuce, tomato, and house sauce.", "120.00", 14),
                ("Double Patty Burger", "Two beef patties with cheese and house sauce.", "165.00", 16),
                ("Chicken Sandwich", "Crispy chicken fillet with slaw.", "115.00", 13),
                ("Cheese Fries", "Crispy fries with cheese sauce.", "80.00", 8),
                ("Dynamite Lumpia", "Chili cheese rolls with garlic dip.", "85.00", 9),
            ],
            "Drinks": [
                ("Iced Tea", "House brewed iced tea.", "35.00", 2),
                ("Cucumber Lemonade", "Fresh cucumber lemonade.", "55.00", 3),
                ("Bottled Water", "Cold bottled water.", "25.00", 1),
                ("Mango Shake", "Ripe mango shake.", "85.00", 5),
            ],
            "Desserts": [
                ("Leche Flan", "Creamy caramel custard.", "70.00", 4),
                ("Pastel Slice", "Soft custard-filled bun.", "45.00", 2),
            ],
        }

        products = []
        for order, (category_name, rows) in enumerate(menu.items(), start=1):
            category, _ = Category.objects.update_or_create(
                store=store,
                slug=category_name.lower().replace(" and ", "-").replace(" ", "-"),
                defaults={
                    "name": category_name,
                    "description": f"{category_name} menu items",
                    "is_active": True,
                    "order": order,
                },
            )
            for name, description, price, prep_time in rows:
                product, _ = Product.objects.update_or_create(
                    category=category,
                    name=name,
                    defaults={
                        "slug": name.lower().replace(" ", "-"),
                        "description": description,
                        "price": Decimal(price),
                        "product_type": ProductType.FOOD,
                        "unit_type": UnitType.PIECE,
                        "preparation_time_minutes": prep_time,
                        "inventory_mode": InventoryMode.NONE,
                        "is_available": True,
                        "is_active": True,
                    },
                )
                products.append(product)
        return products

    def _seed_orders(self, store, customers, riders, products, now, rng):
        lanes = [
            ("Downtown Marawi", Decimal("8.000900"), Decimal("124.285700")),
            ("MSU Main", Decimal("7.998800"), Decimal("124.261900")),
            ("Tibanga", Decimal("8.015500"), Decimal("124.276100")),
            ("Banggolo Poblacion", Decimal("8.003200"), Decimal("124.284100")),
            ("Saduc", Decimal("8.011900"), Decimal("124.294700")),
        ]
        today_plan = [
            (OrderStatus.PENDING, 9),
            (OrderStatus.ACCEPTED, 18),
            (OrderStatus.PREPARING, 14),
            (OrderStatus.READY, 7),
            (OrderStatus.ON_THE_WAY, 20),
            (OrderStatus.DELIVERED, 30),
            (OrderStatus.CANCELLED, 4),
        ]
        yesterday_plan = [
            (OrderStatus.DELIVERED, 81),
            (OrderStatus.CANCELLED, 3),
        ]

        for status, count in today_plan:
            for index in range(count):
                minutes_ago = 3 + (index % 18) * 5
                if status == OrderStatus.PREPARING and index < 6:
                    minutes_ago = 25 + index * 3
                created_at = now - timedelta(minutes=minutes_ago)
                self._create_order(store, customers, riders, products, lanes, status, created_at, rng)

        yesterday_base = now - timedelta(days=1)
        for status, count in yesterday_plan:
            for index in range(count):
                created_at = yesterday_base - timedelta(minutes=20 + index * 9)
                self._create_order(store, customers, riders, products, lanes, status, created_at, rng)

    def _create_order(self, store, customers, riders, products, lanes, status, created_at, rng):
        customer = rng.choice(customers)
        delivery_method = DeliveryMethod.PICKUP if rng.random() < 0.15 else DeliveryMethod.DELIVERY
        lane, latitude, longitude = rng.choice(lanes)
        selected_products = rng.sample(products, rng.randint(1, 3))
        subtotal = Decimal("0.00")
        line_items = []
        for product in selected_products:
            quantity = rng.randint(1, 3)
            subtotal += product.price * quantity
            line_items.append((product, quantity, product.price))

        delivery_fee = Decimal("0.00") if delivery_method == DeliveryMethod.PICKUP else Decimal(str(rng.choice([35, 40, 45, 50])))
        system_fee = Decimal("10.00")
        discount = Decimal(str(rng.choice([0, 0, 0, 15, 20])))
        total_amount = max(subtotal + delivery_fee + system_fee - discount, Decimal("0.00"))
        rider = rng.choice(riders) if status in [OrderStatus.ON_THE_WAY, OrderStatus.DELIVERED] else None
        delivered_at = None
        if status == OrderStatus.DELIVERED:
            delivered_at = created_at + timedelta(minutes=rng.randint(24, 42))

        order = Order.objects.create(
            customer=customer,
            store=store,
            rider=rider,
            status=status,
            delivery_method=delivery_method,
            delivery_address_text=f"{lane}, Marawi City, Lanao del Sur, Philippines",
            delivery_latitude=latitude,
            delivery_longitude=longitude,
            subtotal=subtotal,
            delivery_fee=delivery_fee,
            system_fee=system_fee,
            discount_amount=discount,
            total_amount=total_amount,
            delivered_at=delivered_at,
            estimated_arrival_time=created_at + timedelta(minutes=35),
        )
        for product, quantity, unit_price in line_items:
            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=quantity,
                unit_price=unit_price,
            )

        updated_at = created_at + timedelta(minutes=rng.randint(3, 22))
        if status == OrderStatus.PREPARING and created_at <= timezone.now() - timedelta(minutes=15):
            updated_at = created_at
        Order.objects.filter(id=order.id).update(created_at=created_at, updated_at=updated_at)
