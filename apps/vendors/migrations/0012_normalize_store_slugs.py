from django.db import migrations
from django.utils.text import slugify


def normalize_store_slugs(apps, schema_editor):
    Store = apps.get_model("vendors", "Store")
    stores = list(Store.objects.order_by("created_at", "id"))
    reserved_slugs = {store.slug for store in stores}
    for store in stores:
        candidate = f"slug-migration-{store.id}"
        while candidate in reserved_slugs:
            candidate = f"temporary-{candidate}"
        reserved_slugs.discard(store.slug)
        reserved_slugs.add(candidate)
        store.slug = candidate
        store.save(update_fields=["slug"])

    used_slugs = set()
    for store in stores:
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
        ("vendors", "0011_store_slug"),
    ]

    operations = [
        migrations.RunPython(normalize_store_slugs, migrations.RunPython.noop),
    ]
