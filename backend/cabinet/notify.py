from __future__ import annotations

from cabinet.models import Notification
from patients.models import Patient


def notify_patient(
    patient: Patient, message: str, notif_type: str = "rdv"
) -> None:
    if not patient:
        return
    Notification.objects.create(
        destinataire_patient=patient,
        message=message,
        type=notif_type,
    )


def notify_all_patients(message: str, notif_type: str = "cabinet") -> None:
    for p in Patient.objects.all().iterator():
        notify_patient(p, message, notif_type)


def notify_all_secretaries(message: str, notif_type: str = "rdv") -> None:
    from accounts.models import Secretaire

    for s in Secretaire.objects.select_related("user").iterator():
        if not s.user.is_active:
            continue
        Notification.objects.create(
            destinataire_secretaire=s, message=message, type=notif_type
        )


def secretaries_for_alerts():
    from accounts.models import Secretaire

    return Secretaire.objects.filter(user__is_active=True).select_related("user")
