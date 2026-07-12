from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0006_ensure_product_sku_column"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE catalog_product "
                        "ADD COLUMN IF NOT EXISTS low_stock_threshold integer "
                        "NOT NULL DEFAULT 5"
                    ),
                    reverse_sql=migrations.RunSQL.noop,
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="product",
                    name="low_stock_threshold",
                    field=models.PositiveIntegerField(default=5),
                ),
            ],
        ),
    ]
