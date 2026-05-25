"""Assure une ligne Medecin pour chaque compte utilisateur avec rôle médecin."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractBaseUser

from .models import Medecin


def ensure_medecin_for_single_user(user: AbstractBaseUser) -> Medecin | None:
    """Crée le profil Medecin si l'utilisateur est médecin et qu'il manque."""
    if getattr(user, "role", None) != "doctor":
        return None
    m, _ = Medecin.objects.get_or_create(
        user=user,
        defaults={"specialite": "Cardiologie"},
    )
    return m


def ensure_medecin_for_doctor_users() -> int:
    """
    Crée les profils Medecin manquants (lien 1–1 avec User role=doctor).
    Retourne le nombre de profils créés.
    """
    User = get_user_model()
    created = 0
    for u in User.objects.filter(role="doctor"):
        _, was_created = Medecin.objects.get_or_create(
            user=u,
            defaults={"specialite": "Cardiologie"},
        )
        if was_created:
            created += 1
    return created


def medecins_for_appointments():
    """
    Tous les profils « Médecin » liés à un compte actif rôle médecin,
    prêts pour les listes de réservation (landing + espace patient).
    """
    ensure_medecin_for_doctor_users()
    return (
        Medecin.objects.select_related("user")
        .filter(user__role="doctor", user__is_active=True)
        .order_by("user__last_name", "user__first_name", "user__username")
    )
