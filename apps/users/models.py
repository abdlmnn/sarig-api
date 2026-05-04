from django.db import models
from django.contrib.auth.models import AbstractUser


class Role(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name


class User(AbstractUser):
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=15, unique=True, null=True, blank=True)
    roles = models.ManyToManyField(Role, blank=True)

    # Keep this incredibly simple. Just authentication fields.


class Profile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    avatar = models.ImageField(
        upload_to="avatars/",
        height_field=None,
        width_field=None,
        max_length=None,
        null=True,
        blank=True,
    )
    date_of_birth = models.DateField(null=True, blank=True)

    # Any other personal info goes here, NOT in the User model


class Address(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="addresses",
    )
    # e.g., "Home", "Office"
    label = models.CharField(max_length=50)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    street_address = models.TextField()
    is_default = models.BooleanField(default=False)
