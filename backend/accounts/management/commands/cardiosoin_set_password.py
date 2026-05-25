"""
Définit le mot de passe d’un compte (hash Django) — utile si la BDD
contient un mot de passe en clair ou un hash non Django.

  python manage.py cardiosoin_set_password admin@cabinet.com MonNouveauMotDePasse
  python manage.py cardiosoin_set_password mon_identifiant MonNouveauMotDePasse
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

User = get_user_model()


class Command(BaseCommand):
    help = "Définit le mot de passe d’un utilisateur (par username exact ou e-mail)."

    def add_arguments(self, parser) -> None:
        parser.add_argument("ident", help="Username ou e-mail (identique à la fiche en base).")
        parser.add_argument("password", help="Nouveau mot de passe (sera haché par Django).")

    def handle(self, *args, **options) -> None:
        ident = (options["ident"] or "").strip()
        password = options["password"] or ""
        if not ident or not password:
            raise CommandError("ident et password requis.")

        q = Q(username__iexact=ident) | Q(email__iexact=ident)
        users = list(User.objects.filter(q))
        if not users:
            raise CommandError(f"Aucun utilisateur pour « {ident} » (username ni e-mail).")
        if len(users) > 1:
            raise CommandError("Plusieurs comptes correspondent — unifiez l’e-mail en base.")
        u = users[0]
        u.set_password(password)
        u.save()
        self.stdout.write(
            self.style.SUCCESS(
                f"Mot de passe mis à jour pour {u.username} (rôle: {getattr(u, 'role', '?')})."
            )
        )
