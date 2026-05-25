"""Profil patient : création paresseuse si l'utilisateur est patient (comptes anciens / admin)."""

from __future__ import annotations

from datetime import date

from django.contrib.auth.models import AbstractBaseUser

from .models import DossierMedical, Patient


def ensure_patient_for_user(user: AbstractBaseUser) -> Patient | None:
    """
    Retourne le Patient lié à l'utilisateur, ou le crée avec des valeurs par défaut
    (même logique que le signal post_save).
    Retourne None si l'utilisateur n'est pas un patient.
    """
    if getattr(user, "role", None) != "patient":
        return None
    p, _ = Patient.objects.get_or_create(
        user=user,
        defaults={
            "date_naissance": date(2000, 1, 1),
            "telephone": "",
        },
    )
    DossierMedical.objects.get_or_create(patient=p)
    return p
