"""Configuration Gmail (mode développement uniquement)."""

from __future__ import annotations

import smtplib

from django.conf import settings
from django.contrib import messages
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from accounts.email_config import (
    clear_gmail_credentials,
    mail_is_ready,
    persist_gmail_credentials,
    validate_google_app_password,
)
from accounts.email_send import EmailDeliveryError, send_transactional_email
from accounts.email_smtp_errors import format_smtp_error
from accounts.email_validation import validate_recipient_email


def _debug_only(request: HttpRequest) -> HttpResponseForbidden | None:
    if not settings.DEBUG:
        return HttpResponseForbidden("Disponible uniquement en mode développement.")
    return None


def _send_test_email(recipient: str, password: str) -> None:
    """Test SMTP avec le mot de passe fourni (sans l'enregistrer d'abord)."""
    from django.core.mail import EmailMessage, get_connection

    from accounts.email_config import smtp_connection_params

    params = smtp_connection_params()
    connection = get_connection(
        backend="django.core.mail.backends.smtp.EmailBackend",
        host=params["host"],
        port=params["port"],
        username=params["username"],
        password=password,
        use_tls=params["use_tls"],
        use_ssl=params["use_ssl"],
        timeout=params["timeout"],
        fail_silently=False,
    )
    msg = EmailMessage(
        subject="CardioSoin - Test Gmail",
        body=(
            "Bonjour,\n\n"
            "La configuration e-mail CardioSoin fonctionne.\n"
            "Retournez sur votre profil et cliquez sur « Envoyer le code ».\n\n"
            "— CardioSoin"
        ),
        from_email=getattr(
            settings, "DEFAULT_FROM_EMAIL", f"CardioSoin <{params['username']}>"
        ),
        to=[recipient],
        connection=connection,
    )
    msg.encoding = "utf-8"
    msg.send(fail_silently=False)


@never_cache
@require_http_methods(["GET", "POST"])
def email_smtp_setup(request: HttpRequest) -> HttpResponse:
    """Page locale pour enregistrer le mot de passe d'application Gmail."""
    denied = _debug_only(request)
    if denied:
        return denied

    recipient = (settings.EMAIL_HOST_USER or "").strip()
    ok_recipient, err_recipient, recipient_norm = validate_recipient_email(recipient)

    if request.method == "POST":
        raw_password = request.POST.get("app_password") or ""
        ok_pwd, err_pwd, password = validate_google_app_password(raw_password)
        if not ok_pwd:
            messages.error(request, err_pwd)
            return redirect("email_smtp_setup")

        if not ok_recipient:
            messages.error(request, err_recipient or "E-mail Gmail invalide dans .env.")
            return redirect("email_smtp_setup")

        try:
            _send_test_email(recipient_norm, password)
        except (EmailDeliveryError, smtplib.SMTPException, OSError) as exc:
            clear_gmail_credentials()
            messages.error(request, format_smtp_error(exc))
            return redirect("email_smtp_setup")

        persist_gmail_credentials(password)
        messages.success(
            request,
            f"Configuration réussie. Un e-mail de test a été envoyé à {recipient_norm}.",
        )
        return redirect("email_smtp_setup")

    return render(
        request,
        "accounts/email_smtp_setup.html",
        {
            "smtp_ready": mail_is_ready(),
            "gmail_user": recipient,
            "gmail_user_valid": ok_recipient,
            "gmail_user_error": err_recipient,
        },
    )
