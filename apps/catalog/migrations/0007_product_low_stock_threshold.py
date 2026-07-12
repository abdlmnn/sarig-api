from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0006_ensure_product_sku_column"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="low_stock_threshold",
            field=models.PositiveIntegerField(default=5),
        ),
    ]
