"""Vérifie la config e-mail et envoie un code test : py manage.py check_email_delivery"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from accounts.email_config import mail_is_ready
from accounts.email_validation import validate_recipient_email
from accounts.email_verification import PURPOSE_CHANGE_PASSWORD, send_verification_code


class Command(BaseCommand):
    help = "Valide l'e-mail, vérifie Gmail/Resend, envoie un code de test."

    def add_arguments(self, parser):
        parser.add_argument(
            "email",
            nargs="?",
            default="",
            help="Destinataire (défaut : EMAIL_HOST_USER)",
        )

    def handle(self, *args, **options):
        raw = (options["email"] or settings.EMAIL_HOST_USER or "").strip()
        ok, err, email = validate_recipient_email(raw)
        if not ok:
            raise CommandError(f"E-mail invalide : {err}")

        self.stdout.write(f"E-mail valide : {email}")
        if not mail_is_ready():
            raise CommandError(
                "Envoi impossible. Ouvrez http://127.0.0.1:8000/configurer-email/ "
                "et enregistrez le mot de passe d'application Google."
            )

        self.stdout.write("Service d'envoi : OK")
        sent, msg = send_verification_code(
            email=email,
            purpose=PURPOSE_CHANGE_PASSWORD,
        )
        if not sent:
            raise CommandError(msg)
        self.stdout.write(self.style.SUCCESS(msg))
