from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0002_paymenttransaction_payment_id"),
    ]

    operations = [
        migrations.AlterField(
            model_name="paymenttransaction",
            name="status",
            field=models.CharField(
                choices=[
                    ("PENDING", "Pending/Awaiting Payment"),
                    ("AUTHORIZED", "Authorized (Funds held, not captured)"),
                    ("SUCCESS", "Payment Successful"),
                    ("FAILED", "Payment Failed"),
                    ("EXPIRED", "Payment Expired"),
                    ("REFUNDED", "Payment Refunded"),
                ],
                db_index=True,
                default="PENDING",
                max_length=20,
            ),
        ),
    ]
