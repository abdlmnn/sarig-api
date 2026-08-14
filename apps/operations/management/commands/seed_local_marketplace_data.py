from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from apps.catalog.models import Category, InventoryMode, Product, ProductType, UnitType
from apps.onboarding.models import (
    ApplicationStatus,
    BusinessType,
    DeliveryTime,
    LocationSource,
    MerchantApplication,
    RiderApplication,
    VehicleType,
)
from apps.orders.models import DeliveryMethod, Order, OrderItem, OrderStatus
from apps.payments.models import PaymentMethod, PaymentStatus, PaymentTransaction
from apps.riders.models import RiderProfile
from apps.users.models import Role, User
from apps.vendors.models import BusinessVertical, Store, StoreDeliveryTime, StoreManualOverride


DEFAULT_PASSWORD = "salih123"
ADMIN_PASSWORD = "admin123"


class Command(BaseCommand):
    help = "Seed local marketplace data with realistic Marawi stores, products, riders, and orders."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Remove this seed set before reseeding.")

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("This local seed command must only run when DEBUG=True.")

        if options["reset"]:
            self.reset_seed_data()

        self.ensure_roles()
        self.ensure_admin_user()
        verticals = self.seed_verticals()
        merchants = self.seed_merchants()
        customers = self.seed_customers()
        riders = self.seed_riders()
        stores = self.seed_stores(verticals, merchants)
        products = self.seed_catalog(stores)
        merchant_apps, rider_apps = self.seed_onboarding_applications(verticals, merchants)
        orders = self.seed_orders(stores, products, customers, riders)

        self.stdout.write(self.style.SUCCESS("Seeded local marketplace data."))
        self.stdout.write(f"Stores: {len(stores)}")
        self.stdout.write(f"Products: {len(products)}")
        self.stdout.write(f"Riders: {len(riders)}")
        self.stdout.write(f"Merchant applications: {len(merchant_apps)}")
        self.stdout.write(f"Rider applications: {len(rider_apps)}")
        self.stdout.write(f"Orders: {len(orders)}")
        self.stdout.write(f"Merchant password: {DEFAULT_PASSWORD}")
        self.stdout.write(f"Customer password: {DEFAULT_PASSWORD}")
        self.stdout.write(f"Rider password: {DEFAULT_PASSWORD}")
        self.stdout.write(f"Admin login: admin / {ADMIN_PASSWORD}")

    def ensure_roles(self):
        for name in ["Customer", "Merchant", "Rider"]:
            Role.objects.get_or_create(name=name)

    def ensure_admin_user(self):
        admin, created = User.objects.update_or_create(
            username="admin",
            defaults={
                "email": "admin@sarig.local",
                "first_name": "Sarig",
                "last_name": "Admin",
                "is_active": True,
                "is_staff": True,
                "is_superuser": True,
            },
        )
        admin.set_password(ADMIN_PASSWORD)
        admin.save(update_fields=["password", "email", "first_name", "last_name", "is_active", "is_staff", "is_superuser"])
        return admin

    def reset_seed_data(self):
        usernames = [
            "restaurant1",
            "grocery1",
            "pharmacy1",
            "bakery1",
            "customer1",
            "customer2",
            "customer3",
            "rider1",
            "rider2",
            "rider3",
            "ranaw_grill_owner",
            "msu_mart_owner",
            "lakecare_pharmacy_owner",
            "padian_bakes_owner",
            "customer_amira",
            "customer_jalal",
            "customer_mariam",
            "rider_nasser",
            "rider_samira",
            "rider_khalid",
        ]
        stores = Store.objects.filter(owner__username__in=usernames)
        MerchantApplication.objects.filter(application_id__in=["MR-1028", "MR-2034", "MR-3140", "MR-4256"]).delete()
        RiderApplication.objects.filter(application_id__in=["RD-1028", "RD-2034", "RD-3140"]).delete()
        PaymentTransaction.objects.filter(order__store__in=stores).delete()
        Order.objects.filter(store__in=stores).delete()
        Category.objects.filter(store__in=stores).delete()
        stores.delete()
        RiderProfile.objects.filter(user__username__in=usernames).delete()
        User.objects.filter(username__in=usernames).delete()

    def seed_verticals(self):
        data = [
            ("restaurant", "Restaurant", [ProductType.FOOD], False),
            ("grocery", "Grocery", [ProductType.GROCERY, ProductType.GENERAL], False),
            ("pharmacy", "Pharmacy", [ProductType.MEDICINE, ProductType.GENERAL], True),
            ("bakery", "Bakery", [ProductType.FOOD], False),
        ]
        verticals = {}
        for slug, name, product_types, requires_license in data:
            vertical, _ = BusinessVertical.objects.update_or_create(
                slug=slug,
                defaults={
                    "name": name,
                    "allowed_product_types": product_types,
                    "requires_license": requires_license,
                    "required_documents": ["mayors_permit"],
                    "is_active": True,
                },
            )
            verticals[slug] = vertical
        return verticals

    def user(self, username, email, role_name, first_name, last_name, phone):
        user, created = User.objects.update_or_create(
            username=username,
            defaults={
                "email": email,
                "first_name": first_name,
                "last_name": last_name,
                "phone_number": phone,
                "is_active": True,
            },
        )
        if created or not user.has_usable_password():
            user.set_password(DEFAULT_PASSWORD)
            user.save(update_fields=["password"])
        user.roles.add(Role.objects.get(name=role_name))
        return user

    def seed_merchants(self):
        return {
            "ranaw": self.user("restaurant1", "restaurant1@sarig.local", "Merchant", "Salma", "Macapaar", "+639171201001"),
            "mart": self.user("grocery1", "grocery1@sarig.local", "Merchant", "Omar", "Disomangcop", "+639171201002"),
            "pharmacy": self.user("pharmacy1", "pharmacy1@sarig.local", "Merchant", "Amina", "Pangandaman", "+639171201003"),
            "bakery": self.user("bakery1", "bakery1@sarig.local", "Merchant", "Nora", "Ali", "+639171201004"),
        }

    def seed_customers(self):
        return [
            self.user("customer1", "customer1@sarig.local", "Customer", "Amira", "Usman", "+639172001001"),
            self.user("customer2", "customer2@sarig.local", "Customer", "Jalal", "Macarambon", "+639172001002"),
            self.user("customer3", "customer3@sarig.local", "Customer", "Mariam", "Malik", "+639172001003"),
        ]

    def seed_riders(self):
        rider_rows = [
            ("rider1", "rider1@sarig.local", "Nasser", "Musa", "+639173001001", Decimal("8.000700"), Decimal("124.266600"), "LDR-4101"),
            ("rider2", "rider2@sarig.local", "Samira", "Ampaso", "+639173001002", Decimal("8.003400"), Decimal("124.283900"), "LDR-4102"),
            ("rider3", "rider3@sarig.local", "Khalid", "Mamar", "+639173001003", Decimal("7.996400"), Decimal("124.285700"), "LDR-4103"),
        ]
        riders = []
        for username, email, first, last, phone, lat, lng, plate in rider_rows:
            user = self.user(username, email, "Rider", first, last, phone)
            profile, _ = RiderProfile.objects.update_or_create(
                user=user,
                defaults={
                    "is_online": True,
                    "is_available": True,
                    "can_do_delivery": True,
                    "can_do_ride_hailing": True,
                    "vehicle_type": "MOTORCYCLE",
                    "plate_number": plate,
                    "current_latitude": lat,
                    "current_longitude": lng,
                },
            )
            riders.append(profile)
        return riders

    def seed_stores(self, verticals, merchants):
        rows = [
            ("ranaw", "Ranaw Grill and Kitchen", "Poblacion Branch", "restaurant", Decimal("8.002900"), Decimal("124.285500"), "Poblacion Core", "Quezon Avenue"),
            ("mart", "MSU Campus Mart", "Rapasun Branch", "grocery", Decimal("8.000700"), Decimal("124.266600"), "Rapasun MSU", "University Avenue"),
            ("pharmacy", "Lakecare Pharmacy", "Amai Pakpak Branch", "pharmacy", Decimal("8.003400"), Decimal("124.283900"), "Banggolo Poblacion", "Amai Pakpak Avenue"),
            ("bakery", "Padian Bakeshop", "Marinaut Branch", "bakery", Decimal("7.996400"), Decimal("124.285700"), "Marinaut West", "Lakeside Drive"),
        ]
        stores = {}
        for key, name, branch, vertical_slug, lat, lng, barangay, street in rows:
            store, _ = Store.objects.update_or_create(
                owner=merchants[key],
                name=name,
                defaults={
                    "vertical": verticals[vertical_slug],
                    "branch_name": branch,
                    "company_email": merchants[key].email,
                    "contact_number": merchants[key].phone_number or "",
                    "delivery_time": StoreDeliveryTime.ALL_DAY,
                    "latitude": lat,
                    "longitude": lng,
                    "street_address": street,
                    "city": "Marawi City",
                    "barangay": barangay,
                    "province": "Lanao del Sur",
                    "postal_code": "9700",
                    "pinned_address": f"{street}, {barangay}, Marawi City, Lanao del Sur",
                    "commission_rate": Decimal("15.00"),
                    "is_open": True,
                    "is_active": True,
                    "manual_override": StoreManualOverride.OPEN_NOW,
                    "manual_override_reason": "Available for local testing",
                    "auto_accept_orders": False,
                    "rating": Decimal("4.70"),
                },
            )
            self.seed_store_branding(store, key)
            stores[key] = store
        return stores

    def seed_store_branding(self, store, key):
        branding_files = {
            "ranaw": {
                "logo_image": "ranaw-grill-logo.png",
                "banner_image": "ranaw-grill-banner.png",
            },
        }.get(key)
        update_fields = []
        if branding_files:
            branding_dir = Path(settings.BASE_DIR) / "data" / "store-branding"
            for field_name, file_name in branding_files.items():
                source = branding_dir / file_name
                if not source.exists():
                    continue
                with source.open("rb") as file_obj:
                    getattr(store, field_name).save(file_name, File(file_obj), save=False)
                update_fields.append(field_name)
        else:
            generated = self.generated_store_branding(key, store.name)
            if not generated:
                return
            for field_name, file_name, content in generated:
                getattr(store, field_name).save(file_name, ContentFile(content), save=False)
                update_fields.append(field_name)
        if update_fields:
            store.save(update_fields=[*update_fields, "updated_at"])

    def generated_store_branding(self, key, store_name):
        styles = {
            "mart": ("#0f766e", "#ccfbf1", "M"),
            "pharmacy": ("#047857", "#d1fae5", "L"),
            "bakery": ("#b45309", "#ffedd5", "P"),
        }
        style = styles.get(key)
        if not style:
            return None
        primary, soft, letter = style
        escaped_name = store_name.replace("&", "and")
        banner = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="500" viewBox="0 0 1200 500">
  <rect width="1200" height="500" fill="{soft}"/>
  <circle cx="1040" cy="100" r="190" fill="{primary}" opacity="0.16"/>
  <circle cx="120" cy="430" r="210" fill="{primary}" opacity="0.10"/>
  <rect x="80" y="110" width="520" height="280" rx="38" fill="white" opacity="0.82"/>
  <text x="125" y="235" font-family="Arial, sans-serif" font-size="64" font-weight="800" fill="{primary}">{escaped_name}</text>
  <text x="128" y="295" font-family="Arial, sans-serif" font-size="30" font-weight="600" fill="#334155">Open for local deliveries</text>
</svg>""".encode()
        logo = f"""<svg xmlns="http://www.w3.org/2000/svg" width="400" height="400" viewBox="0 0 400 400">
  <rect width="400" height="400" rx="88" fill="{primary}"/>
  <circle cx="200" cy="200" r="128" fill="white" opacity="0.18"/>
  <text x="200" y="240" text-anchor="middle" font-family="Arial, sans-serif" font-size="150" font-weight="900" fill="white">{letter}</text>
</svg>""".encode()
        return [
            ("banner_image", f"{key}-banner.svg", banner),
            ("logo_image", f"{key}-logo.svg", logo),
        ]

    def seed_catalog(self, stores):
        catalog = {
            "ranaw": {
                "Rice Meals": [
                    ("Chicken Pastil", "Shredded chicken with rice and palapa", "65.00", 38, ProductType.FOOD, UnitType.PIECE),
                    ("Beef Rendang Rice", "Slow-cooked beef rendang with steamed rice", "145.00", 18, ProductType.FOOD, UnitType.PIECE),
                    ("Chicken Biryani", "Spiced rice meal with chicken and cucumber salad", "160.00", 21, ProductType.FOOD, UnitType.PIECE),
                ],
                "Drinks": [
                    ("Cucumber Lemonade", "Fresh cucumber lemonade", "55.00", 40, ProductType.FOOD, UnitType.BOTTLE),
                    ("Mango Shake", "Cold mango shake", "85.00", 22, ProductType.FOOD, UnitType.BOTTLE),
                ],
            },
            "mart": {
                "Pantry": [
                    ("Premium Rice 5kg", "Locally packed rice", "310.00", 25, ProductType.GROCERY, UnitType.PACK),
                    ("Cooking Oil 1L", "Vegetable cooking oil", "145.00", 30, ProductType.GROCERY, UnitType.BOTTLE),
                    ("Sardines 155g", "Tomato sauce sardines", "32.00", 60, ProductType.GROCERY, UnitType.CAN),
                ],
                "Household": [
                    ("Laundry Detergent", "Powder detergent sachet bundle", "78.00", 35, ProductType.GENERAL, UnitType.PACK),
                    ("Dishwashing Liquid", "Lemon dishwashing liquid", "92.00", 28, ProductType.GENERAL, UnitType.BOTTLE),
                ],
            },
            "pharmacy": {
                "Medicines": [
                    ("Paracetamol 500mg", "Pain and fever relief tablet", "5.00", 200, ProductType.MEDICINE, UnitType.TABLET),
                    ("Cetirizine 10mg", "Antihistamine tablet", "8.00", 120, ProductType.MEDICINE, UnitType.TABLET),
                    ("Oral Rehydration Salts", "Rehydration sachet", "18.00", 90, ProductType.MEDICINE, UnitType.SACHET),
                ],
                "Wellness": [
                    ("Vitamin C 500mg", "Vitamin supplement tablet", "7.00", 150, ProductType.GENERAL, UnitType.TABLET),
                    ("Alcohol 500ml", "Isopropyl alcohol", "95.00", 55, ProductType.GENERAL, UnitType.BOTTLE),
                ],
            },
            "bakery": {
                "Bread": [
                    ("Cheese Ensaymada", "Soft bread with cheese topping", "45.00", 32, ProductType.FOOD, UnitType.PIECE),
                    ("Ube Pandesal", "Purple yam-filled pandesal", "18.00", 70, ProductType.FOOD, UnitType.PIECE),
                ],
                "Cakes": [
                    ("Chocolate Cake Slice", "Moist chocolate cake slice", "75.00", 16, ProductType.FOOD, UnitType.PIECE),
                    ("Leche Flan Cup", "Creamy caramel custard", "55.00", 24, ProductType.FOOD, UnitType.PIECE),
                ],
            },
        }
        products = []
        for store_key, categories in catalog.items():
            store = stores[store_key]
            for order, (category_name, product_rows) in enumerate(categories.items(), start=1):
                category, _ = Category.objects.update_or_create(
                    store=store,
                    slug=slugify(category_name),
                    defaults={
                        "name": category_name,
                        "description": f"{category_name} available from {store.name}",
                        "is_active": True,
                        "order": order,
                    },
                )
                for name, description, price, stock, product_type, unit_type in product_rows:
                    product, _ = Product.objects.update_or_create(
                        category=category,
                        slug=slugify(name),
                        defaults={
                            "sku": f"{store_key.upper()}-{slugify(name).upper()[:24]}",
                            "name": name,
                            "description": description,
                            "price": Decimal(price),
                            "product_type": product_type,
                            "unit_type": unit_type,
                            "inventory_mode": InventoryMode.SIMPLE_STOCK,
                            "stock_quantity": stock,
                            "low_stock_threshold": 8,
                            "is_available": True,
                            "is_active": True,
                            "preparation_time_minutes": 15 if product_type == ProductType.FOOD else None,
                            "requires_prescription": False,
                        },
                    )
                    products.append(product)
        return products

    def local_file(self, file_name, content_type="application/pdf"):
        if content_type == "image/png":
            return ContentFile(
                b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
                b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDAT\x08\xd7c\xf8\xff"
                b"\xff?\x00\x05\xfe\x02\xfeA\xd9\x8f\xb5\x00\x00\x00\x00IEND\xaeB`\x82",
                name=file_name,
            )
        return ContentFile(b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n", name=file_name)

    def seed_onboarding_applications(self, verticals, merchants):
        merchant_rows = [
            ("MR-1028", merchants["ranaw"], "Ranaw Grill and Kitchen", "Salma", "Macapaar", "restaurant", BusinessType.RESTAURANT, ApplicationStatus.PENDING, "Poblacion Core", "Quezon Avenue", Decimal("8.002900"), Decimal("124.285500")),
            ("MR-2034", merchants["mart"], "MSU Campus Mart", "Omar", "Disomangcop", "grocery", BusinessType.SHOP, ApplicationStatus.UNDER_REVIEW, "Rapasun MSU", "University Avenue", Decimal("8.000700"), Decimal("124.266600")),
            ("MR-3140", merchants["pharmacy"], "Lakecare Pharmacy", "Amina", "Pangandaman", "pharmacy", BusinessType.SHOP, ApplicationStatus.APPROVED, "Banggolo Poblacion", "Amai Pakpak Avenue", Decimal("8.003400"), Decimal("124.283900")),
            ("MR-4256", merchants["bakery"], "Padian Bakeshop", "Nora", "Ali", "bakery", BusinessType.RESTAURANT, ApplicationStatus.REQUEST_CHANGES, "Marinaut West", "Lakeside Drive", Decimal("7.996400"), Decimal("124.285700")),
        ]
        merchant_apps = []
        for app_id, applicant, business_name, first, last, vertical_slug, business_type, status, barangay, street, lat, lng in merchant_rows:
            app, created = MerchantApplication.objects.update_or_create(
                application_id=app_id,
                defaults={
                    "applicant": applicant,
                    "business_name": business_name,
                    "owner_first_name": first,
                    "owner_last_name": last,
                    "company_email": applicant.email,
                    "contact_number": applicant.phone_number or "+639170000000",
                    "business_type": business_type,
                    "business_vertical": verticals[vertical_slug],
                    "delivery_time": DeliveryTime.ALL_DAY,
                    "branch_name": "Main Branch",
                    "terms_accepted": True,
                    "business_address": f"{street}, {barangay}, Marawi City",
                    "city": "Marawi City",
                    "barangay": barangay,
                    "province": "Lanao del Sur",
                    "postal_code": "9700",
                    "street": street,
                    "location_source": LocationSource.PIN,
                    "pinned_address": f"{street}, {barangay}, Marawi City, Lanao del Sur",
                    "latitude": lat,
                    "longitude": lng,
                    "status": status,
                    "admin_remarks": "Please provide updated storefront photos." if status == ApplicationStatus.REQUEST_CHANGES else "",
                    "requested_fields": ["storefront_photo"] if status == ApplicationStatus.REQUEST_CHANGES else [],
                },
            )
            if created or not app.dti_sec_certificate:
                app.dti_sec_certificate.save(f"{app_id.lower()}-dti.pdf", self.local_file(f"{app_id.lower()}-dti.pdf"), save=False)
                app.mayors_permit.save(f"{app_id.lower()}-permit.pdf", self.local_file(f"{app_id.lower()}-permit.pdf"), save=False)
                app.owner_valid_id.save(f"{app_id.lower()}-id.pdf", self.local_file(f"{app_id.lower()}-id.pdf"), save=False)
                app.storefront_photo.save(f"{app_id.lower()}-storefront.png", self.local_file(f"{app_id.lower()}-storefront.png", "image/png"), save=False)
                if vertical_slug == "pharmacy":
                    app.pharmacy_license.save(f"{app_id.lower()}-license.pdf", self.local_file(f"{app_id.lower()}-license.pdf"), save=False)
                app.save()
            merchant_apps.append(app)

        rider_rows = [
            ("RD-1028", "Nasser", "Musa", "nasser.rider@sarig.local", "+639173001001", ApplicationStatus.PENDING, "Rapasun MSU", VehicleType.MOTORCYCLE, "Honda Click 125", "LDR-4101"),
            ("RD-2034", "Samira", "Ampaso", "samira.rider@sarig.local", "+639173001002", ApplicationStatus.UNDER_REVIEW, "Poblacion Core", VehicleType.MOTORCYCLE, "Yamaha Mio Gear", "LDR-4102"),
            ("RD-3140", "Khalid", "Mamar", "khalid.rider@sarig.local", "+639173001003", ApplicationStatus.APPROVED, "Marinaut West", VehicleType.MOTORCYCLE, "Suzuki Raider", "LDR-4103"),
        ]
        rider_apps = []
        for app_id, first, last, email, phone, status, barangay, vehicle_type, vehicle_brand, plate in rider_rows:
            app, created = RiderApplication.objects.update_or_create(
                application_id=app_id,
                defaults={
                    "first_name": first,
                    "last_name": last,
                    "email": email,
                    "phone_number": phone,
                    "terms_accepted": True,
                    "current_address": f"{barangay}, Marawi City",
                    "barangay": barangay,
                    "city": "Marawi City",
                    "province": "Lanao del Sur",
                    "postal_code": "9700",
                    "emergency_contact_name": f"{first} Contact",
                    "emergency_contact_number": "+639179999999",
                    "emergency_contact_relationship": "Family",
                    "vehicle_type": vehicle_type,
                    "vehicle_brand": vehicle_brand,
                    "plate_number": plate,
                    "status": status,
                },
            )
            if created or not app.professional_drivers_license:
                app.professional_drivers_license.save(f"{app_id.lower()}-license.pdf", self.local_file(f"{app_id.lower()}-license.pdf"), save=False)
                app.nbi_clearance.save(f"{app_id.lower()}-nbi.pdf", self.local_file(f"{app_id.lower()}-nbi.pdf"), save=False)
                app.vehicle_photo_front.save(f"{app_id.lower()}-front.png", self.local_file(f"{app_id.lower()}-front.png", "image/png"), save=False)
                app.vehicle_photo_back.save(f"{app_id.lower()}-back.png", self.local_file(f"{app_id.lower()}-back.png", "image/png"), save=False)
                app.save()
            rider_apps.append(app)
        return merchant_apps, rider_apps

    def seed_orders(self, stores, products, customers, riders):
        selected = [products[0], products[3], products[5], products[10]]
        rows = [
            (stores["ranaw"], customers[0], riders[0].user, selected[0], OrderStatus.PREPARING, PaymentMethod.COD, PaymentStatus.PENDING),
            (stores["mart"], customers[1], riders[1].user, selected[2], OrderStatus.READY, PaymentMethod.PAYMONGO, PaymentStatus.SUCCESS),
            (stores["pharmacy"], customers[2], None, selected[3], OrderStatus.PENDING, PaymentMethod.COD, PaymentStatus.PENDING),
        ]
        orders = []
        for store, customer, rider, product, status, payment_method, payment_status in rows:
            subtotal = product.price * Decimal("2")
            delivery_fee = Decimal("45.00")
            system_fee = Decimal("8.00")
            total = subtotal + delivery_fee + system_fee
            order, _ = Order.objects.update_or_create(
                customer=customer,
                store=store,
                delivery_address_text=f"{customer.first_name}'s address near {store.barangay}",
                defaults={
                    "rider": rider,
                    "status": status,
                    "delivery_method": DeliveryMethod.DELIVERY,
                    "delivery_latitude": store.latitude,
                    "delivery_longitude": store.longitude,
                    "subtotal": subtotal,
                    "delivery_fee": delivery_fee,
                    "system_fee": system_fee,
                    "total_amount": total,
                },
            )
            OrderItem.objects.update_or_create(
                order=order,
                product=product,
                defaults={"quantity": 2, "unit_price": product.price},
            )
            PaymentTransaction.objects.update_or_create(
                order=order,
                defaults={
                    "payment_method": payment_method,
                    "status": payment_status,
                    "amount": total,
                    "payment_id": f"pay_local_{str(order.id)[:12]}" if payment_method == PaymentMethod.PAYMONGO else None,
                },
            )
            orders.append(order)
        return orders
