"""Lecture et enregistrement des identifiants d'envoi e-mail."""

from __future__ import annotations

import os
import re
from pathlib import Path

from django.conf import settings

_SECRET_FILE = Path(settings.BASE_DIR) / "email_secret.txt"
_ENV_FILE = Path(settings.BASE_DIR) / ".env"
_PLACEHOLDER_PASSWORDS = frozenset(
    {
        "",
        "votre_mot_de_passe_application_16_caracteres",
        "changeme",
    }
)


def secret_file_path() -> Path:
    return _SECRET_FILE


_APP_PASSWORD_RE = re.compile(r"^[a-z]{16}$")


def _clean_password(raw: str) -> str:
    value = (raw or "").strip().replace(" ", "").lower()
    if value in _PLACEHOLDER_PASSWORDS:
        return ""
    return value


def validate_google_app_password(raw: str) -> tuple[bool, str, str]:
    """
    Un mot de passe d'application Google = exactement 16 lettres (ex. abcd efgh ijkl mnop).
    Ce n'est PAS le mot de passe de connexion Gmail.
    """
    cleaned = _clean_password(raw)
    if not cleaned:
        return False, "Mot de passe d'application requis.", ""
    if "@" in raw or len(cleaned) != 16:
        return (
            False,
            "Format incorrect : il faut 16 lettres (mot de passe d'application Google), "
            "pas votre mot de passe Gmail.",
            "",
        )
    if not _APP_PASSWORD_RE.match(cleaned):
        return (
            False,
            "Le mot de passe d'application ne contient que des lettres (16 caractères).",
            "",
        )
    return True, "", cleaned


def clear_gmail_credentials() -> None:
    if _SECRET_FILE.is_file():
        _SECRET_FILE.unlink()
    update_env_app_password("")
    os.environ.pop("EMAIL_HOST_PASSWORD", None)


def read_app_password_from_file() -> str:
    if not _SECRET_FILE.is_file():
        return ""
    return _clean_password(_SECRET_FILE.read_text(encoding="utf-8"))


def write_app_password_to_file(password: str) -> None:
    cleaned = _clean_password(password)
    _SECRET_FILE.write_text(cleaned, encoding="utf-8")


def update_env_app_password(password: str) -> None:
    """Met à jour EMAIL_HOST_PASSWORD dans backend/.env."""
    cleaned = _clean_password(password)
    if not _ENV_FILE.is_file():
        return
    lines = _ENV_FILE.read_text(encoding="utf-8").splitlines()
    found = False
    new_lines: list[str] = []
    for line in lines:
        if line.startswith("EMAIL_HOST_PASSWORD="):
            new_lines.append(f"EMAIL_HOST_PASSWORD={cleaned}")
            found = True
        else:
            new_lines.append(line)
    if not found:
        new_lines.append(f"EMAIL_HOST_PASSWORD={cleaned}")
    _ENV_FILE.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    os.environ["EMAIL_HOST_PASSWORD"] = cleaned


def effective_smtp_password() -> str:
    for key in ("EMAIL_HOST_PASSWORD", "GMAIL_APP_PASSWORD", "EMAIL_APP_PASSWORD"):
        pwd = _clean_password(os.environ.get(key, ""))
        if pwd:
            return pwd
    pwd = _clean_password(getattr(settings, "EMAIL_HOST_PASSWORD", "") or "")
    if pwd:
        return pwd
    return read_app_password_from_file()


def resend_api_key() -> str:
    return (os.environ.get("RESEND_API_KEY") or getattr(settings, "RESEND_API_KEY", "") or "").strip()


def smtp_is_ready() -> bool:
    user = (getattr(settings, "EMAIL_HOST_USER", "") or "").strip()
    if not user or user.lower() in {"", "votre.adresse@gmail.com"}:
        return False
    pwd = effective_smtp_password()
    if not pwd:
        return False
    ok, _, _ = validate_google_app_password(pwd)
    return ok


def mail_is_ready() -> bool:
    return smtp_is_ready() or bool(resend_api_key())


def smtp_connection_params() -> dict:
    return {
        "host": getattr(settings, "EMAIL_HOST", "smtp.gmail.com"),
        "port": int(getattr(settings, "EMAIL_PORT", 587)),
        "username": getattr(settings, "EMAIL_HOST_USER", ""),
        "password": effective_smtp_password(),
        "use_tls": getattr(settings, "EMAIL_USE_TLS", True),
        "use_ssl": getattr(settings, "EMAIL_USE_SSL", False),
        "timeout": getattr(settings, "EMAIL_TIMEOUT", 30),
    }


def persist_gmail_credentials(password: str) -> None:
    cleaned = _clean_password(password)
    write_app_password_to_file(cleaned)
    update_env_app_password(cleaned)
