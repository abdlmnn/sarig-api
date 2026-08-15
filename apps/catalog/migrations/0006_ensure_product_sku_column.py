from django.db import migrations


def ensure_sku_column(apps, schema_editor):
    table_name = "catalog_product"
    column_names = {
        column.name
        for column in schema_editor.connection.introspection.get_table_description(
            schema_editor.connection.cursor(),
            table_name,
        )
    }
    if "sku" in column_names:
        return
    schema_editor.execute(
        "ALTER TABLE catalog_product "
        "ADD COLUMN sku varchar(80) NOT NULL DEFAULT ''"
    )


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0005_product_sku"),
    ]

    operations = [
        migrations.RunPython(ensure_sku_column, reverse_code=migrations.RunPython.noop),
        migrations.RunSQL(
            sql=(
                "CREATE INDEX IF NOT EXISTS catalog_product_sku_idx "
                "ON catalog_product (sku);"
            ),
            reverse_sql="DROP INDEX IF EXISTS catalog_product_sku_idx;",
        ),
    ]
