from __future__ import annotations

import datetime
from datetime import time

from accounts.medecin_utils import medecins_for_appointments
from accounts.models import Medecin, Secretaire
from accounts.permissions import is_secretary
from appointments.models import RendezVous
from cabinet.absence_service import absences_for_history, notify_secretaries_absence, on_absence_created
from cabinet.models import Absence, StatutCabinet, Notification
from cabinet.notify import notify_all_patients, notify_patient
from cabinet.slots import suggest_available_slots
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import transaction
from django.db.models import Case, IntegerField, Value, When
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie

from patients.models import DossierMedical, Patient
from prescriptions.models import Ordonnance


MSG_CONFLIT = "Ce créneau est déjà pris. Choisissez un autre horaire."


def _secretary_resolve_patient_from_name(raw: str) -> tuple[Patient | None, str]:
    """
    Associe la saisie libre du secrétariat à une fiche Patient (nom affiché ou identifiant).
    """
    raw = (raw or "").strip()
    if not raw:
        return None, "Indiquez le nom du patient."
    raw_l = raw.lower()
    patients = list(Patient.objects.select_related("user"))
    exact: list[Patient] = []
    loose: list[Patient] = []
    for p in patients:
        u = p.user
        full = (u.get_full_name() or "").strip()
        full_l = full.lower() if full else ""
        uname_l = (u.username or "").strip().lower()
        display = full_l or uname_l
        if display == raw_l or uname_l == raw_l:
            exact.append(p)
        elif raw_l in display:
            loose.append(p)
    if len(exact) == 1:
        return exact[0], ""
    if len(exact) > 1:
        return (
            None,
            "Plusieurs fiches portent exactement ce nom. Précisez ou utilisez le nom d’utilisateur du compte patient.",
        )
    if len(loose) == 1:
        return loose[0], ""
    if len(loose) == 0:
        return (
            None,
            f"Aucun patient « {raw} ». Vérifiez l’orthographe ou enregistrez le patient d’abord.",
        )
    return (
        None,
        "Plusieurs patients correspondent. Saisissez le nom complet tel qu’enregistré sur la fiche.",
    )


def _local_day_bounds(day: datetime.date, tz) -> tuple[datetime.datetime, datetime.datetime]:
    start = timezone.make_aware(datetime.datetime.combine(day, time.min), tz)
    return start, start + datetime.timedelta(days=1)


def _patient_ids_rdv_day(day: datetime.date, tz) -> list[int]:
    d0, d1 = _local_day_bounds(day, tz)
    return list(
        RendezVous.objects.filter(
            date_heure__gte=d0,
            date_heure__lt=d1,
            patient__isnull=False,
        )
        .exclude(statut="annulé")
        .values_list("patient_id", flat=True)
        .distinct()
    )


def _notify_absence_options(jour: datetime.date, tz) -> list[dict]:
    out: list[dict] = []
    for a in (
        Absence.objects.filter(date_absence__gte=jour)
        .select_related("medecin__user")
        .order_by("date_absence", "pk")[:40]
    ):
        a0, a1 = _local_day_bounds(a.date_absence, tz)
        pids = list(
            RendezVous.objects.filter(
                medecin=a.medecin,
                date_heure__gte=a0,
                date_heure__lt=a1,
                patient__isnull=False,
            )
            .exclude(statut="annulé")
            .values_list("patient_id", flat=True)
            .distinct()
        )
        if not pids:
            continue
        dr = a.medecin.user.get_full_name() or a.medecin.user.username
        out.append(
            {
                "id": a.pk,
                "label": (
                    f"{a.date_absence:%d/%m/%Y} — Dr {dr} — "
                    f"{len(pids)} patient(s) avec RDV actif"
                ),
                "count": len(pids),
            }
        )
    return out


@login_required(login_url="staff_login")
@user_passes_test(is_secretary)
def secretary_desk(request: HttpRequest) -> HttpResponse:
    s = get_object_or_404(Secretaire, user=request.user)
    cab = StatutCabinet.get_solo()
    tz = timezone.get_current_timezone()
    n_unread = Notification.objects.filter(
        destinataire_secretaire=s, lu=False
    ).count()
    notifications_recent = list(
        Notification.objects.filter(destinataire_secretaire=s)
        .annotate(
            _prio=Case(
                When(type="absence", then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            )
        )
        .order_by("_prio", "-date_creation")[:25]
    )

    jour = timezone.localdate()
    start = timezone.make_aware(datetime.datetime.combine(jour, time.min), tz)
    end = start + datetime.timedelta(days=1)
    rdvs_aujourdhui = list(
        RendezVous.objects.filter(date_heure__gte=start, date_heure__lt=end)
        .exclude(statut="annulé")
        .select_related("patient__user", "medecin__user")
        .order_by("date_heure")
    )
    stat_rdv_aujourdhui = len(rdvs_aujourdhui)

    planning_start_d = jour - datetime.timedelta(days=90)
    planning_end_d = jour + datetime.timedelta(days=180)
    planning_start = timezone.make_aware(
        datetime.datetime.combine(planning_start_d, time.min), tz
    )
    planning_end = timezone.make_aware(
        datetime.datetime.combine(planning_end_d, time.max), tz
    )
    rdvs_planning_qs = RendezVous.objects.filter(
        date_heure__gte=planning_start, date_heure__lte=planning_end
    ).exclude(statut="annulé")
    rdv_date_marks = sorted(
        {
            timezone.localtime(r.date_heure, tz).date().isoformat()
            for r in rdvs_planning_qs.only("date_heure")
        }
    )
    rdvs_planning = list(
        rdvs_planning_qs.exclude(date_heure__gte=start, date_heure__lt=end)
        .select_related("patient__user", "medecin__user")
        .order_by("date_heure")
    )

    patients_recent = list(
        Patient.objects.select_related("user")
        .order_by("-user__date_joined", "-pk")[:12]
    )

    demain = jour + datetime.timedelta(days=1)
    notify_count_aujourdhui = len(_patient_ids_rdv_day(jour, tz))
    notify_count_demain = len(_patient_ids_rdv_day(demain, tz))
    notify_absence_options = _notify_absence_options(jour, tz)

    return render(
        request,
        "accounts/secretary_desk.html",
        {
            "user": request.user,
            "secretaire": s,
            "cabinet_statut": cab.statut,
            "notifications_recent": notifications_recent,
            "unread_count": n_unread,
            "stat_patients": Patient.objects.count(),
            "stat_rdv_aujourdhui": stat_rdv_aujourdhui,
            "jour": jour,
            "rdvs_aujourdhui": rdvs_aujourdhui,
            "rdvs_planning": rdvs_planning,
            "rdv_date_marks": rdv_date_marks,
            "patients_recent": patients_recent,
            "notify_count_aujourdhui": notify_count_aujourdhui,
            "notify_count_demain": notify_count_demain,
            "notify_absence_options": notify_absence_options,
        },
    )


@login_required(login_url="staff_login")
@user_passes_test(is_secretary)
def secretary_notify_patients(request: HttpRequest) -> HttpResponse:
    """Envoie une notification portail à des patients ciblés (RDV ou absence)."""
    if request.method != "POST":
        return redirect("secretary_desk")

    scope = (request.POST.get("scope") or "").strip()
    message = (request.POST.get("message") or "").strip()
    if not message:
        messages.error(request, "Saisissez un message pour les patients.")
        return redirect("secretary_desk")
    if len(message) > 2000:
        messages.error(request, "Message trop long (2000 caractères maximum).")
        return redirect("secretary_desk")

    tz = timezone.get_current_timezone()
    jour = timezone.localdate()
    notif_type = "rdv"
    patient_ids: list[int] = []

    if scope == "rdv_aujourdhui":
        patient_ids = _patient_ids_rdv_day(jour, tz)
    elif scope == "rdv_demain":
        patient_ids = _patient_ids_rdv_day(jour + datetime.timedelta(days=1), tz)
    elif scope == "absence":
        notif_type = "absence"
        try:
            aid = int(request.POST.get("absence_id", "0"))
        except ValueError:
            aid = 0
        absence = Absence.objects.filter(pk=aid).select_related("medecin").first()
        if absence is None:
            messages.error(request, "Absence introuvable.")
            return redirect("secretary_desk")
        a0, a1 = _local_day_bounds(absence.date_absence, tz)
        patient_ids = list(
            RendezVous.objects.filter(
                medecin=absence.medecin,
                date_heure__gte=a0,
                date_heure__lt=a1,
                patient__isnull=False,
            )
            .exclude(statut="annulé")
            .values_list("patient_id", flat=True)
            .distinct()
        )
    else:
        messages.error(request, "Cible de notification invalide.")
        return redirect("secretary_desk")

    if not patient_ids:
        msg = (
            "Aucun patient avec compte et rendez-vous actif pour cette sélection "
            "(seuls les RDV liés à une fiche patient reçoivent une notification sur l’espace patient)."
        )
        if scope == "rdv_aujourdhui":
            d0, d1 = _local_day_bounds(jour, tz)
            g = (
                RendezVous.objects.filter(
                    date_heure__gte=d0,
                    date_heure__lt=d1,
                    patient__isnull=True,
                )
                .exclude(statut="annulé")
                .count()
            )
            if g:
                msg += f" Détail : {g} rendez-vous « visiteur » (sans compte) aujourd’hui — contactez-les par e-mail ou téléphone."
        elif scope == "rdv_demain":
            d0, d1 = _local_day_bounds(jour + datetime.timedelta(days=1), tz)
            g = (
                RendezVous.objects.filter(
                    date_heure__gte=d0,
                    date_heure__lt=d1,
                    patient__isnull=True,
                )
                .exclude(statut="annulé")
                .count()
            )
            if g:
                msg += f" Détail : {g} rendez-vous « visiteur » (sans compte) demain — contactez-les hors portail."
        elif scope == "absence":
            msg += (
                " Pour une absence : seuls les RDV encore actifs ce jour-là avec le même médecin "
                "comptent ; à l’enregistrement d’une absence, les créneaux sont souvent déjà annulés."
            )
        messages.warning(request, msg)
        return redirect("secretary_desk")

    with transaction.atomic():
        for pid in patient_ids:
            p = Patient.objects.filter(pk=pid).first()
            if p:
                notify_patient(p, message, notif_type)

    messages.success(
        request,
        f"Notification envoyée à {len(patient_ids)} patient(s). "
        "Ils la verront sur leur tableau de bord (badge notifications).",
    )
    return redirect("secretary_desk")


@login_required(login_url="staff_login")
@user_passes_test(is_secretary)
@ensure_csrf_cookie
def secretary_rdv_creer(request: HttpRequest) -> HttpResponse:
    medecins = medecins_for_appointments()
    if request.method == "POST":
        patient_q = (request.POST.get("patient") or "").strip()[:200]
        try:
            mid = int(request.POST.get("medecin", "0"))
        except ValueError:
            mid = 0
        d = request.POST.get("date")
        h = request.POST.get("heure", "09:00")
        motif = (request.POST.get("motif") or "").strip()
        tel = (request.POST.get("telephone") or "").strip()[:20]

        def _rdv_form_sticky() -> dict:
            return {
                "telephone": tel,
                "date": (d or "").strip(),
                "heure": (h or "09:00").strip(),
                "motif": motif,
                "patient_nom": patient_q,
                "medecin": str(mid) if mid else "",
            }

        p, err_patient = _secretary_resolve_patient_from_name(patient_q)
        if err_patient:
            messages.error(request, err_patient)
            return render(
                request,
                "cabinet/secretary_rdv_creer.html",
                {
                    "medecins": medecins,
                    "form_sticky": _rdv_form_sticky(),
                },
            )

        med = get_object_or_404(Medecin, pk=mid)
        try:
            parts = h.split(":")
            hh, mm = int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
            day = datetime.date.fromisoformat(d)
            when = timezone.make_aware(
                datetime.datetime.combine(day, time(hh, mm)),
                timezone.get_current_timezone(),
            )
        except (ValueError, OSError):
            messages.error(request, "Date ou heure invalide.")
            return render(
                request,
                "cabinet/secretary_rdv_creer.html",
                {
                    "medecins": medecins,
                    "form_sticky": _rdv_form_sticky(),
                },
            )
        if RendezVous.objects.filter(
            medecin=med,
            date_heure=when,
            statut__in=["en_attente", "confirmé"],
        ).exists():
            messages.error(request, MSG_CONFLIT)
            alts = suggest_available_slots(med, from_date=day)
            return render(
                request,
                "cabinet/secretary_rdv_creer.html",
                {
                    "medecins": medecins,
                    "error": MSG_CONFLIT,
                    "alternatives": alts,
                    "form_sticky": _rdv_form_sticky(),
                },
            )
        with transaction.atomic():
            if tel:
                p.telephone = tel
                p.save(update_fields=["telephone"])
            rdv = RendezVous.objects.create(
                patient=p,
                medecin=med,
                date_heure=when,
                motif=motif,
                statut="confirmé",
                cree_par="secretaire",
            )
        notify_patient(
            p,
            f"Votre rendez-vous du {when.strftime('%d/%m/%Y %H:%M')} avec Dr {med.user.get_full_name() or med.user.last_name or med.user.username} a été confirmé.",
            "rdv",
        )
        messages.success(request, "Rendez-vous créé et patient notifié.")
        return redirect("secretary_rdv_creer")
    return render(
        request,
        "cabinet/secretary_rdv_creer.html",
        {
            "medecins": medecins,
            "form_sticky": {},
        },
    )


@login_required(login_url="staff_login")
@user_passes_test(is_secretary)
def secretary_statut_cabinet(request: HttpRequest) -> HttpResponse:
    s = get_object_or_404(Secretaire, user=request.user)
    if request.method == "POST":
        n = (request.POST.get("statut") or "ouvert").lower()
        if n not in ("ouvert", "fermé"):
            n = "ouvert"
        c = StatutCabinet.get_solo()
        old = c.statut
        c.statut = n
        c.modifie_par = s
        c.save()
        if old != c.statut:
            st = "ouvert" if c.statut == "ouvert" else "fermé"
            notify_all_patients(
                f"Le cabinet est maintenant {st}.",
                "cabinet",
            )
        messages.success(request, "Statut du cabinet mis à jour.")
        if request.POST.get("redirect_to") == "desk":
            return redirect("secretary_desk")
        return redirect("secretary_statut_cabinet")
    cab = StatutCabinet.get_solo()
    return render(
        request, "cabinet/secretary_statut.html", {"cab": cab, "secretaire": s}
    )


@login_required(login_url="staff_login")
@user_passes_test(is_secretary)
def secretary_absence(request: HttpRequest) -> HttpResponse:
    medecins = medecins_for_appointments()
    s = get_object_or_404(Secretaire, user=request.user)
    if request.method == "POST":
        mid = int(request.POST.get("medecin", "0"))
        d = request.POST.get("date")
        motif = (request.POST.get("motif") or "").strip()
        med = get_object_or_404(Medecin, pk=mid)
        dabs = datetime.date.fromisoformat(d)
        a = Absence.objects.create(
            medecin=med,
            date_absence=dabs,
            motif=motif,
            signalee_par="secretaire",
        )
        on_absence_created(a)
        notify_secretaries_absence(a)
        messages.success(
            request,
            "Absence enregistrée, annonce envoyée au secrétariat et patients notifiés.",
        )
        return redirect("secretary_absence")
    return render(
        request,
        "cabinet/secretary_absence.html",
        {
            "medecins": medecins,
            "secretaire": s,
            "absences_historique": absences_for_history(),
        },
    )


@login_required(login_url="staff_login")
@user_passes_test(is_secretary)
def secretary_agenda(request: HttpRequest) -> HttpResponse:
    j = request.GET.get("jour")
    if j:
        day = datetime.date.fromisoformat(j)
    else:
        day = timezone.localdate()
    start = timezone.make_aware(
        datetime.datetime.combine(day, time.min),
        timezone.get_current_timezone(),
    )
    end = start + datetime.timedelta(days=1)
    rdvs = (
        RendezVous.objects.filter(date_heure__gte=start, date_heure__lt=end)
        .select_related("patient__user", "medecin__user")
        .order_by("date_heure")
    )
    return render(
        request,
        "cabinet/secretary_agenda.html",
        {"rdvs": rdvs, "jour": day},
    )


@login_required(login_url="staff_login")
@user_passes_test(is_secretary)
def secretary_patient_dossier(request: HttpRequest, patient_id: int) -> HttpResponse:
    p = get_object_or_404(Patient, pk=patient_id)
    doss = get_object_or_404(DossierMedical, patient=p)
    rdvs = RendezVous.objects.filter(patient=p).order_by("-date_heure")
    ordon = Ordonnance.objects.filter(patient=p).select_related("medecin__user")
    return render(
        request,
        "cabinet/secretary_patient_dossier.html",
        {"patient": p, "doss": doss, "rdvs": rdvs, "ordonnances": ordon},
    )


@login_required(login_url="staff_login")
@user_passes_test(is_secretary)
def secretary_rdv_action(request: HttpRequest, pk: int) -> HttpResponse:
    get_object_or_404(Secretaire, user=request.user)
    rdv = get_object_or_404(RendezVous, pk=pk)
    if request.method == "POST":
        act = request.POST.get("action", "")
        if act == "confirm":
            if rdv.statut != "confirmé":
                rdv.statut = "confirmé"
                rdv.save()
                if rdv.patient_id:
                    notify_patient(
                        rdv.patient,
                        f"Votre rendez-vous du {rdv.date_heure.strftime('%d/%m/%Y %H:%M')} a été confirmé par le secrétariat.",
                        "rdv",
                    )
        elif act == "annuler":
            rdv.statut = "annulé"
            rdv.save()
            if rdv.patient_id:
                notify_patient(
                    rdv.patient,
                    f"Votre rendez-vous du {rdv.date_heure.strftime('%d/%m/%Y %H:%M')} a été annulé par le secrétariat.",
                    "rdv",
                )
        messages.success(request, "Rendez-vous mis à jour.")
    return redirect("secretary_agenda")
