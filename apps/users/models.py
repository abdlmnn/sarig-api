from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
  email = models.EmailField(unique=True)

class Role(models.IntegerChoices):
  SEEKER = 1, 'Job Seeker'
  EMPLOYER = 2, 'Employer'
  ADMIN = 3, 'Admin'

class VerificationLevel(models.IntegerChoices):
  UNVERIFIED = 0, 'Unverified'
  COMMUNITY = 1, 'Community Verified'
  ADMIN = 2, 'Admin Verified'

class Barangay(models.Model):
  name = models.CharField(
    max_length=100,
    unique=True
  )

  def __str__(self):
      return self.name

class UserProfile(models.Model):
  user = models.OneToOneField(
    User,
    on_delete=models.CASCADE,
    related_name="profile"
  )
  role = models.IntegerField(
    choices=Role.choices,
    default=Role.SEEKER
  )
  phone_number = models.CharField(
    max_length=20,
    blank=True
  )
  barangay = models.ForeignKey(
    Barangay,
    on_delete=models.SET_NULL,
    null=True,
    blank=True
  )
  verification_status = models.IntegerField(
    choices=VerificationLevel.choices,
    default=VerificationLevel.UNVERIFIED
  )
  created_at = models.DateField(auto_now_add=True)

  class Meta:
    indexes = [
      models.Index(fields=["role"]),
      models.Index(fields=["verification_status"])
    ]

  def __str__(self):
      return f"{self.user.username} profile"
