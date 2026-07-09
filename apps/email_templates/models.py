from django.db import models


class EmailTemplate(models.Model):
    key = models.SlugField(max_length=120, unique=True)
    name = models.CharField(max_length=160)
    subject = models.CharField(max_length=255)
    body = models.TextField()
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("key",)

    def __str__(self):
        return self.name
