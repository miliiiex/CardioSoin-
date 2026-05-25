"""Assure une ligne Secretaire pour chaque compte utilisateur avec rôle secrétaire (admin, etc.)."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractBaseUser

from .models import Secretaire


def ensure_secretaire_for_single_user(user: AbstractBaseUser) -> Secretaire | None:
    if getattr(user, "role", None) != "secretary":
        return None
    s, _ = Secretaire.objects.get_or_create(
        user=user,
        defaults={"telephone": ""},
    )
    return s


def ensure_secretaire_backfill() -> int:
    """
    Crée les profils Secretaire manquants (même rôle=secretary, ajout manuel
    en base / anciennes données). Utile au démarrage pour réparer l’existant.
    """
    User = get_user_model()
    created = 0
    for u in User.objects.filter(role="secretary"):
        _, was_created = Secretaire.objects.get_or_create(
            user=u, defaults={"telephone": ""}
        )
        if was_created:
            created += 1
    return created
