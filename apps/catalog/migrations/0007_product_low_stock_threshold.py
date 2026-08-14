from django.db import migrations, models


def ensure_low_stock_threshold_column(apps, schema_editor):
    table_name = "catalog_product"
    column_names = {
        column.name
        for column in schema_editor.connection.introspection.get_table_description(
            schema_editor.connection.cursor(),
            table_name,
        )
    }
    if "low_stock_threshold" in column_names:
        return
    schema_editor.execute(
        "ALTER TABLE catalog_product "
        "ADD COLUMN low_stock_threshold integer NOT NULL DEFAULT 5"
    )


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0006_ensure_product_sku_column"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    ensure_low_stock_threshold_column,
                    reverse_code=migrations.RunPython.noop,
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
