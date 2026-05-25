"""Test d'envoi SMTP : py manage.py test_email_send votre@email.com"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from accounts.email_config import mail_is_ready
from accounts.email_validation import validate_recipient_email
from accounts.email_send import send_transactional_email


class Command(BaseCommand):
    help = "Envoie un e-mail de test pour vérifier la configuration SMTP (.env)."

    def add_arguments(self, parser):
        parser.add_argument(
            "recipient",
            nargs="?",
            default="",
            help="Adresse destinataire (défaut : EMAIL_HOST_USER)",
        )

    def handle(self, *args, **options):
        raw = (options["recipient"] or settings.EMAIL_HOST_USER or "").strip()
        ok, err, recipient = validate_recipient_email(raw)
        if not ok:
            raise CommandError(err or "Destinataire invalide.")

        self.stdout.write(f"Backend : {settings.EMAIL_BACKEND}")
        self.stdout.write(f"Host    : {settings.EMAIL_HOST}:{settings.EMAIL_PORT}")
        self.stdout.write(f"From    : {settings.DEFAULT_FROM_EMAIL}")
        self.stdout.write(f"To      : {recipient}")
        if not mail_is_ready():
            raise CommandError(
                "Gmail non configuré.\n"
                "Ouvrez http://127.0.0.1:8000/configurer-email/ "
                "ou lancez : py manage.py configure_email"
            )

        send_transactional_email(
            subject="CardioSoin - Test envoi e-mail",
            body=(
                "Bonjour,\n\n"
                "Si vous lisez ce message, l'envoi SMTP CardioSoin fonctionne.\n\n"
                "— CardioSoin"
            ),
            to=[recipient],
        )
        self.stdout.write(self.style.SUCCESS("E-mail envoye avec succes."))
