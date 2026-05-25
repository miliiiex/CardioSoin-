"""Données d'inscription en attente de vérification e-mail (session)."""

from __future__ import annotations

from django.http import HttpRequest

SESSION_REG_PENDING = "reg_pending_data"


def get_pending_registration(request: HttpRequest) -> dict | None:
    data = request.session.get(SESSION_REG_PENDING)
    return data if isinstance(data, dict) else None


def save_pending_registration(request: HttpRequest, data: dict) -> None:
    request.session[SESSION_REG_PENDING] = data
    request.session.modified = True


def clear_pending_registration(request: HttpRequest) -> None:
    request.session.pop(SESSION_REG_PENDING, None)
    request.session.modified = True
