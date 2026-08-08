from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("vendors", "0012_normalize_store_slugs"),
    ]

    operations = [
        migrations.AlterField(
            model_name="store",
            name="slug",
            field=models.SlugField(editable=False, max_length=280, unique=True),
        ),
        migrations.AddConstraint(
            model_name="store",
            constraint=models.CheckConstraint(
                condition=~models.Q(slug=""),
                name="vendors_store_slug_not_blank",
            ),
        ),
    ]
