from django.contrib.auth import get_user_model
from django.db.models.signals import post_save

from .medecin_utils import ensure_medecin_for_single_user
from .secretary_utils import ensure_secretaire_for_single_user


def connect_accounts_signals():
    User = get_user_model()
    post_save.connect(
        _on_user_saved,
        sender=User,
        dispatch_uid="accounts.ensure_staff_profiles",
    )


def _on_user_saved(sender, instance, **kwargs):
    role = getattr(instance, "role", None)
    if role == "doctor":
        ensure_medecin_for_single_user(instance)
    elif role == "secretary":
        ensure_secretaire_for_single_user(instance)
