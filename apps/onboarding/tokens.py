import uuid

from django.core import signing

from .models import AccountSetupToken


ACCOUNT_SETUP_TOKEN_SALT = "onboarding.account-setup"


def encode_account_setup_token(invitation):
    return signing.dumps({"invitation_id": str(invitation.pk)}, salt=ACCOUNT_SETUP_TOKEN_SALT, compress=True)


def resolve_account_setup_token(value, *, for_update=False):
    queryset = AccountSetupToken.objects.select_for_update() if for_update else AccountSetupToken.objects.all()
    try:
        payload = signing.loads(value, salt=ACCOUNT_SETUP_TOKEN_SALT)
        invitation_id = uuid.UUID(payload["invitation_id"])
        return queryset.get(pk=invitation_id)
    except (signing.BadSignature, KeyError, TypeError, ValueError, AccountSetupToken.DoesNotExist):
        pass

    # Compatibility for invitations issued before signed setup links.
    try:
        return queryset.get(token=uuid.UUID(str(value)))
    except (ValueError, AccountSetupToken.DoesNotExist):
        return None
