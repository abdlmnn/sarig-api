from django.db import migrations, models
from django.utils.text import slugify


def populate_store_slugs(apps, schema_editor):
    Store = apps.get_model("vendors", "Store")
    used_slugs = set()
    for store in Store.objects.order_by("created_at", "id"):
        base = slugify(store.name)[:260] or str(store.id)
        candidate = base
        if candidate in used_slugs:
            branch = slugify(store.branch_name)[:80]
            if branch:
                candidate = f"{base[:199]}-{branch}"
        suffix = 2
        while candidate in used_slugs:
            candidate = f"{base[:270 - len(str(suffix))]}-{suffix}"
            suffix += 1
        store.slug = candidate
        store.save(update_fields=["slug"])
        used_slugs.add(candidate)


class Migration(migrations.Migration):
    dependencies = [
        ("vendors", "0010_store_branding_images"),
    ]

    operations = [
        migrations.AddField(
            model_name="store",
            name="slug",
            field=models.CharField(blank=True, max_length=280, null=True),
        ),
        migrations.RunPython(populate_store_slugs, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="store",
            name="slug",
            field=models.SlugField(blank=True, max_length=280, unique=True),
        ),
    ]
