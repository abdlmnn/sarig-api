# Generated manually for Phase 2B dual-mode geo column.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("riders", "0004_remove_riderprofile_riders_ride_is_onli_6dda04_idx_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="riderprofile",
            name="location_wkt",
            field=models.CharField(blank=True, db_index=True, max_length=120, null=True),
        ),
    ]
