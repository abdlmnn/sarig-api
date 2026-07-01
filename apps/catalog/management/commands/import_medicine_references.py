import csv
from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_date

from apps.catalog.models import MedicineReference


def clean_text(value):
    return " ".join(str(value or "").replace("\r", " ").replace("\n", " ").split()).strip()


def none_if_placeholder(value):
    value = clean_text(value)
    return "" if value.upper() in {"N/A", "NA", "NONE", "-"} else value


def bounded(value, max_length):
    return none_if_placeholder(value)[:max_length]


def parse_expiry(value):
    value = clean_text(value)
    if not value:
        return None
    parsed = parse_date(value)
    if parsed:
        return parsed
    for fmt in ("%d %B %Y", "%d %b %Y"):
        try:
            from datetime import datetime

            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def is_prescription(classification):
    return "PRESCRIPTION" in clean_text(classification).upper() or "(RX)" in clean_text(classification).upper()


class Command(BaseCommand):
    help = "Import FDA medicine reference data from data/drug_products.csv."

    def add_arguments(self, parser):
        parser.add_argument("csv_path", nargs="?", default="data/drug_products.csv")
        parser.add_argument("--include-expired", action="store_true", help="Import expired rows as inactive references.")

    def handle(self, *args, **options):
        path = Path(options["csv_path"])
        if not path.exists():
            raise CommandError(f"CSV file not found: {path}")

        today = date.today()
        stats = {
            "created": 0,
            "updated": 0,
            "skipped_expired": 0,
            "skipped_missing_registration": 0,
            "skipped_missing_generic": 0,
            "duplicates": 0,
        }
        seen_registration_numbers = set()

        with path.open(newline="", encoding="utf-8-sig") as csv_file:
            reader = csv.DictReader(csv_file)
            for row in reader:
                registration_number = clean_text(row.get("Registration Number"))
                generic_name = none_if_placeholder(row.get("Generic Name"))
                if not registration_number:
                    stats["skipped_missing_registration"] += 1
                    continue
                if registration_number in seen_registration_numbers:
                    stats["duplicates"] += 1
                seen_registration_numbers.add(registration_number)
                if not generic_name:
                    stats["skipped_missing_generic"] += 1
                    continue

                expiry_date = parse_expiry(row.get("Expiry Date"))
                active = expiry_date is None or expiry_date >= today
                if not active and not options["include_expired"]:
                    stats["skipped_expired"] += 1
                    continue

                defaults = {
                    "product_information": bounded(row.get("Product Information"), 255),
                    "generic_name": generic_name[:255],
                    "brand_name": bounded(row.get("Brand Name"), 255),
                    "dosage_strength": bounded(row.get("Dosage Strength"), 255),
                    "dosage_form": bounded(row.get("Dosage Form"), 255),
                    "classification": bounded(row.get("Classification"), 255),
                    "pharmacologic_category": bounded(row.get("Pharmacologic Category"), 255),
                    "packaging": none_if_placeholder(row.get("Packaging")),
                    "manufacturer": bounded(row.get("Manufacturer"), 255),
                    "country_of_origin": bounded(row.get("Country of Origin"), 120),
                    "trader": bounded(row.get("Trader"), 255),
                    "importer": bounded(row.get("Importer"), 255),
                    "distributor": bounded(row.get("Distributor"), 255),
                    "expiry_date": expiry_date,
                    "requires_prescription": is_prescription(row.get("Classification")),
                    "is_active": active,
                }
                _, created = MedicineReference.objects.update_or_create(
                    registration_number=registration_number,
                    defaults=defaults,
                )
                stats["created" if created else "updated"] += 1

        self.stdout.write(self.style.SUCCESS(f"Medicine reference import complete: {stats}"))
