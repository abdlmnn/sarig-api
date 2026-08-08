from django.db import migrations


def clear_non_branding_banners(apps, schema_editor):
    Store = apps.get_model("vendors", "Store")
    (
        Store.objects.exclude(banner_image__isnull=True)
        .exclude(banner_image="")
        .exclude(banner_image__startswith="stores/banners/")
        .update(banner_image=None)
    )


class Migration(migrations.Migration):
    dependencies = [
        ("vendors", "0014_consolidate_store_images"),
    ]

    operations = [
        migrations.RunPython(
            clear_non_branding_banners,
            migrations.RunPython.noop,
        ),
    ]
