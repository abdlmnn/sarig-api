import uuid

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("vendors", "0007_businessvertical_product_rules"),
        ("catalog", "0008_categorytemplate"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProductReference",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=255)),
                ("brand_name", models.CharField(blank=True, max_length=255)),
                ("barcode", models.CharField(blank=True, db_index=True, max_length=80)),
                ("description", models.TextField(blank=True)),
                ("product_type", models.CharField(choices=[("food", "Food"), ("medicine", "Medicine"), ("grocery", "Grocery"), ("general", "General")], db_index=True, default="grocery", max_length=20)),
                ("unit_type", models.CharField(blank=True, choices=[("piece", "Piece"), ("pack", "Pack"), ("bottle", "Bottle"), ("can", "Can"), ("kilo", "Kilo"), ("gram", "Gram"), ("liter", "Liter"), ("sachet", "Sachet"), ("box", "Box"), ("dozen", "Dozen"), ("tablet", "Tablet"), ("capsule", "Capsule")], max_length=20)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("source", models.CharField(blank=True, max_length=80)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("vertical", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="product_references", to="vendors.businessvertical")),
            ],
            options={
                "ordering": ["vertical__slug", "name", "brand_name"],
            },
        ),
        migrations.AddIndex(
            model_name="productreference",
            index=models.Index(fields=["name"], name="catalog_pro_name_69b43c_idx"),
        ),
        migrations.AddIndex(
            model_name="productreference",
            index=models.Index(fields=["brand_name"], name="catalog_pro_brand_n_0ead5f_idx"),
        ),
        migrations.AddIndex(
            model_name="productreference",
            index=models.Index(fields=["barcode"], name="catalog_pro_barcode_740c23_idx"),
        ),
    ]
