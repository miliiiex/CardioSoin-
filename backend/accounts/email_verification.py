"""
Envoi et validation de codes de vérification par e-mail.
"""

from __future__ import annotations

import random
import re
from datetime import timedelta
from typing import TYPE_CHECKING

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from accounts.email_send import EmailDeliveryError, send_transactional_email
from accounts.email_validation import normalize_email, validate_recipient_email
from django.utils import timezone

from accounts.models import EmailVerificationCode, User

if TYPE_CHECKING:
    from django.http import HttpRequest

PURPOSE_REGISTER = "register"
PURPOSE_RESET_PASSWORD = "reset_password"
PURPOSE_CHANGE_PASSWORD = "change_password"

PURPOSE_LABELS = {
    PURPOSE_REGISTER: "confirmation d'inscription",
    PURPOSE_RESET_PASSWORD: "réinitialisation du mot de passe",
    PURPOSE_CHANGE_PASSWORD: "modification du mot de passe",
}

_CODE_RE = re.compile(r"^\d{6}$")
_MAX_SENDS_PER_HOUR = 5
_MAX_ATTEMPTS = 8


def _normalize_email(email: str) -> str:
    return normalize_email(email)


def _code_expiry() -> timezone.datetime:
    minutes = int(getattr(settings, "EMAIL_VERIFICATION_CODE_MINUTES", 15))
    return timezone.now() + timedelta(minutes=minutes)


def _session_key(purpose: str, email: str) -> str:
    return f"email_verified:{purpose}:{_normalize_email(email)}"


def _password_change_session_key(user_id: int) -> str:
    return f"pwd_change_verified:{user_id}"


def generate_numeric_code(length: int = 6) -> str:
    return "".join(str(random.randint(0, 9)) for _ in range(length))


def mark_email_verified_in_session(
    request: HttpRequest, purpose: str, email: str
) -> None:
    request.session[_session_key(purpose, email)] = timezone.now().isoformat()
    request.session.modified = True


def mark_password_change_verified(request: HttpRequest, user: User) -> None:
    request.session[_password_change_session_key(user.pk)] = (
        timezone.now().isoformat()
    )
    request.session.modified = True


def is_email_verified_in_session(
    request: HttpRequest, purpose: str, email: str
) -> bool:
    raw = request.session.get(_session_key(purpose, email))
    if not raw:
        return False
    try:
        verified_at = timezone.datetime.fromisoformat(raw)
        if timezone.is_naive(verified_at):
            verified_at = timezone.make_aware(verified_at)
    except (TypeError, ValueError):
        return False
    max_age = int(getattr(settings, "EMAIL_VERIFICATION_SESSION_MINUTES", 45))
    return timezone.now() - verified_at <= timedelta(minutes=max_age)


def is_password_change_verified_in_session(
    request: HttpRequest, user: User
) -> bool:
    raw = request.session.get(_password_change_session_key(user.pk))
    if not raw:
        return False
    try:
        verified_at = timezone.datetime.fromisoformat(raw)
        if timezone.is_naive(verified_at):
            verified_at = timezone.make_aware(verified_at)
    except (TypeError, ValueError):
        return False
    max_age = int(getattr(settings, "EMAIL_VERIFICATION_SESSION_MINUTES", 45))
    return timezone.now() - verified_at <= timedelta(minutes=max_age)


def clear_email_verification_session(
    request: HttpRequest, purpose: str, email: str
) -> None:
    request.session.pop(_session_key(purpose, email), None)
    request.session.modified = True


def _can_send_more(email: str, purpose: str) -> bool:
    since = timezone.now() - timedelta(hours=1)
    return (
        EmailVerificationCode.objects.filter(
            email=_normalize_email(email),
            purpose=purpose,
            created_at__gte=since,
        ).count()
        < _MAX_SENDS_PER_HOUR
    )


def send_verification_code(
    *,
    email: str,
    purpose: str,
    user: User | None = None,
) -> tuple[bool, str]:
    """
    Crée un code, l'envoie par e-mail.
    Retourne (succès, message utilisateur).
    """
    ok_email, err_email, email_n = validate_recipient_email(email)
    if not ok_email:
        return False, err_email

    if purpose not in PURPOSE_LABELS:
        return False, "Action non reconnue."

    if not _can_send_more(email_n, purpose):
        return False, "Trop de demandes. Réessayez dans une heure."

    if purpose == PURPOSE_REGISTER:
        if User.objects.filter(email__iexact=email_n).exists():
            return False, "Cet e-mail est déjà associé à un compte."

    if purpose == PURPOSE_RESET_PASSWORD:
        if not User.objects.filter(email__iexact=email_n).exists():
            return True, (
                "Si un compte est associé à cet e-mail, un code de vérification "
                "vient d'y être envoyé."
            )

    from accounts.email_config import mail_is_ready

    if not mail_is_ready():
        if settings.DEBUG:
            return False, (
                "Envoi e-mail impossible : configurez Gmail sur "
                "http://127.0.0.1:8000/configurer-email/ "
                "(mot de passe d'application Google, 16 caractères)."
            )
        return False, (
            "Envoi e-mail temporairement indisponible. "
            "Contactez l'administrateur du site."
        )

    code = generate_numeric_code()
    EmailVerificationCode.objects.filter(
        email=email_n, purpose=purpose, used_at__isnull=True
    ).update(used_at=timezone.now())

    record = EmailVerificationCode.objects.create(
        email=email_n,
        purpose=purpose,
        code_hash=make_password(code),
        user=user,
        expires_at=_code_expiry(),
    )

    label = PURPOSE_LABELS[purpose]
    minutes = getattr(settings, "EMAIL_VERIFICATION_CODE_MINUTES", 15)
    subject = f"CardioSoin - Code de verification ({label})"
    body = (
        f"Bonjour,\n\n"
        f"Votre code de verification CardioSoin est : {code}\n\n"
        f"Il est valable {minutes} minutes.\n"
        f"Ne partagez ce code avec personne.\n\n"
        f"— L'equipe CardioSoin"
    )
    try:
        send_transactional_email(subject=subject, body=body, to=[email_n])
    except (EmailDeliveryError, Exception) as exc:
        record.delete()
        if settings.DEBUG:
            import logging

            logging.getLogger(__name__).exception("Echec envoi e-mail: %s", exc)
        hint = (
            " Vérifiez le mot de passe d'application sur /configurer-email/."
            if settings.DEBUG
            else ""
        )
        return False, f"Impossible d'envoyer l'e-mail : {exc}.{hint}"

    return True, (
        f"Un code à 6 chiffres a été envoyé à {email_n}. "
        f"Vérifiez aussi vos courriers indésirables."
    )


def verify_submitted_code(
    *,
    email: str,
    code: str,
    purpose: str,
) -> tuple[bool, str]:
    email_n = _normalize_email(email)
    code_s = (code or "").strip()
    if not _CODE_RE.match(code_s):
        return False, "Le code doit contenir 6 chiffres."

    row = (
        EmailVerificationCode.objects.filter(
            email=email_n,
            purpose=purpose,
            used_at__isnull=True,
            expires_at__gte=timezone.now(),
        )
        .order_by("-created_at")
        .first()
    )
    if not row:
        return False, "Code expiré ou introuvable. Demandez un nouveau code."

    row.attempts += 1
    row.save(update_fields=["attempts"])
    if row.attempts > _MAX_ATTEMPTS:
        row.used_at = timezone.now()
        row.save(update_fields=["used_at"])
        return False, "Trop de tentatives. Demandez un nouveau code."

    if not check_password(code_s, row.code_hash):
        return False, "Code incorrect."

    row.used_at = timezone.now()
    row.save(update_fields=["used_at"])
    return True, "Adresse e-mail vérifiée."
