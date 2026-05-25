"""Configuration interactive Gmail : py manage.py configure_email"""

from getpass import getpass

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from accounts.email_config import (
    mail_is_ready,
    persist_gmail_credentials,
    validate_google_app_password,
)
from accounts.email_send import EmailDeliveryError
from accounts.email_validation import validate_recipient_email
from accounts.email_send import send_transactional_email


class Command(BaseCommand):
    help = "Enregistre le mot de passe d'application Gmail et envoie un e-mail de test."

    def handle(self, *args, **options):
        user = (settings.EMAIL_HOST_USER or "").strip()
        ok, err, user_norm = validate_recipient_email(user)
        if not ok:
            raise CommandError(err or "EMAIL_HOST_USER invalide dans backend/.env.")

        self.stdout.write(
            "Créez un mot de passe d'application : https://myaccount.google.com/apppasswords"
        )
        raw = getpass("Collez le mot de passe d'application (16 lettres) : ")
        ok_pwd, err_pwd, password = validate_google_app_password(raw)
        if not ok_pwd:
            raise CommandError(err_pwd)

        persist_gmail_credentials(password)
        if not mail_is_ready():
            raise CommandError("Configuration incomplète après enregistrement.")

        try:
            send_transactional_email(
                subject="CardioSoin - Test Gmail",
                body="Configuration e-mail réussie.\n\n— CardioSoin",
                to=[user_norm],
            )
        except EmailDeliveryError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(f"E-mail de test envoyé à {user_norm}."))
