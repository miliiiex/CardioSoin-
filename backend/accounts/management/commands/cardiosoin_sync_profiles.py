"""
Crée les profils Medecin / Secretaire manquants pour les comptes existants
(utile après ajout manuel en base ou avant ce correctif).

  python manage.py cardiosoin_sync_profiles
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from accounts.medecin_utils import ensure_medecin_for_doctor_users
from accounts.secretary_utils import ensure_secretaire_backfill


class Command(BaseCommand):
    help = "Crée les fiches Médecin et Secrétaire manquantes pour les User concernés."

    def handle(self, *args, **options) -> None:
        n_m = ensure_medecin_for_doctor_users()
        n_s = ensure_secretaire_backfill()
        self.stdout.write(
            self.style.SUCCESS(
                f"Profils créés : {n_m} médecin(s), {n_s} secrétaire(s)."
            )
        )
