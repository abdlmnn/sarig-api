from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0005_product_sku"),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                "ALTER TABLE catalog_product "
                "ADD COLUMN IF NOT EXISTS sku varchar(80) NOT NULL DEFAULT '';"
            ),
            reverse_sql=(
                "ALTER TABLE catalog_product "
                "DROP COLUMN IF EXISTS sku;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "CREATE INDEX IF NOT EXISTS catalog_product_sku_idx "
                "ON catalog_product (sku);"
            ),
            reverse_sql="DROP INDEX IF EXISTS catalog_product_sku_idx;",
        ),
    ]
