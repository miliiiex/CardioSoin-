from __future__ import annotations

from datetime import date, datetime, time, timedelta

from django.utils import timezone

from accounts.models import Medecin
from appointments.models import RendezVous

STEP_MINUTES = 30
OPEN_HOURS = (9, 12, 14, 18)  # 9-12, 14-18


def _iter_day_slots(d: date):
    tz = timezone.get_current_timezone()
    for h_start, h_end in ((9, 12), (14, 18)):
        t = h_start * 60
        end = h_end * 60
        while t < end:
            hh, mm = divmod(t, 60)
            naive = datetime.combine(d, time(hh, mm))
            yield timezone.make_aware(naive, tz)
            t += STEP_MINUTES


def suggest_available_slots(
    med: Medecin, from_date: date, days: int = 7, max_suggestions: int = 8
) -> list[datetime]:
    """Créneaux proposés (non réservés) sur plusieurs jours ouvrables."""
    out: list[datetime] = []
    cur = from_date
    for _ in range(days):
        if cur.weekday() < 5:  # lun–ven
            for na in _iter_day_slots(cur):
                if na < timezone.now():
                    continue
                if not _slot_taken(med, na):
                    out.append(na)
                    if len(out) >= max_suggestions:
                        return out
        cur += timedelta(days=1)
    return out


def _slot_taken(med: Medecin, when: datetime) -> bool:
    if timezone.is_naive(when):
        when = timezone.make_aware(when, timezone.get_current_timezone())
    return RendezVous.objects.filter(
        medecin=med,
        date_heure=when,
        statut__in=["en_attente", "confirmé"],
    ).exists()
