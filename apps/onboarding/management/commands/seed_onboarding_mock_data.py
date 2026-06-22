from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.marketing.models import DiscountType, PromoCode
from apps.onboarding.models import (
    AccountSetupToken,
    ApplicationEditToken,
    ApplicationStatus,
    ApplicationStatusHistory,
    BusinessType,
    DeliveryTime,
    LocationSource,
    MerchantApplication,
    RiderApplication,
    VehicleType,
)
from apps.onboarding.services import ApplicationService
from apps.operations.models import AdminAlert, AlertSeverity, LoadStatus, ServiceZone, ServiceZoneMetricSnapshot
from apps.operations.seed_data import MARAWI_SERVICE_ZONES
from apps.orders.models import DeliveryMethod, Order, OrderStatus
from apps.payments.models import PaymentMethod, PaymentStatus, PaymentTransaction
from apps.riders.models import RiderProfile
from apps.rides.models import Ride, RideStatus


PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDAT\x08\xd7c\xf8\xff"
    b"\xff?\x00\x05\xfe\x02\xfeA\xd9\x8f\xb5\x00\x00\x00\x00IEND\xaeB`\x82"
)
PDF_BYTES = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"

ZONE_COORDS = {
    "Saduc Proper": (Decimal("8.012600"), Decimal("124.291200")),
    "Basak Malutlut": (Decimal("8.004500"), Decimal("124.299900")),
    "Poblacion": (Decimal("8.003400"), Decimal("124.283900")),
    "Poblacion Core": (Decimal("8.002900"), Decimal("124.285500")),
    "Matampay": (Decimal("8.019200"), Decimal("124.287500")),
    "Sagonsongan": (Decimal("7.969800"), Decimal("124.295800")),
    "Datu Naga": (Decimal("8.007500"), Decimal("124.281100")),
    "Bangon": (Decimal("8.010700"), Decimal("124.277900")),
    "Rapasun MSU": (Decimal("8.000700"), Decimal("124.266600")),
    "Lilod Madaya": (Decimal("8.000200"), Decimal("124.292600")),
    "Marinaut West": (Decimal("7.996400"), Decimal("124.285700")),
    "Papandayan": (Decimal("7.997300"), Decimal("124.279900")),
}


MERCHANT_SEEDS = [
    ("Sultan Food House", "Hassan", "Macarambon", "merchant1@sarig.local", "+63 917-110-1001", BusinessType.RESTAURANT, DeliveryTime.ALL_DAY, "Main Branch", "Saduc Proper", "National Highway", LocationSource.PIN, ApplicationStatus.PENDING, "", []),
    ("Basak Grocery Hub", "Nora", "Ali", "merchant2@sarig.local", "+63 917-110-1002", BusinessType.SHOP, DeliveryTime.MORNING, "Warehouse Counter", "Basak Malutlut", "Basak Road", LocationSource.MANUAL, ApplicationStatus.UNDER_REVIEW, "", []),
    ("Lakeview Bakeshop", "Rizalyn", "Abas", "merchant3@sarig.local", "+63 917-110-1003", BusinessType.SHOP, DeliveryTime.AFTERNOON, "Front Kiosk", "Poblacion", "Amai Pakpak Avenue", LocationSource.PIN, ApplicationStatus.APPROVED, "", []),
    ("Ranaw Fresh Market", "Jamil", "Guro", "merchant4@sarig.local", "+63 917-110-1004", BusinessType.SHOP, DeliveryTime.MORNING, "Produce Side", "Matampay", "Market Loop", LocationSource.PIN, ApplicationStatus.REQUEST_CHANGES, "Please upload a clearer mayor's permit and storefront photo.", ["mayors_permit", "storefront_photo"]),
    ("Merienda Express", "Sittie", "Acmad", "merchant5@sarig.local", "+63 917-110-1005", BusinessType.RESTAURANT, DeliveryTime.EVENING, "Night Counter", "Sagonsongan", "Commercial Strip", LocationSource.MANUAL, ApplicationStatus.REJECTED, "Application rejected because submitted identity documents could not be verified.", []),
    ("Kambal Chicken House", "Fahad", "Mimbalawag", "merchant6@sarig.local", "+63 917-110-1006", BusinessType.RESTAURANT, DeliveryTime.ALL_DAY, "Family Hall", "Datu Naga", "Interior Road 3", LocationSource.PIN, ApplicationStatus.PENDING, "", []),
    ("Hariraya Dry Goods", "Mina", "Racman", "merchant7@sarig.local", "+63 917-110-1007", BusinessType.SHOP, DeliveryTime.AFTERNOON, "Textiles Unit", "Bangon", "Bangon Crossing", LocationSource.PIN, ApplicationStatus.UNDER_REVIEW, "", []),
    ("Sajid Coffee Corner", "Aina", "Sambitory", "merchant8@sarig.local", "+63 917-110-1008", BusinessType.RESTAURANT, DeliveryTime.MORNING, "Campus Side", "Rapasun MSU", "University Avenue", LocationSource.PIN, ApplicationStatus.APPROVED, "", []),
    ("Bai Essentials", "Maryam", "Lidasan", "merchant9@sarig.local", "+63 917-110-1009", BusinessType.SHOP, DeliveryTime.ALL_DAY, "Retail Booth", "Lilod Madaya", "Main Access Road", LocationSource.MANUAL, ApplicationStatus.REQUEST_CHANGES, "Please resubmit DTI certificate with a complete page scan.", ["dti_sec_certificate"]),
    ("Panggao Seafood Grill", "Ismael", "Pangandaman", "merchant10@sarig.local", "+63 917-110-1010", BusinessType.RESTAURANT, DeliveryTime.EVENING, "Lakeside Grill", "Marinaut West", "Lakeside Drive", LocationSource.PIN, ApplicationStatus.PENDING, "", []),
]

RIDER_SEEDS = [
    ("Ameer", "S.", "rider1@sarig.local", "+63 961-093-9761", "Saduc Proper", "Salma S.", "+63 917-200-1001", "Sister", VehicleType.MOTORCYCLE, "Honda Click 125", "LDR-1001", ApplicationStatus.REQUEST_CHANGES, "Please upload a clearer NBI clearance.", ["nbi_clearance"]),
    ("Khalid", "Mamar", "rider2@sarig.local", "+63 961-093-9762", "Basak Malutlut", "Mariam Mamar", "+63 917-200-1002", "Mother", VehicleType.BICYCLE, "Trek FX", "", ApplicationStatus.PENDING, "", []),
    ("Saidah", "Macud", "rider3@sarig.local", "+63 961-093-9763", "Matampay", "Karim Macud", "+63 917-200-1003", "Brother", VehicleType.MOTORCYCLE, "Yamaha Mio Gear", "LDR-1003", ApplicationStatus.UNDER_REVIEW, "", []),
    ("Abid", "Taha", "rider4@sarig.local", "+63 961-093-9764", "Sagonsongan", "Nur Taha", "+63 917-200-1004", "Wife", VehicleType.CAR, "Toyota Wigo", "LDS-2404", ApplicationStatus.APPROVED, "", []),
    ("Sakira", "Ampaso", "rider5@sarig.local", "+63 961-093-9765", "Datu Naga", "Latip Ampaso", "+63 917-200-1005", "Father", VehicleType.MOTORCYCLE, "Suzuki Raider", "LDR-1005", ApplicationStatus.REJECTED, "Application rejected because driver identity could not be verified.", []),
    ("Rashid", "Amerol", "rider6@sarig.local", "+63 961-093-9766", "Bangon", "Fatima Amerol", "+63 917-200-1006", "Mother", VehicleType.BICYCLE, "Giant Escape", "", ApplicationStatus.PENDING, "", []),
    ("Nur-Ain", "Balindong", "rider7@sarig.local", "+63 961-093-9767", "Rapasun MSU", "Said Balindong", "+63 917-200-1007", "Uncle", VehicleType.MOTORCYCLE, "Honda Beat", "LDR-1007", ApplicationStatus.UNDER_REVIEW, "", []),
    ("Jabir", "Guiapal", "rider8@sarig.local", "+63 961-093-9768", "Poblacion", "Nadia Guiapal", "+63 917-200-1008", "Wife", VehicleType.CAR, "Suzuki S-Presso", "LDS-2408", ApplicationStatus.APPROVED, "", []),
    ("Mona", "Mimbisa", "rider9@sarig.local", "+63 961-093-9769", "Lilod Madaya", "Faisal Mimbisa", "+63 917-200-1009", "Brother", VehicleType.MOTORCYCLE, "Kawasaki Barako", "LDR-1009", ApplicationStatus.REQUEST_CHANGES, "Please re-upload front vehicle photo and OR/CR.", ["vehicle_photo_front", "lto_or_cr"]),
    ("Tariq", "Disomimba", "rider10@sarig.local", "+63 961-093-9770", "Marinaut West", "Rabiya Disomimba", "+63 917-200-1010", "Mother", VehicleType.BICYCLE, "Trinx Tempo", "", ApplicationStatus.PENDING, "", []),
]


class Command(BaseCommand):
    help = "Seed onboarding and operations mock data for merchant/rider signup and admin dashboards."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete existing onboarding and operations mock data before reseeding.")

    def handle(self, *args, **options):
        with transaction.atomic():
            if options["reset"]:
                self.reset_mock_data()

            admin_user = self.ensure_admin_user()
            self.seed_service_zones()
            merchant_apps = self.seed_merchants(admin_user)
            rider_apps = self.seed_riders(admin_user)
            stores = self.materialize_approved_merchants(merchant_apps)
            riders = self.materialize_approved_riders(rider_apps)
            customers = self.ensure_customers()
            promo_codes = self.ensure_promo_codes()
            self.seed_orders(stores, riders, customers, promo_codes)
            self.seed_rides(riders, customers)
            self.seed_zone_snapshots()
            self.seed_alerts()

        self.stdout.write(self.style.SUCCESS(f"Seeded onboarding mock data: {len(merchant_apps)} merchants, {len(rider_apps)} riders."))
        self.stdout.write(self.style.SUCCESS(f"Seeded operations mock data: {ServiceZone.objects.count()} zones, {len(stores)} stores, {len(riders)} rider profiles."))
        self.stdout.write(self.style.SUCCESS("Admin login: username=admin password=admin12345"))
        self.stdout.write(self.style.SUCCESS("Command example: python manage.py seed_onboarding_mock_data --reset"))

    def reset_mock_data(self):
        merchant_emails = [seed[3] for seed in MERCHANT_SEEDS]
        rider_emails = [seed[2] for seed in RIDER_SEEDS]
        app_ids = list(MerchantApplication.objects.filter(company_email__in=merchant_emails).values_list("application_id", flat=True))
        app_ids += list(RiderApplication.objects.filter(email__in=rider_emails).values_list("application_id", flat=True))

        ApplicationStatusHistory.objects.filter(application_id__in=app_ids).delete()
        ApplicationEditToken.objects.filter(application_id__in=app_ids).delete()
        AccountSetupToken.objects.filter(application_id__in=app_ids).delete()
        MerchantApplication.objects.filter(company_email__in=merchant_emails).delete()
        RiderApplication.objects.filter(email__in=rider_emails).delete()
        PaymentTransaction.objects.filter(external_transaction_id__startswith="mock_").delete()
        Order.objects.filter(delivery_address_text__startswith="Mock Address ").delete()
        Ride.objects.filter(cancel_reason__startswith="mock_seed").delete()
        PromoCode.objects.filter(code__in=["WELCOME10", "MARAWI50"]).delete()
        AdminAlert.objects.filter(source="operations-seed").delete()
        ServiceZoneMetricSnapshot.objects.all().delete()
        ServiceZone.objects.filter(city__iexact="Marawi").delete()

    def ensure_admin_user(self):
        User = get_user_model()
        admin_user, _ = User.objects.get_or_create(
            username="admin",
            defaults={"email": "admin@sarig.local", "is_staff": True, "is_superuser": True},
        )
        admin_user.email = "admin@sarig.local"
        admin_user.is_staff = True
        admin_user.is_superuser = True
        admin_user.set_password("admin12345")
        admin_user.save()
        return admin_user

    def compact_phone(self, value):
        digits = "".join(ch for ch in str(value or "") if ch.isdigit())
        if digits.startswith("63"):
            digits = f"+{digits}"
        elif digits.startswith("0"):
            digits = f"+63{digits[1:]}"
        elif digits:
            digits = f"+{digits}"
        return digits[:15]

    def seed_service_zones(self):
        for zone in MARAWI_SERVICE_ZONES:
            ServiceZone.objects.update_or_create(
                slug=zone["slug"],
                defaults={
                    "name": zone["name"],
                    "city": "Marawi",
                    "province": "Lanao del Sur",
                    "center_latitude": zone["center_latitude"],
                    "center_longitude": zone["center_longitude"],
                    "barangay_names": zone["barangay_names"],
                    "priority": zone["priority"],
                    "is_active": True,
                },
            )

    def seed_merchants(self, admin_user):
        applications = []
        for index, seed in enumerate(MERCHANT_SEEDS, start=1):
            lat, lng = ZONE_COORDS[seed[8]]
            pinned_address = f"{seed[9]}, {seed[8]}, Marawi City"
            application, _ = MerchantApplication.objects.get_or_create(
                company_email=seed[3],
                defaults={
                    "business_name": seed[0],
                    "owner_first_name": seed[1],
                    "owner_last_name": seed[2],
                    "contact_number": seed[4],
                    "business_type": seed[5],
                    "delivery_time": seed[6],
                    "branch_name": seed[7],
                    "terms_accepted": True,
                    "business_address": pinned_address,
                    "street": seed[9],
                    "barangay": seed[8],
                    "city": "Marawi",
                    "province": "Lanao del Sur",
                    "postal_code": "9700",
                    "location_source": seed[10],
                    "pinned_address": pinned_address if seed[10] == LocationSource.PIN else "",
                    "latitude": lat if seed[10] == LocationSource.PIN else None,
                    "longitude": lng if seed[10] == LocationSource.PIN else None,
                    "status": seed[11],
                    "admin_remarks": seed[12],
                    "requested_fields": seed[13],
                },
            )
            application.business_name = seed[0]
            application.owner_first_name = seed[1]
            application.owner_last_name = seed[2]
            application.contact_number = seed[4]
            application.business_type = seed[5]
            application.delivery_time = seed[6]
            application.branch_name = seed[7]
            application.terms_accepted = True
            application.business_address = pinned_address
            application.street = seed[9]
            application.barangay = seed[8]
            application.city = "Marawi"
            application.province = "Lanao del Sur"
            application.postal_code = "9700"
            application.location_source = seed[10]
            application.pinned_address = pinned_address if seed[10] == LocationSource.PIN else ""
            application.latitude = lat if seed[10] == LocationSource.PIN else None
            application.longitude = lng if seed[10] == LocationSource.PIN else None
            application.status = seed[11]
            application.admin_remarks = seed[12]
            application.requested_fields = seed[13]
            self.attach_merchant_files(application, index)
            application.save()
            self.update_application_timestamps(application, index)
            self.rebuild_application_state(application, admin_user, index)
            applications.append(application)
        return applications

    def seed_riders(self, admin_user):
        applications = []
        for index, seed in enumerate(RIDER_SEEDS, start=1):
            application, _ = RiderApplication.objects.get_or_create(
                email=seed[2],
                defaults={
                    "first_name": seed[0],
                    "last_name": seed[1],
                    "phone_number": seed[3],
                    "terms_accepted": True,
                    "current_address": f"{seed[4]}, Marawi City",
                    "barangay": seed[4],
                    "city": "Marawi",
                    "province": "Lanao del Sur",
                    "postal_code": "9700",
                    "emergency_contact_name": seed[5],
                    "emergency_contact_number": seed[6],
                    "emergency_contact_relationship": seed[7],
                    "vehicle_type": seed[8],
                    "vehicle_brand": seed[9],
                    "plate_number": seed[10],
                    "status": seed[11],
                    "admin_remarks": seed[12],
                    "requested_fields": seed[13],
                },
            )
            application.first_name = seed[0]
            application.last_name = seed[1]
            application.phone_number = seed[3]
            application.terms_accepted = True
            application.current_address = f"{seed[4]}, Marawi City"
            application.barangay = seed[4]
            application.city = "Marawi"
            application.province = "Lanao del Sur"
            application.postal_code = "9700"
            application.emergency_contact_name = seed[5]
            application.emergency_contact_number = seed[6]
            application.emergency_contact_relationship = seed[7]
            application.vehicle_type = seed[8]
            application.vehicle_brand = seed[9]
            application.plate_number = seed[10]
            application.status = seed[11]
            application.admin_remarks = seed[12]
            application.requested_fields = seed[13]
            self.attach_rider_files(application, index)
            application.save()
            self.update_application_timestamps(application, index + 20)
            self.rebuild_application_state(application, admin_user, index + 20)
            applications.append(application)
        return applications

    def attach_merchant_files(self, application, index):
        if not application.dti_sec_certificate:
            application.dti_sec_certificate.save(f"merchant-{index}-dti.pdf", ContentFile(PDF_BYTES), save=False)
        if not application.mayors_permit:
            application.mayors_permit.save(f"merchant-{index}-permit.pdf", ContentFile(PDF_BYTES), save=False)
        if not application.bir_cor:
            application.bir_cor.save(f"merchant-{index}-bir.pdf", ContentFile(PDF_BYTES), save=False)
        if not application.owner_valid_id:
            application.owner_valid_id.save(f"merchant-{index}-id.pdf", ContentFile(PDF_BYTES), save=False)
        if not application.storefront_photo:
            application.storefront_photo.save(f"merchant-{index}-store.png", ContentFile(PNG_BYTES), save=False)
        application.save()

    def attach_rider_files(self, application, index):
        if not application.vehicle_photo_front:
            application.vehicle_photo_front.save(f"rider-{index}-front.png", ContentFile(PNG_BYTES), save=False)
        if not application.vehicle_photo_back:
            application.vehicle_photo_back.save(f"rider-{index}-back.png", ContentFile(PNG_BYTES), save=False)
        if not application.professional_drivers_license:
            application.professional_drivers_license.save(f"rider-{index}-license.pdf", ContentFile(PDF_BYTES), save=False)
        if not application.lto_or_cr:
            application.lto_or_cr.save(f"rider-{index}-orcr.pdf", ContentFile(PDF_BYTES), save=False)
        if not application.nbi_clearance:
            application.nbi_clearance.save(f"rider-{index}-nbi.pdf", ContentFile(PDF_BYTES), save=False)
        if not application.barangay_clearance:
            application.barangay_clearance.save(f"rider-{index}-barangay.pdf", ContentFile(PDF_BYTES), save=False)
        application.save()

    def update_application_timestamps(self, application, offset_days):
        created_at = timezone.now() - timedelta(days=offset_days)
        updated_at = created_at + timedelta(hours=6)
        application.__class__.objects.filter(pk=application.pk).update(created_at=created_at, updated_at=updated_at)

    def rebuild_application_state(self, application, admin_user, offset_days):
        ApplicationStatusHistory.objects.filter(application_id=application.application_id).delete()
        ApplicationEditToken.objects.filter(application_id=application.application_id).delete()
        AccountSetupToken.objects.filter(application_id=application.application_id).delete()

        created_at = timezone.now() - timedelta(days=offset_days)
        submitted_at = created_at + timedelta(minutes=15)
        application_type = "MERCHANT" if isinstance(application, MerchantApplication) else "RIDER"
        ApplicationStatusHistory.objects.create(
            application_id=application.application_id,
            application_type=application_type,
            from_status="",
            to_status=ApplicationStatus.PENDING,
            remarks="Application submitted.",
            created_at=submitted_at,
        )

        if application.status in {ApplicationStatus.UNDER_REVIEW, ApplicationStatus.REQUEST_CHANGES, ApplicationStatus.APPROVED, ApplicationStatus.REJECTED}:
            ApplicationStatusHistory.objects.create(
                application_id=application.application_id,
                application_type=application_type,
                from_status=ApplicationStatus.PENDING,
                to_status=ApplicationStatus.UNDER_REVIEW,
                remarks="Admin started review.",
                actor=admin_user,
                created_at=submitted_at + timedelta(hours=4),
            )

        if application.status == ApplicationStatus.REQUEST_CHANGES:
            ApplicationStatusHistory.objects.create(
                application_id=application.application_id,
                application_type=application_type,
                from_status=ApplicationStatus.UNDER_REVIEW,
                to_status=ApplicationStatus.REQUEST_CHANGES,
                remarks=application.admin_remarks,
                actor=admin_user,
                created_at=submitted_at + timedelta(hours=7),
            )
            ApplicationEditToken.objects.create(
                application_id=application.application_id,
                application_type=application_type,
                requested_fields=application.requested_fields,
                expires_at=timezone.now() + timedelta(days=7),
            )

        if application.status == ApplicationStatus.APPROVED:
            ApplicationStatusHistory.objects.create(
                application_id=application.application_id,
                application_type=application_type,
                from_status=ApplicationStatus.UNDER_REVIEW,
                to_status=ApplicationStatus.APPROVED,
                remarks="Application approved.",
                actor=admin_user,
                created_at=submitted_at + timedelta(hours=8),
            )
            AccountSetupToken.objects.create(
                application_id=application.application_id,
                application_type=application_type,
                expires_at=timezone.now() + timedelta(days=7),
            )

        if application.status == ApplicationStatus.REJECTED:
            ApplicationStatusHistory.objects.create(
                application_id=application.application_id,
                application_type=application_type,
                from_status=ApplicationStatus.UNDER_REVIEW,
                to_status=ApplicationStatus.REJECTED,
                remarks=application.admin_remarks,
                actor=admin_user,
                created_at=submitted_at + timedelta(hours=8),
            )

    def materialize_approved_merchants(self, applications):
        stores = []
        User = get_user_model()
        for app in applications:
            if app.status != ApplicationStatus.APPROVED:
                continue
            if not app.applicant_id:
                username = app.company_email.split("@", 1)[0]
                user, _ = User.objects.get_or_create(
                    username=username,
                    defaults={"email": app.company_email, "phone_number": self.compact_phone(app.contact_number)},
                )
                user.email = app.company_email
                user.phone_number = self.compact_phone(app.contact_number)
                user.set_password("merchant12345")
                user.save()
                app.applicant = user
                app.save(update_fields=["applicant"])
                ApplicationService.assign_role(user, "Merchant")
            store_qs = app.applicant.stores.filter(name=app.business_name, branch_name=app.branch_name)
            if store_qs.exists():
                stores.append(store_qs.first())
            else:
                stores.append(ApplicationService.create_store_for_merchant(app))
        return stores

    def materialize_approved_riders(self, applications):
        profiles = []
        User = get_user_model()
        for app in applications:
            if app.status != ApplicationStatus.APPROVED:
                continue
            if not app.applicant_id:
                username = app.email.split("@", 1)[0]
                user, _ = User.objects.get_or_create(
                    username=username,
                    defaults={"email": app.email, "phone_number": self.compact_phone(app.phone_number)},
                )
                user.email = app.email
                user.phone_number = self.compact_phone(app.phone_number)
                user.set_password("rider12345")
                user.save()
                app.applicant = user
                app.save(update_fields=["applicant"])
                ApplicationService.assign_role(user, "Rider")
            lat, lng = ZONE_COORDS.get(app.barangay, ZONE_COORDS["Poblacion"])
            profile, _ = RiderProfile.objects.get_or_create(
                user=app.applicant,
                defaults={
                    "vehicle_type": app.vehicle_type,
                    "plate_number": app.plate_number,
                    "is_online": True,
                    "is_available": True,
                    "current_latitude": lat,
                    "current_longitude": lng,
                    "balance": Decimal("850.00"),
                },
            )
            profile.vehicle_type = app.vehicle_type
            profile.plate_number = app.plate_number
            profile.is_online = True
            profile.is_available = True
            profile.current_latitude = lat
            profile.current_longitude = lng
            profile.balance = Decimal("850.00")
            profile.save()
            profiles.append(profile)
        return profiles

    def ensure_customers(self):
        User = get_user_model()
        customers = []
        for index in range(1, 7):
            user, _ = User.objects.get_or_create(
                username=f"customer{index}",
                defaults={
                    "email": f"customer{index}@sarig.local",
                    "phone_number": self.compact_phone(f"+63 905-300-10{index:02d}"),
                    "first_name": f"Customer{index}",
                    "last_name": "Mock",
                },
            )
            user.set_password("customer12345")
            user.save()
            customers.append(user)
        return customers

    def ensure_promo_codes(self):
        now = timezone.now()
        promo1, _ = PromoCode.objects.update_or_create(
            code="WELCOME10",
            defaults={
                "discount_type": DiscountType.PERCENTAGE,
                "discount_value": Decimal("10.00"),
                "min_order_amount": Decimal("200.00"),
                "max_discount_amount": Decimal("100.00"),
                "start_date": now - timedelta(days=7),
                "end_date": now + timedelta(days=30),
                "is_active": True,
            },
        )
        promo2, _ = PromoCode.objects.update_or_create(
            code="MARAWI50",
            defaults={
                "discount_type": DiscountType.FIXED,
                "discount_value": Decimal("50.00"),
                "min_order_amount": Decimal("300.00"),
                "max_discount_amount": Decimal("50.00"),
                "start_date": now - timedelta(days=7),
                "end_date": now + timedelta(days=30),
                "is_active": True,
            },
        )
        return [promo1, promo2]

    def seed_orders(self, stores, riders, customers, promo_codes):
        if not stores or not riders or not customers:
            return
        zone_map = {zone.name: zone for zone in ServiceZone.objects.all()}
        seeds = [
            (stores[0], customers[0], riders[0], OrderStatus.DELIVERED, Decimal("420.00"), Decimal("49.00"), Decimal("30.00"), promo_codes[0], Decimal("42.00"), "Saduc Corridor"),
            (stores[0], customers[1], riders[0], OrderStatus.ON_THE_WAY, Decimal("315.00"), Decimal("39.00"), Decimal("22.00"), None, Decimal("0.00"), "Saduc Corridor"),
            (stores[1], customers[2], riders[1], OrderStatus.PREPARING, Decimal("280.00"), Decimal("35.00"), Decimal("18.00"), None, Decimal("0.00"), "Basak Commercial"),
            (stores[1], customers[3], riders[1], OrderStatus.DELIVERED, Decimal("550.00"), Decimal("45.00"), Decimal("28.00"), promo_codes[1], Decimal("50.00"), "Basak Commercial"),
            (stores[0], customers[4], riders[0], OrderStatus.ACCEPTED, Decimal("230.00"), Decimal("30.00"), Decimal("15.00"), None, Decimal("0.00"), "Poblacion Core"),
            (stores[1], customers[5], riders[1], OrderStatus.DELIVERED, Decimal("640.00"), Decimal("55.00"), Decimal("32.00"), None, Decimal("0.00"), "Poblacion Core"),
        ]
        for index, seed in enumerate(seeds, start=1):
            zone = zone_map[seed[9]]
            order, _ = Order.objects.update_or_create(
                delivery_address_text=f"Mock Address {index}",
                defaults={
                    "delivery_method": DeliveryMethod.DELIVERY,
                    "customer": seed[1],
                    "store": seed[0],
                    "rider": seed[2].user,
                    "status": seed[3],
                    "delivery_latitude": zone.center_latitude,
                    "delivery_longitude": zone.center_longitude,
                    "subtotal": seed[4],
                    "delivery_fee": seed[5],
                    "system_fee": seed[6],
                    "total_amount": seed[4] + seed[5] + seed[6] - seed[8],
                    "promo_code": seed[7],
                    "discount_amount": seed[8],
                    "estimated_arrival_time": timezone.now() + timedelta(minutes=20 if seed[3] != OrderStatus.DELIVERED else -15),
                    "delivered_at": timezone.now() - timedelta(hours=1) if seed[3] == OrderStatus.DELIVERED else None,
                },
            )
            PaymentTransaction.objects.update_or_create(
                external_transaction_id=f"mock_order_payment_{index}",
                defaults={
                    "order": order,
                    "amount": order.total_amount,
                    "payment_method": PaymentMethod.COD if index % 2 else PaymentMethod.PAYMONGO,
                    "status": PaymentStatus.SUCCESS if seed[3] == OrderStatus.DELIVERED else PaymentStatus.PENDING,
                },
            )

    def seed_rides(self, riders, customers):
        if not riders or not customers:
            return
        seeds = [
            (customers[0], riders[0], RideStatus.COMPLETED, Decimal("8.003400"), Decimal("124.283900"), Decimal("8.012600"), Decimal("124.291200"), Decimal("95.00")),
            (customers[1], riders[1], RideStatus.MATCHED, Decimal("8.004500"), Decimal("124.299900"), Decimal("8.002900"), Decimal("124.285500"), Decimal("88.00")),
            (customers[2], riders[0], RideStatus.IN_TRIP, Decimal("7.996400"), Decimal("124.285700"), Decimal("8.019200"), Decimal("124.287500"), Decimal("120.00")),
            (customers[3], riders[1], RideStatus.REQUESTED, Decimal("8.000700"), Decimal("124.266600"), Decimal("8.010700"), Decimal("124.277900"), Decimal("110.00")),
        ]
        for index, seed in enumerate(seeds, start=1):
            Ride.objects.update_or_create(
                cancel_reason=f"mock_seed_{index}",
                defaults={
                    "passenger": seed[0],
                    "rider": seed[1],
                    "status": seed[2],
                    "requested_vehicle_type": seed[1].vehicle_type,
                    "assigned_vehicle_type": seed[1].vehicle_type if seed[2] != RideStatus.REQUESTED else None,
                    "pickup_lat": seed[3],
                    "pickup_lng": seed[4],
                    "dropoff_lat": seed[5],
                    "dropoff_lng": seed[6],
                    "estimated_fare": seed[7],
                    "final_fare": seed[7] if seed[2] == RideStatus.COMPLETED else None,
                    "distance_km": Decimal("4.50"),
                    "duration_min": Decimal("18.00"),
                    "matched_at": timezone.now() - timedelta(minutes=20) if seed[2] in {RideStatus.MATCHED, RideStatus.IN_TRIP, RideStatus.COMPLETED} else None,
                    "started_at": timezone.now() - timedelta(minutes=12) if seed[2] in {RideStatus.IN_TRIP, RideStatus.COMPLETED} else None,
                    "completed_at": timezone.now() - timedelta(minutes=1) if seed[2] == RideStatus.COMPLETED else None,
                },
            )

    def seed_zone_snapshots(self):
        ServiceZoneMetricSnapshot.objects.all().delete()
        payloads = [
            ("Poblacion Core", 4, 1, 2, 3, 2, 7, LoadStatus.HIGH),
            ("Saduc Corridor", 3, 1, 1, 2, 1, 9, LoadStatus.WATCH),
            ("Basak Commercial", 2, 0, 2, 2, 1, 4, LoadStatus.STABLE),
            ("Matampay Calocan", 1, 1, 1, 1, 0, 3, LoadStatus.STABLE),
        ]
        for name, active_orders, bookings, available_riders, active_riders, merchants, delay, load in payloads:
            zone = ServiceZone.objects.filter(name=name).first()
            if not zone:
                continue
            ServiceZoneMetricSnapshot.objects.create(
                zone=zone,
                active_orders=active_orders,
                active_transport_bookings=bookings,
                available_riders=available_riders,
                active_riders=active_riders,
                approved_merchants=merchants,
                average_delay_minutes=delay,
                load_status=load,
            )

    def seed_alerts(self):
        alerts = [
            (AlertSeverity.CRITICAL, "Saduc rider shortage", "Available riders in Saduc Corridor dropped below safe threshold."),
            (AlertSeverity.WARNING, "Permit resubmissions pending", "Multiple merchant applications are waiting on document resubmission."),
            (AlertSeverity.INFO, "Morning spike expected", "Poblacion Core shows higher than usual order volume before noon."),
            (AlertSeverity.WARNING, "Delayed deliveries detected", "Two live orders are approaching ETA breach in Saduc Corridor."),
        ]
        for severity, title, message in alerts:
            AdminAlert.objects.update_or_create(
                source="operations-seed",
                title=title,
                defaults={"severity": severity, "message": message, "is_resolved": False},
            )
