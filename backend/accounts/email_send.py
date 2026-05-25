"""Envoi d'e-mails transactionnels (Gmail SMTP ou Resend)."""

from __future__ import annotations

import json
import smtplib
import urllib.error
import urllib.request

from django.conf import settings

from accounts.email_smtp_errors import format_smtp_error
from django.core.mail import EmailMessage, get_connection

from accounts.email_config import (
    mail_is_ready,
    resend_api_key,
    smtp_connection_params,
    smtp_is_ready,
)


class EmailDeliveryError(Exception):
    """Échec d'envoi (configuration ou serveur distant)."""


def _from_email() -> str:
    return getattr(
        settings, "DEFAULT_FROM_EMAIL", "CardioSoin <noreply@cardiosoin.local>"
    )


def _send_via_resend(*, subject: str, body: str, to: list[str]) -> None:
    api_key = resend_api_key()
    if not api_key:
        raise EmailDeliveryError("Clé Resend absente.")

    from_addr = getattr(settings, "RESEND_FROM_EMAIL", "onboarding@resend.dev")
    payload = json.dumps(
        {
            "from": from_addr,
            "to": to,
            "subject": subject,
            "text": body,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status >= 400:
                raise EmailDeliveryError(f"Resend HTTP {resp.status}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise EmailDeliveryError(f"Resend : {detail}") from exc
    except urllib.error.URLError as exc:
        raise EmailDeliveryError(f"Réseau Resend : {exc}") from exc


def _send_via_smtp(*, subject: str, body: str, to: list[str]) -> None:
    params = smtp_connection_params()
    connection = get_connection(
        backend="django.core.mail.backends.smtp.EmailBackend",
        host=params["host"],
        port=params["port"],
        username=params["username"],
        password=params["password"],
        use_tls=params["use_tls"],
        use_ssl=params["use_ssl"],
        timeout=params["timeout"],
        fail_silently=False,
    )
    msg = EmailMessage(
        subject=subject,
        body=body,
        from_email=_from_email(),
        to=to,
        connection=connection,
    )
    msg.encoding = "utf-8"
    try:
        msg.send(fail_silently=False)
    except smtplib.SMTPException as exc:
        raise EmailDeliveryError(format_smtp_error(exc)) from exc


def send_transactional_email(
    *,
    subject: str,
    body: str,
    to: list[str],
) -> None:
    if not mail_is_ready():
        raise EmailDeliveryError(
            "Aucun service d'envoi configuré (Gmail ou Resend)."
        )

    if resend_api_key():
        _send_via_resend(subject=subject, body=body, to=to)
        return

    if smtp_is_ready():
        _send_via_smtp(subject=subject, body=body, to=to)
        return

    raise EmailDeliveryError("Configuration e-mail incomplète.")


def smtp_configured() -> bool:
    return mail_is_ready()
