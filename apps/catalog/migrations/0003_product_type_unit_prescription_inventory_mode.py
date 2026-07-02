from django.db import migrations, models


def backfill_inventory_mode(apps, schema_editor):
    Product = apps.get_model("catalog", "Product")
    Product.objects.filter(track_inventory=True).update(inventory_mode="simple_stock")
    Product.objects.filter(track_inventory=False).update(inventory_mode="none", stock_quantity=None)


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0002_product_stock_quantity_product_track_inventory_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="brand_name",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="product",
            name="dosage",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="product",
            name="generic_name",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="product",
            name="inventory_mode",
            field=models.CharField(choices=[("none", "No stock tracking"), ("simple_stock", "Simple stock")], default="none", max_length=20),
        ),
        migrations.AddField(
            model_name="product",
            name="medicine_form",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="product",
            name="preparation_time_minutes",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="product",
            name="product_type",
            field=models.CharField(choices=[("food", "Food"), ("medicine", "Medicine"), ("grocery", "Grocery"), ("general", "General")], db_index=True, default="general", max_length=20),
        ),
        migrations.AddField(
            model_name="product",
            name="requires_prescription",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="product",
            name="unit_type",
            field=models.CharField(blank=True, choices=[("piece", "Piece"), ("pack", "Pack"), ("bottle", "Bottle"), ("can", "Can"), ("kilo", "Kilo"), ("gram", "Gram"), ("liter", "Liter"), ("sachet", "Sachet"), ("box", "Box"), ("dozen", "Dozen"), ("tablet", "Tablet"), ("capsule", "Capsule")], max_length=20),
        ),
        migrations.AlterField(
            model_name="product",
            name="stock_quantity",
            field=models.PositiveIntegerField(blank=True, default=None, null=True),
        ),
        migrations.RunPython(backfill_inventory_mode, migrations.RunPython.noop),
    ]
