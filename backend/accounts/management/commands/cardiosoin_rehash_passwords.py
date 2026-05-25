"""
Recalcule les mots de passe stockés en clair (legacy) : utile une fois
après correction de l’admin / du modèle User.

  python manage.py cardiosoin_rehash_passwords
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from accounts.models import password_looks_django_hashed


class Command(BaseCommand):
    help = "Hache les mots de passe en clair déjà en base (sécurité rétroactive)."

    def handle(self, *args, **options) -> None:
        User = get_user_model()
        n = 0
        for u in User.objects.iterator():
            if u.password and not password_looks_django_hashed(u.password):
                raw = u.password
                u.set_password(raw)
                u.save(update_fields=["password"])
                n += 1
        self.stdout.write(
            self.style.SUCCESS(
                f"Comptes corrigés : {n} (mots de passe hachés)."
            )
        )
