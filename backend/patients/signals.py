from django.db.models.signals import post_save

from .patient_utils import ensure_patient_for_user


def ensure_patient_profile_and_dossier(sender, instance, **kwargs):
    ensure_patient_for_user(instance)


def connect_patient_signals():
    from django.contrib.auth import get_user_model

    post_save.connect(ensure_patient_profile_and_dossier, sender=get_user_model())
