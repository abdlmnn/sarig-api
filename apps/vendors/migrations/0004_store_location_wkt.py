# Generated manually for Phase 2B dual-mode geo column.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("vendors", "0003_store_auto_accept_orders"),
    ]

    operations = [
        migrations.AddField(
            model_name="store",
            name="location_wkt",
            field=models.CharField(blank=True, db_index=True, max_length=120, null=True),
        ),
    ]
