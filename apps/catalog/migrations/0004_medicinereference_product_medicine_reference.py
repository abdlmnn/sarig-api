import uuid
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0003_product_type_unit_prescription_inventory_mode"),
    ]

    operations = [
        migrations.CreateModel(
            name="MedicineReference",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("registration_number", models.CharField(db_index=True, max_length=80, unique=True)),
                ("product_information", models.CharField(blank=True, max_length=255)),
                ("generic_name", models.CharField(max_length=255)),
                ("brand_name", models.CharField(blank=True, max_length=255)),
                ("dosage_strength", models.CharField(blank=True, max_length=255)),
                ("dosage_form", models.CharField(blank=True, max_length=255)),
                ("classification", models.CharField(blank=True, max_length=255)),
                ("pharmacologic_category", models.CharField(blank=True, max_length=255)),
                ("packaging", models.TextField(blank=True)),
                ("manufacturer", models.CharField(blank=True, max_length=255)),
                ("country_of_origin", models.CharField(blank=True, max_length=120)),
                ("trader", models.CharField(blank=True, max_length=255)),
                ("importer", models.CharField(blank=True, max_length=255)),
                ("distributor", models.CharField(blank=True, max_length=255)),
                ("expiry_date", models.DateField(blank=True, db_index=True, null=True)),
                ("requires_prescription", models.BooleanField(db_index=True, default=False)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("source", models.CharField(default="FDA Philippines", max_length=80)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["generic_name", "brand_name", "registration_number"],
                "indexes": [
                    models.Index(fields=["generic_name"], name="catalog_med_generic_784c71_idx"),
                    models.Index(fields=["brand_name"], name="catalog_med_brand_n_6cfd9d_idx"),
                    models.Index(fields=["classification"], name="catalog_med_classif_8340e2_idx"),
                ],
            },
        ),
        migrations.AddField(
            model_name="product",
            name="medicine_reference",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="products", to="catalog.medicinereference"),
        ),
    ]
