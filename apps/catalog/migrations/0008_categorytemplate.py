from django.db import migrations, models
import django.db.models.deletion
import uuid


CATEGORY_TEMPLATES = {
    "restaurant": [
        ("Rice Meals", "rice-meals", "Main rice meals and plated meals."),
        ("Chicken", "chicken", "Chicken dishes and combos."),
        ("Burgers And Sandwiches", "burgers-and-sandwiches", "Burgers, sandwiches, wraps, and handheld meals."),
        ("Pasta", "pasta", "Pasta dishes and sauce-based meals."),
        ("Snacks", "snacks", "Light meals, sides, and quick bites."),
        ("Drinks", "drinks", "Beverages and refreshments."),
        ("Desserts", "desserts", "Sweets and dessert items."),
    ],
    "pharmacy": [
        ("Pain Relief", "pain-relief", "Pain relief and fever medicines."),
        ("Antibiotics", "antibiotics", "Antibiotic medicines that may require prescription checks."),
        ("Vitamins And Supplements", "vitamins-and-supplements", "Vitamins, minerals, and supplements."),
        ("First Aid", "first-aid", "Wound care, antiseptics, and first aid essentials."),
        ("Cough And Cold", "cough-and-cold", "Cough, cold, flu, and allergy products."),
        ("Baby Care", "baby-care", "Baby health and care products."),
        ("Personal Care", "personal-care", "Health, hygiene, and personal care products."),
    ],
    "grocery": [
        ("Rice And Staples", "rice-and-staples", "Rice, grains, noodles, and pantry staples."),
        ("Canned Goods", "canned-goods", "Canned foods and preserved goods."),
        ("Beverages", "beverages", "Drinks, water, juice, coffee, and tea."),
        ("Snacks", "snacks", "Chips, biscuits, sweets, and snack items."),
        ("Household", "household", "Cleaning and household essentials."),
        ("Frozen Goods", "frozen-goods", "Frozen meat, meals, and chilled goods."),
        ("Personal Care", "personal-care", "Hygiene and care products."),
    ],
    "market": [
        ("Vegetables", "vegetables", "Fresh vegetables and produce."),
        ("Fruits", "fruits", "Fresh fruits and seasonal produce."),
        ("Meat", "meat", "Fresh meat and butcher items."),
        ("Fish And Seafood", "fish-and-seafood", "Fish, seafood, and related market goods."),
        ("Dry Goods", "dry-goods", "Dry market goods and packaged staples."),
        ("Rice And Staples", "rice-and-staples", "Rice, grains, and basic staples."),
    ],
    "convenience-store": [
        ("Beverages", "beverages", "Ready-to-drink beverages and bottled water."),
        ("Snacks", "snacks", "Quick snacks and convenience items."),
        ("Ready To Eat", "ready-to-eat", "Ready-to-eat meals and packed food."),
        ("Personal Care", "personal-care", "Personal hygiene and daily care."),
        ("Household", "household", "Small household essentials."),
        ("Load And Essentials", "load-and-essentials", "Load cards, batteries, and common essentials."),
    ],
    "general-store": [
        ("Household", "household", "Household supplies and common home items."),
        ("Personal Care", "personal-care", "Personal care and hygiene products."),
        ("School Supplies", "school-supplies", "School and office supplies."),
        ("Hardware", "hardware", "Basic hardware and repair items."),
        ("Dry Goods", "dry-goods", "Dry goods and small retail products."),
        ("Essentials", "essentials", "Everyday essentials and common store items."),
    ],
    "bakery": [
        ("Bread", "bread", "Breads, rolls, and baked staples."),
        ("Cakes", "cakes", "Cakes and celebration bakes."),
        ("Pastries", "pastries", "Pastries and filled baked goods."),
        ("Cookies", "cookies", "Cookies and small baked treats."),
        ("Drinks", "drinks", "Beverages sold with baked goods."),
        ("Specialty Bakes", "specialty-bakes", "Specialty, seasonal, and custom bakery items."),
    ],
}


def seed_category_templates(apps, schema_editor):
    BusinessVertical = apps.get_model("vendors", "BusinessVertical")
    CategoryTemplate = apps.get_model("catalog", "CategoryTemplate")

    for vertical_slug, templates in CATEGORY_TEMPLATES.items():
        vertical = BusinessVertical.objects.filter(slug=vertical_slug).first()
        if not vertical:
            continue
        for index, (name, slug, description) in enumerate(templates, start=1):
            CategoryTemplate.objects.update_or_create(
                vertical=vertical,
                slug=slug,
                defaults={
                    "name": name,
                    "description": description,
                    "order": index,
                    "is_active": True,
                },
            )


def remove_category_templates(apps, schema_editor):
    CategoryTemplate = apps.get_model("catalog", "CategoryTemplate")
    CategoryTemplate.objects.filter(
        vertical__slug__in=list(CATEGORY_TEMPLATES.keys())
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("vendors", "0009_store_availability_controls"),
        ("catalog", "0007_product_low_stock_threshold"),
    ]

    operations = [
        migrations.CreateModel(
            name="CategoryTemplate",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=100)),
                ("slug", models.SlugField(max_length=120)),
                ("description", models.TextField(blank=True)),
                ("order", models.PositiveIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "vertical",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="category_templates",
                        to="vendors.businessvertical",
                    ),
                ),
            ],
            options={
                "ordering": ["vertical__slug", "order", "name"],
                "unique_together": {("vertical", "slug")},
            },
        ),
        migrations.RunPython(seed_category_templates, remove_category_templates),
    ]
