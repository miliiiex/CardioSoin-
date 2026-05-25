"""Validation des adresses e-mail avant envoi."""

from __future__ import annotations

import re

from django.core.exceptions import ValidationError
from django.core.validators import validate_email

_DISPOSABLE_DOMAINS = frozenset(
    {
        "mailinator.com",
        "tempmail.com",
        "guerrillamail.com",
        "yopmail.com",
        "10minutemail.com",
    }
)


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def validate_recipient_email(email: str) -> tuple[bool, str, str]:
    """
    Vérifie qu'une adresse est utilisable pour l'envoi.
    Retourne (ok, message_erreur, email_normalisé).
    """
    email_n = normalize_email(email)
    if not email_n:
        return False, "Adresse e-mail obligatoire.", ""
    if len(email_n) > 254:
        return False, "Adresse e-mail trop longue.", ""
    try:
        validate_email(email_n)
    except ValidationError:
        return False, "Adresse e-mail invalide (vérifiez le format).", ""

    local, _, domain = email_n.partition("@")
    if not local or not domain or "." not in domain:
        return False, "Adresse e-mail invalide.", ""
    if domain in _DISPOSABLE_DOMAINS:
        return False, "Les adresses e-mail temporaires ne sont pas acceptées.", ""
    if not re.match(r"^[a-z0-9._%+\-]+$", local):
        return False, "Caractères non autorisés dans l'adresse e-mail.", ""

    return True, "", email_n
