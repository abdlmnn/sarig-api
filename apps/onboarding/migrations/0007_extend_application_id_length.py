from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("onboarding", "0006_merchantapplication_pharmacy_license"),
    ]

    operations = [
        migrations.AlterField(
            model_name="accountsetuptoken",
            name="application_id",
            field=models.CharField(db_index=True, max_length=40),
        ),
        migrations.AlterField(
            model_name="applicationedittoken",
            name="application_id",
            field=models.CharField(db_index=True, max_length=40),
        ),
        migrations.AlterField(
            model_name="applicationstatushistory",
            name="application_id",
            field=models.CharField(db_index=True, max_length=40),
        ),
        migrations.AlterField(
            model_name="merchantapplication",
            name="application_id",
            field=models.CharField(blank=True, db_index=True, max_length=40, unique=True),
        ),
        migrations.AlterField(
            model_name="riderapplication",
            name="application_id",
            field=models.CharField(blank=True, db_index=True, max_length=40, unique=True),
        ),
    ]
