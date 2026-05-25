from __future__ import annotations

from datetime import date

from django.utils import formats

from accounts.models import Medecin
from appointments.models import RendezVous
from cabinet.models import Absence
from cabinet.notify import notify_all_secretaries, notify_patient


def _format_date(d: date) -> str:
    return formats.date_format(d, "DATE_FORMAT", use_l10n=True)


def cancel_rdvs_on_absence_day(med: Medecin, d: date, dr_label: str) -> None:
    for rdv in (
        RendezVous.objects.filter(medecin=med, date_heure__date=d)
        .exclude(statut__in=["annulé", "terminé"])
        .select_related("patient", "medecin__user")
    ):
        rdv.statut = "annulé"
        rdv.save()
        msg = (
            f"Le {dr_label} sera absent le {_format_date(d)}. "
            "Votre rendez-vous a été annulé. Vous serez recontacté."
        )
        notify_patient(rdv.patient, msg, "absence")


def on_absence_created(absence: Absence) -> None:
    med = absence.medecin
    u = med.user
    name = u.get_full_name() or u.username
    dr_label = f"Dr {name}"
    cancel_rdvs_on_absence_day(med, absence.date_absence, dr_label)


def notify_secretaries_absence(absence: Absence) -> None:
    """Annonce d’absence visible dans le tableau de bord secrétaire (type « absence »)."""
    med = absence.medecin
    dr = med.user.get_full_name() or med.user.username
    d = _format_date(absence.date_absence)
    motif = (absence.motif or "").strip() or "—"
    if absence.signalee_par == "medecin":
        intro = f"Le Dr {dr} a signalé son absence le {d}."
    else:
        intro = f"Absence du Dr {dr} le {d} (enregistrée par le secrétariat)."
    notify_all_secretaries(f"{intro} Motif : {motif}", "absence")


def notify_after_doctor_self_absence(med: Medecin, absence: Absence) -> None:
    """Compatibilité : délègue à notify_secretaries_absence."""
    notify_secretaries_absence(absence)


def absences_for_history(*, medecin: Medecin | None = None, limit: int = 30) -> list[Absence]:
    qs = Absence.objects.select_related("medecin__user").order_by(
        "-date_creation", "-date_absence"
    )
    if medecin is not None:
        qs = qs.filter(medecin=medecin)
    return list(qs[:limit])
