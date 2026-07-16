from django.db.models.signals import pre_save
from django.dispatch import receiver

from .models import User


@receiver(pre_save, sender=User)
def revoke_sessions_when_user_is_deactivated(sender, instance, **kwargs):
    if not instance.pk or instance.is_active:
        return
    was_active = sender.objects.filter(pk=instance.pk, is_active=True).exists()
    if was_active:
        from .auth_sessions import revoke_user_refresh_tokens

        revoke_user_refresh_tokens(instance)
