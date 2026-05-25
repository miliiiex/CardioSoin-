from __future__ import annotations

import calendar
import datetime
import json
import os
from decimal import Decimal, InvalidOperation
from collections import defaultdict
from datetime import time, timedelta
from typing import Any

from accounts.models import Medecin, Secretaire, User
from accounts.permissions import is_doctor
from appointments.models import RendezVous
from cabinet.absence_service import (
    absences_for_history,
    notify_secretaries_absence,
    on_absence_created,
)
from cabinet.desk_risk_svg import build_risk_trend_svg
from cabinet.ecg_analysis import analyze_physionet_mit_record
from cabinet.models import Absence, ECGAnalyse, ScoreCardiovasculaire, StatutCabinet
from cabinet.notify import notify_patient
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import IntegrityError, transaction
from django.db.utils import DatabaseError
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from patients.models import DossierMedical, Patient
from prescriptions.certificat_text import build_certificat_redaction
from prescriptions.documents_catalog import (
    BILAN_KEY_SET,
    CERTIFICAT_TYPES,
    EXAMEN_KEY_SET,
    BILAN_ITEMS,
    CERTIFICAT_KEY_SET,
    EXAMEN_ITEMS,
)
from prescriptions.models import DocumentMedical, Medicament, Ordonnance


_STAFF_AVATAR_MAX_BYTES = 2 * 1024 * 1024


def _staff_avatar_upload(request: HttpRequest) -> tuple[Any | None, str | None]:
    """Retourne (fichier image ou None, message d'erreur ou None)."""
    f = request.FILES.get("avatar")
    if not f or not getattr(f, "name", ""):
        return None, None
    if getattr(f, "size", 0) > _STAFF_AVATAR_MAX_BYTES:
        return None, "Image trop volumineuse (maximum 2 Mo)."
    return f, None


def _parse_secretaire_salaire(request: HttpRequest) -> tuple[Decimal | None, str | None]:
    raw = (request.POST.get("salaire") or "").strip().replace(" ", "").replace(",", ".")
    if not raw:
        return None, None
    try:
        value = Decimal(raw)
    except InvalidOperation:
        return None, "Salaire invalide : utilisez un nombre (ex. 8500 ou 8500,50)."
    if value < 0:
        return None, "Le salaire ne peut pas être négatif."
    if value > Decimal("99999999.99"):
        return None, "Salaire hors limite."
    return value, None


MITBIH_DEMO_RECORDS: tuple[tuple[str, str], ...] = (
    ("100", "100 — signal de référence"),
    ("101", "101 — rythme régulier"),
    ("103", "103"),
    ("105", "105"),
    ("106", "106 — extrasystoles"),
    ("109", "109"),
    ("111", "111"),
    ("118", "118"),
    ("124", "124"),
    ("208", "208 — complexes V"),
    ("214", "214"),
    ("217", "217"),
    ("219", "219"),
)


def _mitbih_local_dir() -> str | None:
    d = os.environ.get("MITBIH_LOCAL_DIR", "").strip()
    return d or None


@login_required(login_url="staff_login")
@user_passes_test(is_doctor)
def doctor_desk(request: HttpRequest) -> HttpResponse:
    med = get_object_or_404(Medecin, user=request.user)
    tz = timezone.get_current_timezone()
    now = timezone.now()
    jour = timezone.localdate()

    cab = StatutCabinet.get_solo()

    start = timezone.make_aware(datetime.datetime.combine(jour, time.min), tz)
    end = start + datetime.timedelta(days=1)
    rdvs_aujourdhui = list(
        RendezVous.objects.filter(
            medecin=med, date_heure__gte=start, date_heure__lt=end
        )
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
        medecin=med,
        date_heure__gte=planning_start,
        date_heure__lte=planning_end,
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

    stat_patients = Patient.objects.count()
    stat_total_secretaires = Secretaire.objects.count()
    stat_rdv_a_venir = (
        RendezVous.objects.filter(medecin=med, date_heure__gte=now)
        .exclude(statut="annulé")
        .count()
    )

    _NIVEAU_SLUG = {"faible": "low", "modéré": "mid", "élevé": "high"}
    last_scores = list(
        ScoreCardiovasculaire.objects.filter(medecin=med)
        .select_related("patient__user")
        .order_by("-date_calcul")[:3]
    )
    score_bars: list[dict[str, Any]] = []
    for s in last_scores:
        r = float(s.risk_percent)
        p = s.patient.user
        score_bars.append(
            {
                "risk": r,
                "label": timezone.localtime(s.date_calcul, tz).strftime("%d/%m %H:%M"),
                "label_short": timezone.localtime(s.date_calcul, tz).strftime("%d/%m"),
                "niveau": s.get_niveau_display(),
                "niveau_slug": _NIVEAU_SLUG.get(s.niveau, "mid"),
                "patient": (p.get_full_name() or p.username or "Patient")[:32],
            }
        )
    chrono_risks = [float(b["risk"]) for b in reversed(score_bars)]
    curve_x_labels = [b["label_short"] for b in reversed(score_bars)]
    score_curve = (
        build_risk_trend_svg(chrono_risks, x_labels=curve_x_labels)
        if chrono_risks
        else None
    )

    return render(
        request,
        "accounts/doctor_desk.html",
        {
            "user": request.user,
            "medecin": med,
            "cabinet_statut": cab.statut,
            "stat_patients": stat_patients,
            "stat_total_secretaires": stat_total_secretaires,
            "stat_rdv_aujourdhui": stat_rdv_aujourdhui,
            "stat_rdv_a_venir": stat_rdv_a_venir,
            "jour": jour,
            "rdvs_aujourdhui": rdvs_aujourdhui,
            "rdvs_planning": rdvs_planning,
            "rdv_date_marks": rdv_date_marks,
            "patients_recent": patients_recent,
            "score_bars": score_bars,
            "score_curve": score_curve,
        },
    )


_MOIS_FR = (
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
)


@login_required(login_url="staff_login")
@user_passes_test(is_doctor)
def doctor_agenda(request: HttpRequest) -> HttpResponse:
    med = get_object_or_404(Medecin, user=request.user)
    j = request.GET.get("jour")
    if j:
        try:
            day = datetime.date.fromisoformat(j)
        except ValueError:
            day = timezone.localdate()
    else:
        day = timezone.localdate()

    year, month = day.year, day.month
    tz = timezone.get_current_timezone()
    if month == 12:
        month_end = datetime.date(year + 1, 1, 1)
    else:
        month_end = datetime.date(year, month + 1, 1)
    month_start = datetime.date(year, month, 1)
    range_start = timezone.make_aware(
        datetime.datetime.combine(month_start, time.min), tz
    )
    range_end = timezone.make_aware(
        datetime.datetime.combine(month_end, time.min), tz
    )
    all_rdvs = (
        RendezVous.objects.filter(
            medecin=med, date_heure__gte=range_start, date_heure__lt=range_end
        )
        .select_related("patient__user")
        .order_by("date_heure")
    )
    by_day: dict[datetime.date, list[RendezVous]] = defaultdict(list)
    for r in all_rdvs:
        d = timezone.localtime(r.date_heure, tz).date()
        by_day[d].append(r)

    cal = calendar.Calendar(firstweekday=0)  # lundi
    month_weeks: list[list[dict[str, Any]]] = []
    for week in cal.monthdatescalendar(year, month):
        row: list[dict[str, Any]] = []
        for d in week:
            row.append(
                {
                    "date": d,
                    "in_month": d.month == month,
                    "rdvs": by_day.get(d, []),
                }
            )
        month_weeks.append(row)

    if month == 1:
        py, pm = year - 1, 12
    else:
        py, pm = year, month - 1
    if month == 12:
        ny, nm = year + 1, 1
    else:
        ny, nm = year, month + 1
    prev_mois = datetime.date(py, pm, 1)
    next_mois = datetime.date(ny, nm, 1)

    return render(
        request,
        "cabinet/doctor_agenda.html",
        {
            "agenda_mois": month_weeks,
            "mois_label": f"{_MOIS_FR[month - 1]} {year}",
            "jour": day,
            "prev_mois": prev_mois,
            "next_mois": next_mois,
            "medecin": med,
        },
    )


def _safe_next_path(nxt: str | None) -> str | None:
    if nxt and nxt.startswith("/") and not nxt.startswith("//"):
        return nxt
    return None


@login_required(login_url="staff_login")
@user_passes_test(is_doctor)
def doctor_rdv_terminer(request: HttpRequest, pk: int) -> HttpResponse:
    med = get_object_or_404(Medecin, user=request.user)
    rdv = get_object_or_404(RendezVous, pk=pk, medecin=med)
    nxt: str | None = None
    if request.method == "POST":
        rdv.statut = "terminé"
        rdv.save()
        messages.success(request, "Consultation marquée comme terminée.")
        nxt = _safe_next_path(request.POST.get("next"))
    if nxt:
        return redirect(nxt)
    return redirect("doctor_agenda")


@login_required(login_url="staff_login")
@user_passes_test(is_doctor)
@require_POST
def doctor_dossier_autosave(request: HttpRequest, patient_id: int) -> JsonResponse:
    p = get_object_or_404(Patient, pk=patient_id)
    doss, _ = DossierMedical.objects.get_or_create(patient=p)
    try:
        body = json.loads(request.body.decode() or "{}")
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"ok": False, "error": "Format JSON invalide."}, status=400)
    if "antecedents" in body:
        doss.antecedents = str(body.get("antecedents") or "")
    if "allergies" in body:
        doss.allergies = str(body.get("allergies") or "")
    if "notes_generales" in body:
        doss.notes_generales = str(body.get("notes_generales") or "")
    doss.save()
    return JsonResponse(
        {
            "ok": True,
            "saved_at": timezone.now().isoformat(),
        }
    )


@login_required(login_url="staff_login")
@user_passes_test(is_doctor)
def doctor_dossier(request: HttpRequest, patient_id: int) -> HttpResponse:
    p = get_object_or_404(Patient, pk=patient_id)
    doss, _ = DossierMedical.objects.get_or_create(patient=p)
    rdvs = (
        RendezVous.objects.filter(patient=p)
        .select_related("medecin__user")
        .order_by("-date_heure")
    )
    if request.method == "POST":
        doss.antecedents = request.POST.get("antecedents", "")
        doss.allergies = request.POST.get("allergies", "")
        doss.notes_generales = request.POST.get("notes_generales", "")
        doss.save()
        messages.success(request, "Dossier enregistré.")
        return redirect("doctor_dossier", patient_id=p.id)
    return render(
        request,
        "cabinet/doctor_dossier.html",
        {"patient": p, "doss": doss, "rdvs": rdvs},
    )


def _rdv_optional_for_doctor_patient(
    med: Medecin, patient: Patient, rdv_id_raw: str
) -> tuple[RendezVous | None, str | None]:
    """Retourne (rdv, erreur_message)."""
    raw = (rdv_id_raw or "").strip()
    if not raw:
        return None, None
    try:
        rid = int(raw)
    except ValueError:
        return None, "Identifiant de rendez-vous invalide."
    rdv = RendezVous.objects.filter(pk=rid, patient=patient, medecin=med).first()
    if rdv is None:
        return None, "Rendez-vous introuvable ou ne correspond pas à ce patient."
    return rdv, None


@login_required(login_url="staff_login")
@user_passes_test(is_doctor)
def doctor_ordonnance_nouveau(request: HttpRequest) -> HttpResponse:
    med = get_object_or_404(Medecin, user=request.user)
    patients = Patient.objects.select_related("user").order_by(
        "user__last_name", "user__first_name"
    )
    rdvs_qs = (
        RendezVous.objects.filter(medecin=med, patient__isnull=False)
        .select_related("patient__user")
        .order_by("-date_heure")[:400]
    )
    rdvs_for_js = [
        {
            "id": r.id,
            "patient_id": r.patient_id,
            "label": r.date_heure.strftime("%d/%m/%Y %H:%M"),
            "statut": r.statut,
        }
        for r in rdvs_qs
    ]

    def tpl_ctx(extra: dict | None = None) -> dict:
        c = {
            "patients": patients,
            "medecin": med,
            "rdvs_json": json.dumps(rdvs_for_js),
            "bilan_items": BILAN_ITEMS,
            "examen_items": EXAMEN_ITEMS,
            "certificat_types": CERTIFICAT_TYPES,
            "date_aujourdhui": timezone.localdate().isoformat(),
        }
        if extra:
            c.update(extra)
        return c

    if request.method != "POST":
        return render(request, "cabinet/doctor_ordonnance.html", tpl_ctx())

    doc_action = (request.POST.get("doc_action") or "").strip()

    if doc_action == "ordonnance":
        pid = int(request.POST.get("patient", "0") or 0)
        p = get_object_or_404(Patient, pk=pid)
        rdv, err = _rdv_optional_for_doctor_patient(
            med, p, request.POST.get("ordo_rdv", "")
        )
        if err:
            messages.error(request, err)
            return render(request, "cabinet/doctor_ordonnance.html", tpl_ctx())
        med_names = request.POST.getlist("med_nom")
        dosages = request.POST.getlist("med_dosage")
        durees = request.POST.getlist("med_duree")
        instrs = request.POST.getlist("med_inst")
        lignes: list[dict[str, str]] = []
        for i in range(len(med_names)):
            nom = (med_names[i] or "").strip()
            if not nom:
                continue
            lignes.append(
                {
                    "nom": nom,
                    "dosage": ((dosages[i] if i < len(dosages) else "") or "").strip(),
                    "duree": ((durees[i] if i < len(durees) else "") or "").strip(),
                    "instructions": (
                        (instrs[i] if i < len(instrs) else "") or ""
                    ).strip(),
                }
            )
        if not lignes:
            messages.error(
                request,
                "Indiquez au moins un médicament (le nom est obligatoire).",
            )
            return render(request, "cabinet/doctor_ordonnance.html", tpl_ctx())
        with transaction.atomic():
            o = Ordonnance.objects.create(
                patient=p, medecin=med, rendez_vous=rdv
            )
            for row in lignes:
                Medicament.objects.create(
                    ordonnance=o,
                    nom=row["nom"],
                    dosage=row["dosage"],
                    duree=row["duree"],
                    instructions=row["instructions"],
                )
        notify_patient(
            p,
            "Une nouvelle ordonnance est disponible dans votre espace patient.",
            "ordonnance",
        )
        messages.success(
            request, "Ordonnance créée. Le patient a été notifié."
        )
        return redirect("doctor_ordonnance_nouveau")

    if doc_action == "bilan":
        pid = int(request.POST.get("bilan_patient", "0") or 0)
        p = get_object_or_404(Patient, pk=pid)
        rdv, err = _rdv_optional_for_doctor_patient(
            med, p, request.POST.get("bilan_rdv", "")
        )
        if err:
            messages.error(request, err)
            return render(request, "cabinet/doctor_ordonnance.html", tpl_ctx())
        selected = [
            k for k in request.POST.getlist("bilan_items") if k in BILAN_KEY_SET
        ]
        if not selected:
            messages.error(
                request,
                "Cochez au moins une analyse pour la demande de bilan.",
            )
            return render(request, "cabinet/doctor_ordonnance.html", tpl_ctx())
        commentaire = (request.POST.get("bilan_commentaire") or "").strip()
        with transaction.atomic():
            DocumentMedical.objects.create(
                patient=p,
                medecin=med,
                rendez_vous=rdv,
                kind=DocumentMedical.KIND_BILAN,
                items=selected,
                commentaire=commentaire,
            )
        notify_patient(
            p,
            "Une demande d'analyses (bilan biologique) est disponible dans votre espace patient.",
            "document",
        )
        messages.success(request, "Demande d'analyses enregistrée.")
        return redirect("doctor_ordonnance_nouveau")

    if doc_action == "examens":
        pid = int(request.POST.get("exam_patient", "0") or 0)
        p = get_object_or_404(Patient, pk=pid)
        rdv, err = _rdv_optional_for_doctor_patient(
            med, p, request.POST.get("exam_rdv", "")
        )
        if err:
            messages.error(request, err)
            return render(request, "cabinet/doctor_ordonnance.html", tpl_ctx())
        selected = [
            k for k in request.POST.getlist("examen_items") if k in EXAMEN_KEY_SET
        ]
        if not selected:
            messages.error(
                request, "Cochez au moins un examen pour la demande."
            )
            return render(request, "cabinet/doctor_ordonnance.html", tpl_ctx())
        commentaire = (request.POST.get("exam_commentaire") or "").strip()
        with transaction.atomic():
            DocumentMedical.objects.create(
                patient=p,
                medecin=med,
                rendez_vous=rdv,
                kind=DocumentMedical.KIND_EXAMENS,
                items=selected,
                commentaire=commentaire,
            )
        notify_patient(
            p,
            "Une demande d'examens est disponible dans votre espace patient.",
            "document",
        )
        messages.success(request, "Demande d'examens enregistrée.")
        return redirect("doctor_ordonnance_nouveau")

    if doc_action == "certificat":
        pid = int(request.POST.get("cert_patient", "0") or 0)
        p = get_object_or_404(Patient, pk=pid)
        rdv, err = _rdv_optional_for_doctor_patient(
            med, p, request.POST.get("cert_rdv", "")
        )
        if err:
            messages.error(request, err)
            return render(request, "cabinet/doctor_ordonnance.html", tpl_ctx())
        ctype = (request.POST.get("certificat_type") or "").strip()
        if ctype not in CERTIFICAT_KEY_SET:
            messages.error(request, "Choisissez un type de certificat.")
            return render(request, "cabinet/doctor_ordonnance.html", tpl_ctx())
        probleme = (request.POST.get("cert_probleme") or "").strip()
        if not probleme:
            messages.error(
                request,
                "Décrivez le problème ou le motif médical (ex. arythmie, suivi post-opératoire…).",
            )
            return render(request, "cabinet/doctor_ordonnance.html", tpl_ctx())
        duree_raw = (request.POST.get("cert_duree_jours") or "").strip()
        try:
            duree_jours = int(duree_raw) if duree_raw else 0
        except ValueError:
            duree_jours = 0
            messages.error(request, "La durée doit être un nombre de jours entier.")
            return render(request, "cabinet/doctor_ordonnance.html", tpl_ctx())
        date_debut_s = (request.POST.get("cert_date_debut") or "").strip()
        try:
            date_debut = (
                datetime.date.fromisoformat(date_debut_s)
                if date_debut_s
                else timezone.localdate()
            )
        except ValueError:
            date_debut = timezone.localdate()
        precisions = (request.POST.get("cert_precisions") or "").strip()
        lieu = (request.POST.get("cert_lieu") or "France").strip() or "France"
        certificat_data = {
            "probleme": probleme,
            "duree_jours": duree_jours,
            "date_debut": date_debut.isoformat(),
            "precisions": precisions,
            "lieu": lieu,
            "numero_dossier": str(p.pk),
        }
        doc_tmp = DocumentMedical(
            patient=p,
            medecin=med,
            kind=DocumentMedical.KIND_CERTIFICAT,
            certificat_type=ctype,
            commentaire=probleme,
            certificat_data=certificat_data,
        )
        doc_tmp.date_creation = timezone.now()
        texte_genere = build_certificat_redaction(doc_tmp, p, med)
        certificat_data["texte_genere"] = texte_genere
        with transaction.atomic():
            DocumentMedical.objects.create(
                patient=p,
                medecin=med,
                rendez_vous=rdv,
                kind=DocumentMedical.KIND_CERTIFICAT,
                certificat_type=ctype,
                items=[],
                commentaire=probleme,
                certificat_data=certificat_data,
            )
        notify_patient(
            p,
            "Un certificat médical est disponible dans votre espace patient.",
            "document",
        )
        messages.success(request, "Certificat enregistré.")
        return redirect("doctor_ordonnance_nouveau")

    messages.error(request, "Action non reconnue.")
    return render(request, "cabinet/doctor_ordonnance.html", tpl_ctx())


@login_required(login_url="staff_login")
@user_passes_test(is_doctor)
@require_POST
def doctor_certificat_apercu(request: HttpRequest) -> JsonResponse:
    """Aperçu JSON du texte du certificat (formulaire médecin)."""
    med = get_object_or_404(Medecin, user=request.user)
    pid = int(
        request.POST.get("patient_id")
        or request.POST.get("cert_patient")
        or "0"
    )
    p = get_object_or_404(Patient, pk=pid)
    ctype = (request.POST.get("certificat_type") or "").strip()
    if ctype not in CERTIFICAT_KEY_SET:
        ctype = "aptitude_sport"
    probleme = (request.POST.get("cert_probleme") or "").strip() or "son état de santé cardiovasculaire"
    duree_raw = (request.POST.get("cert_duree_jours") or "").strip()
    try:
        duree_jours = int(duree_raw) if duree_raw else 0
    except ValueError:
        duree_jours = 0
    date_debut_s = (request.POST.get("cert_date_debut") or "").strip()
    try:
        date_debut = (
            datetime.date.fromisoformat(date_debut_s)
            if date_debut_s
            else timezone.localdate()
        )
    except ValueError:
        date_debut = timezone.localdate()
    precisions = (request.POST.get("cert_precisions") or "").strip()
    from prescriptions.certificat_text import build_certificat_redaction_from_form

    texte = build_certificat_redaction_from_form(
        probleme=probleme,
        duree_jours=duree_jours,
        date_debut=date_debut,
        certificat_type=ctype,
        patient=p,
        medecin=med,
        precisions=precisions,
    )
    return JsonResponse({"texte": texte})


@login_required(login_url="staff_login")
@user_passes_test(is_doctor)
def doctor_score(request: HttpRequest) -> HttpResponse:
    med = get_object_or_404(Medecin, user=request.user)
    patients = Patient.objects.select_related("user")
    local_mit = _mitbih_local_dir()
    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        if action != "ecg_mitbih":
            messages.error(request, "Action non reconnue.")
            return redirect("doctor_score")
        pid = int(request.POST.get("patient", "0"))
        p = get_object_or_404(Patient, pk=pid)
        record_id = (request.POST.get("mit_record") or "100").strip()
        blend = request.POST.get("blend_framingham") == "1"
        prev_framingham = (
            ScoreCardiovasculaire.objects.filter(patient=p)
            .order_by("-date_calcul")
            .first()
        )
        fr_risk = (
            float(prev_framingham.risk_percent)
            if (blend and prev_framingham)
            else None
        )
        res = analyze_physionet_mit_record(
            record_id,
            local_dir=local_mit,
            framingham_risk_percent=fr_risk,
        )
        if not res.ok:
            messages.error(request, res.error)
        else:
            try:
                obj = ECGAnalyse.objects.create(
                    patient=p,
                    medecin=med,
                    dataset="mitdb",
                    record_id=record_id,
                    fs=res.fs,
                    duree_s=res.duree_s,
                    risk_percent=res.risk_percent,
                    niveau=res.niveau,
                    risk_ecg_seul=res.risk_ecg_seul,
                    metrics=res.metrics,
                    beat_counts=res.beat_counts,
                    waveform=res.waveform,
                )
            except DatabaseError:
                messages.error(
                    request,
                    "La base ne contient pas encore la table d’analyse ECG. "
                    "Dans un terminal : allez dans le dossier « backend », "
                    "désactivez DJANGO_USE_SQLITE si besoin, puis exécutez : python manage.py migrate",
                )
            else:
                request.session["last_ecg_analyse_id"] = obj.pk
                messages.success(
                    request,
                    f"Analyse ECG enregistrée — indice {res.risk_percent:.1f} % ({res.niveau}).",
                )
        return redirect("doctor_score")
    last_ecg_pk = request.session.pop("last_ecg_analyse_id", None)
    last_ecg = None
    ecg_chart_items: list[dict[str, Any]] = []
    ecg_db_unavailable = False
    tz = timezone.get_current_timezone()
    try:
        if last_ecg_pk:
            last_ecg = (
                ECGAnalyse.objects.filter(pk=last_ecg_pk, medecin=med)
                .select_related("patient__user")
                .first()
            )
        if not last_ecg:
            last_ecg = (
                ECGAnalyse.objects.filter(medecin=med)
                .select_related("patient__user")
                .order_by("-date_analyse")
                .first()
            )
        ecg_timeline = (
            ECGAnalyse.objects.filter(medecin=med)
            .select_related("patient__user")
            .order_by("date_analyse")
        )[:80]
        for e in ecg_timeline:
            ecg_chart_items.append(
                {
                    "t": timezone.localtime(e.date_analyse, tz).isoformat(),
                    "r": float(e.risk_percent),
                    "rec": e.record_id,
                    "niv": e.niveau,
                    "patient": e.patient.user.get_full_name() or e.patient.user.username,
                }
            )
    except DatabaseError:
        ecg_db_unavailable = True
        last_ecg = None
        ecg_chart_items = []
    return render(
        request,
        "cabinet/doctor_score.html",
        {
            "patients": patients,
            "medecin": med,
            "mitbih_records": MITBIH_DEMO_RECORDS,
            "mitbih_local_hint": bool(local_mit),
            "last_ecg": last_ecg,
            "ecg_chart_data": {"items": ecg_chart_items},
            "ecg_db_unavailable": ecg_db_unavailable,
        },
    )


@login_required(login_url="staff_login")
@user_passes_test(is_doctor)
@require_POST
def doctor_ecg_analyze_api(request: HttpRequest) -> JsonResponse:
    """Analyse MIT-BIH (JSON) pour mise à jour quasi temps réel côté navigateur."""
    med = get_object_or_404(Medecin, user=request.user)
    data: dict[str, Any] = {}
    if request.content_type and "application/json" in request.content_type:
        try:
            data = json.loads(request.body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"ok": False, "error": "JSON invalide."}, status=400)
    else:
        data = request.POST.dict()
    record_id = (data.get("record") or data.get("mit_record") or "100").strip()
    try:
        pid = int(data.get("patient_id") or data.get("patient") or 0)
    except (TypeError, ValueError):
        pid = 0
    if pid <= 0:
        return JsonResponse(
            {"ok": False, "error": "Identifiant patient requis."}, status=400
        )
    p = get_object_or_404(Patient, pk=pid)
    blend = str(data.get("blend_framingham", "")).lower() in ("1", "true", "yes")
    prev_framingham = (
        ScoreCardiovasculaire.objects.filter(patient=p).order_by("-date_calcul").first()
    )
    fr_risk = (
        float(prev_framingham.risk_percent)
        if (blend and prev_framingham)
        else None
    )
    res = analyze_physionet_mit_record(
        record_id,
        local_dir=_mitbih_local_dir(),
        framingham_risk_percent=fr_risk,
    )
    if not res.ok:
        return JsonResponse({"ok": False, "error": res.error}, status=400)
    save = str(data.get("save", "1")).lower() not in ("0", "false", "no")
    out = res.as_dict()
    out["ok"] = True
    if save:
        try:
            obj = ECGAnalyse.objects.create(
                patient=p,
                medecin=med,
                dataset="mitdb",
                record_id=record_id,
                fs=res.fs,
                duree_s=res.duree_s,
                risk_percent=res.risk_percent,
                niveau=res.niveau,
                risk_ecg_seul=res.risk_ecg_seul,
                metrics=res.metrics,
                beat_counts=res.beat_counts,
                waveform=res.waveform,
            )
        except DatabaseError:
            return JsonResponse(
                {
                    "ok": False,
                    "error": "Table ECG absente : exécutez « python manage.py migrate » "
                    "sur MySQL (sans variable DJANGO_USE_SQLITE).",
                },
                status=503,
            )
        out["saved_id"] = obj.pk
    else:
        out["saved_id"] = None
    return JsonResponse(out)


@login_required(login_url="staff_login")
@user_passes_test(is_doctor)
def doctor_secretaires(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "create":
            salaire, salaire_err = _parse_secretaire_salaire(request)
            if salaire_err:
                messages.error(request, salaire_err)
                return redirect("doctor_secretaires")
            avatar_f, avatar_err = _staff_avatar_upload(request)
            if avatar_err:
                messages.error(request, avatar_err)
                return redirect("doctor_secretaires")
            try:
                u = User.objects.create_user(
                    username=(request.POST.get("username") or "").strip(),
                    email=(request.POST.get("email") or "").strip(),
                    password=request.POST.get("password") or "changeme",
                    first_name=(request.POST.get("first_name") or "").strip(),
                    last_name=(request.POST.get("last_name") or "").strip(),
                    role="secretary",
                )
            except IntegrityError:
                messages.error(
                    request, "Identifiant ou e-mail déjà utilisé. Choisissez un autre nom d’utilisateur."
                )
            else:
                if avatar_f:
                    u.avatar = avatar_f
                    u.save(update_fields=["avatar"])
                Secretaire.objects.create(
                    user=u,
                    telephone=(request.POST.get("telephone") or "").strip(),
                    salaire=salaire,
                )
                messages.success(request, "Compte secrétaire créé.")
        elif action == "update":
            salaire, salaire_err = _parse_secretaire_salaire(request)
            if salaire_err:
                messages.error(request, salaire_err)
                return redirect("doctor_secretaires")
            avatar_f, avatar_err = _staff_avatar_upload(request)
            if avatar_err:
                messages.error(request, avatar_err)
                return redirect("doctor_secretaires")
            sid = int(request.POST.get("id", "0"))
            s = get_object_or_404(Secretaire, pk=sid)
            s.user.first_name = (request.POST.get("first_name") or "").strip()
            s.user.last_name = (request.POST.get("last_name") or "").strip()
            s.user.email = (request.POST.get("email") or "").strip()
            s.telephone = (request.POST.get("telephone") or "").strip()
            s.salaire = salaire
            s.user.is_active = request.POST.get("is_active") == "1"
            if avatar_f:
                s.user.avatar = avatar_f
            s.user.save()
            s.save()
            messages.success(request, "Secrétaire mis à jour.")
        elif action == "delete":
            sid = int(request.POST.get("id", "0"))
            s = get_object_or_404(Secretaire, pk=sid)
            s.user.delete()
            messages.success(request, "Compte secrétaire supprimé.")
        return redirect("doctor_secretaires")
    secs = Secretaire.objects.select_related("user")
    return render(request, "cabinet/doctor_secretaires.html", {"secretaires": secs})


@login_required(login_url="staff_login")
@user_passes_test(is_doctor)
def doctor_absence(request: HttpRequest) -> HttpResponse:
    med = get_object_or_404(Medecin, user=request.user)
    if request.method == "POST":
        d = request.POST.get("date")
        motif = (request.POST.get("motif") or "").strip()
        dabs = datetime.date.fromisoformat(d)
        a = Absence.objects.create(
            medecin=med,
            date_absence=dabs,
            motif=motif,
            signalee_par="medecin",
        )
        on_absence_created(a)
        notify_secretaries_absence(a)
        messages.success(
            request,
            "Absence enregistrée, secrétariat informé et patients notifiés.",
        )
        return redirect("doctor_absence")
    return render(
        request,
        "cabinet/doctor_absence.html",
        {
            "medecin": med,
            "absences_historique": absences_for_history(medecin=med),
        },
    )
