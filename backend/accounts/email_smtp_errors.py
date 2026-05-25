"""Messages d'erreur SMTP compréhensibles (Gmail)."""

from __future__ import annotations

import smtplib


def format_smtp_error(exc: BaseException) -> str:
  if isinstance(exc, smtplib.SMTPAuthenticationError):
    return (
      "Gmail a refusé la connexion. Utilisez un mot de passe d'application "
      "(16 lettres, sans @ ni mot de passe Gmail habituel). "
      "Création : https://myaccount.google.com/apppasswords "
      "(validation en 2 étapes obligatoire)."
    )
  if isinstance(exc, smtplib.SMTPException):
    return f"Erreur serveur e-mail : {exc}"
  return str(exc)
