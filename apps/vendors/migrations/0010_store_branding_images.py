from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("vendors", "0009_store_availability_controls"),
    ]

    operations = [
        migrations.AddField(
            model_name="store",
            name="banner_image",
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to="stores/banners/",
            ),
        ),
        migrations.AddField(
            model_name="store",
            name="logo_image",
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to="stores/logos/",
            ),
        ),
    ]
