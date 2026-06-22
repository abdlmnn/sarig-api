# Generated manually for the operations admin dashboard MVP.

import django.db.models.deletion
import django.utils.timezone
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ServiceZone",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=120)),
                ("slug", models.SlugField(max_length=140, unique=True)),
                ("city", models.CharField(default="Marawi", max_length=100)),
                ("province", models.CharField(default="Lanao del Sur", max_length=100)),
                ("center_latitude", models.DecimalField(decimal_places=6, max_digits=9)),
                ("center_longitude", models.DecimalField(decimal_places=6, max_digits=9)),
                ("boundary", models.JSONField(blank=True, default=dict)),
                ("barangay_names", models.JSONField(blank=True, default=list)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("priority", models.PositiveIntegerField(db_index=True, default=100)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["priority", "name"],
            },
        ),
        migrations.CreateModel(
            name="AdminAlert",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("severity", models.CharField(choices=[("info", "Info"), ("warning", "Warning"), ("critical", "Critical")], db_index=True, default="info", max_length=20)),
                ("title", models.CharField(max_length=160)),
                ("message", models.TextField()),
                ("source", models.CharField(db_index=True, default="operations", max_length=80)),
                ("is_resolved", models.BooleanField(db_index=True, default=False)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("resolved_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="resolved_admin_alerts", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="ServiceZoneMetricSnapshot",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("active_orders", models.PositiveIntegerField(default=0)),
                ("active_transport_bookings", models.PositiveIntegerField(default=0)),
                ("available_riders", models.PositiveIntegerField(default=0)),
                ("active_riders", models.PositiveIntegerField(default=0)),
                ("approved_merchants", models.PositiveIntegerField(default=0)),
                ("average_delay_minutes", models.PositiveIntegerField(default=0)),
                ("load_status", models.CharField(choices=[("STABLE", "Stable"), ("HIGH", "High"), ("WATCH", "Watch")], default="STABLE", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("zone", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="metric_snapshots", to="operations.servicezone")),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="ServiceZoneAssignment",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("entity_type", models.CharField(choices=[("STORE", "Store"), ("RIDER", "Rider"), ("ORDER", "Order"), ("RIDE", "Ride")], max_length=20)),
                ("entity_id", models.UUIDField(db_index=True)),
                ("source", models.CharField(choices=[("AUTO", "Auto"), ("MANUAL", "Manual")], default="MANUAL", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("zone", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="assignments", to="operations.servicezone")),
            ],
            options={
                "unique_together": {("entity_type", "entity_id")},
            },
        ),
        migrations.AddIndex(
            model_name="servicezone",
            index=models.Index(fields=["city", "is_active"], name="operations__city_3a797e_idx"),
        ),
        migrations.AddIndex(
            model_name="servicezone",
            index=models.Index(fields=["priority"], name="operations__priorit_b35060_idx"),
        ),
        migrations.AddIndex(
            model_name="adminalert",
            index=models.Index(fields=["severity", "is_resolved"], name="operations__severit_0e5710_idx"),
        ),
        migrations.AddIndex(
            model_name="adminalert",
            index=models.Index(fields=["source", "created_at"], name="operations__source_ece78d_idx"),
        ),
        migrations.AddIndex(
            model_name="servicezonemetricsnapshot",
            index=models.Index(fields=["zone", "-created_at"], name="operations__zone_id_1a39a5_idx"),
        ),
        migrations.AddIndex(
            model_name="servicezonemetricsnapshot",
            index=models.Index(fields=["load_status", "created_at"], name="operations__load_st_0528d5_idx"),
        ),
        migrations.AddIndex(
            model_name="servicezoneassignment",
            index=models.Index(fields=["entity_type", "entity_id"], name="operations__entity__a9a271_idx"),
        ),
        migrations.AddIndex(
            model_name="servicezoneassignment",
            index=models.Index(fields=["zone", "entity_type"], name="operations__zone_id_c35a9a_idx"),
        ),
    ]
