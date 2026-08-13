from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0009_orderprescription_multiple_files"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="delivery_option",
            field=models.CharField(
                choices=[
                    ("SAVER", "Saver"),
                    ("STANDARD", "Standard"),
                    ("PRIORITY", "Priority"),
                ],
                db_index=True,
                default="STANDARD",
                max_length=20,
            ),
        ),
    ]
