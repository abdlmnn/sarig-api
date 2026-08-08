from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("vendors", "0013_protect_store_slug"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="store",
            name="image",
        ),
    ]
