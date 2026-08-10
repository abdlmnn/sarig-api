# Generated manually for configured customer cart lines.

from django.db import migrations, models


def populate_line_keys(apps, schema_editor):
    CustomerCartItem = apps.get_model("orders", "CustomerCartItem")
    for item in CustomerCartItem.objects.all().iterator():
        item.line_key = str(item.product_id)
        item.save(update_fields=["line_key"])


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0010_rename_catalog_pro_name_69b43c_idx_catalog_pro_name_ce9885_idx_and_more"),
        ("orders", "0006_customercart_customercartitem_and_more"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="customercartitem",
            name="unique_product_per_customer_cart",
        ),
        migrations.AddField(
            model_name="customercartitem",
            name="line_key",
            field=models.CharField(blank=True, db_index=True, max_length=1500),
        ),
        migrations.RunPython(populate_line_keys, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="customercartitem",
            name="line_key",
            field=models.CharField(db_index=True, max_length=1500),
        ),
        migrations.AddField(
            model_name="customercartitem",
            name="modifiers",
            field=models.ManyToManyField(blank=True, to="catalog.modifieritem"),
        ),
        migrations.AddConstraint(
            model_name="customercartitem",
            constraint=models.UniqueConstraint(
                fields=("cart", "line_key"),
                name="unique_line_per_customer_cart",
            ),
        ),
    ]
