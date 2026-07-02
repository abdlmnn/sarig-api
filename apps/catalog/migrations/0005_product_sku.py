from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0004_medicinereference_product_medicine_reference"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="sku",
            field=models.CharField(blank=True, db_index=True, max_length=80),
        ),
    ]
