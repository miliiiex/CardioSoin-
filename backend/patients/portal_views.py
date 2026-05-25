from __future__ import annotations

import datetime
from datetime import timedelta, time
from io import BytesIO

from accounts.medecin_utils import medecins_for_appointments
from accounts.models import Medecin, User
from accounts.permissions import is_patient
from accounts.views import _validate_birth_date
from appointments.models import RendezVous
from cabinet.models import Notification, StatutCabinet, ScoreCardiovasculaire
from cabinet.slots import suggest_available_slots
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import FileResponse, HttpRequest, HttpResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from patients.models import Patient
from patients.patient_utils import ensure_patient_for_user
from prescriptions.models import DocumentMedical, Ordonnance
from prescriptions.pdf import build_document_medical_pdf, build_ordonnance_pdf

MSG_CRENEAU_PRIS = (
    "Ce créneau est déjà réservé. Veuillez choisir un autre horaire."
)
MSG_DATE_HEURE_PASSEE = (
    "Impossible de réserver une date ou une heure déjà passées."
)
MSG_ANNUL_24H = (
    "Annulation impossible — moins de 24h. Veuillez contacter le cabinet."
)

_AVATAR_MAX_BYTES = 2 * 1024 * 1024


def _patient_page_back(request: HttpRequest) -> tuple[str, str]:
    """URL et libellé du lien retour selon la page d’origine (?from=)."""
    src = (request.GET.get("from") or "").strip().lower()
    if src == "ordonnances":
        return reverse("patient_ordonnances"), "Ordonnances et documents"
    if src == "dashboard":
        return reverse("patient_space"), "Tableau de bord"
    return reverse("patient_rendez_vous"), "Mes rendez-vous"


def _landing_rdv_form_snapshot(request: HttpRequest) -> dict:
    return {
        "medecin": request.POST.get("medecin") or "",
        "date": request.POST.get("date") or "",
        "heure": request.POST.get("heure") or "",
        "motif": request.POST.get("motif") or "",
        "guest_nom_complet": (request.POST.get("guest_nom_complet") or "").strip(),
        "guest_email": (request.POST.get("guest_email") or "").strip(),
        "guest_telephone": (request.POST.get("guest_telephone") or "").strip(),
    }


def _respond_rdv_booking_error(
    request: HttpRequest,
    *,
    error_msg: str,
    alternatives: list,
    medecins,
    from_landing: bool,
) -> HttpResponse:
    """Erreur de réservation : page dédiée patient ou retour accueil avec session."""
    if from_landing:
        request.session["landing_rdv_form"] = _landing_rdv_form_snapshot(request)
        request.session["landing_rdv_alternatives"] = [
            a.strftime("%d/%m/%Y à %H:%M") for a in alternatives
        ]
        messages.error(request, error_msg)
        return redirect("landing")
    return render(
        request,
        "patients/patient_rdv_nouveau.html",
        {
            "error": error_msg,
            "alternatives": alternatives,
            "medecins": medecins,
            "form_data": request.POST,
            "date_min": timezone.localdate().isoformat(),
            "nav_active": "rdv",
        },
    )


def process_rdv_booking_post(
    request: HttpRequest,
    *,
    patient: Patient | None,
    redirect_success: str,
    success_message: str,
) -> HttpResponse:
    """
    Crée un rendez-vous « en attente » depuis le portail patient ou la landing (sans compte).
    `patient` doit être fourni pour un compte patient connecté ; sinon None (visiteur).
    """
    medecins = medecins_for_appointments()
    from_landing = request.POST.get("origin") == "landing"
    motif = (request.POST.get("motif") or "").strip()

    gn, email, tel = "", "", ""
    if patient is None:
        snap = _landing_rdv_form_snapshot(request)
        gn = snap["guest_nom_complet"]
        email = snap["guest_email"]
        tel = snap["guest_telephone"].replace(" ", "")
        guest_errs: list[str] = []
        if len(gn.strip()) < 3:
            guest_errs.append("Merci d’indiquer votre nom complet.")
        if "@" not in email or "." not in email.split("@")[-1]:
            guest_errs.append("Une adresse e-mail valide est requise.")
        if len(tel) < 6:
            guest_errs.append("Un numéro de téléphone valide est requis.")
        if guest_errs:
            if from_landing:
                request.session["landing_rdv_form"] = snap
                for e in guest_errs:
                    messages.error(request, e)
                return redirect("landing")
            for e in guest_errs:
                messages.error(request, e)
            return redirect("landing")

    try:
        mid = int(request.POST.get("medecin", "0"))
        d = request.POST.get("date")
        h = request.POST.get("heure", "09:00")
        med = get_object_or_404(Medecin, pk=mid)
        parts = h.split(":")
        hh, mm = int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
        day = datetime.date.fromisoformat(d or "2000-01-01")
        when = timezone.make_aware(
            datetime.datetime.combine(day, time(hh, mm)),
            timezone.get_current_timezone(),
        )
        if when <= timezone.now():
            return _respond_rdv_booking_error(
                request,
                error_msg=MSG_DATE_HEURE_PASSEE,
                alternatives=[],
                medecins=medecins,
                from_landing=from_landing,
            )
        conflit = RendezVous.objects.filter(
            medecin=med,
            date_heure=when,
            statut__in=["en_attente", "confirmé"],
        ).exists()
        if conflit:
            alt = suggest_available_slots(med, from_date=day, max_suggestions=8)
            return _respond_rdv_booking_error(
                request,
                error_msg=MSG_CRENEAU_PRIS,
                alternatives=alt,
                medecins=medecins,
                from_landing=from_landing,
            )
        with transaction.atomic():
            RendezVous.objects.create(
                patient=patient,
                medecin=med,
                date_heure=when,
                motif=motif,
                statut="en_attente",
                cree_par="visiteur" if patient is None else "patient",
                guest_nom_complet="" if patient else gn,
                guest_email="" if patient else email,
                guest_telephone="" if patient else tel,
            )
        from cabinet.notify import notify_all_secretaries

        dr_label = med.user.get_full_name() or med.user.last_name or med.user.username
        if patient is not None:
            who = patient.user.get_full_name() or patient.user.username
            notify_all_secretaries(
                f"Un patient a demandé un rendez-vous le {when.strftime('%d/%m/%Y %H:%M')} "
                f"avec Dr {dr_label}. (Patient : {who}.)"
            )
        else:
            notify_all_secretaries(
                f"Demande depuis le site : rendez-vous le {when.strftime('%d/%m/%Y %H:%M')} "
                f"avec Dr {dr_label}. Demandeur : {gn} — {email} — {tel}."
            )
        messages.success(request, success_message)
        return redirect(redirect_success)
    except (ValueError, OSError) as e:
        err = str(e) or "Données invalides."
        return _respond_rdv_booking_error(
            request,
            error_msg=err,
            alternatives=[],
            medecins=medecins,
            from_landing=from_landing,
        )


@require_POST
def landing_rdv_public_submit(request: HttpRequest) -> HttpResponse:
    """POST public depuis la landing (sans compte patient)."""
    if request.POST.get("origin") != "landing":
        messages.error(request, "Requête invalide.")
        return redirect("landing")
    if request.user.is_authenticated and getattr(request.user, "role", None) == "patient":
        messages.info(
            request,
            "Vous êtes connecté : le formulaire patient s’applique à votre compte.",
        )
        return redirect("landing")
    return process_rdv_booking_post(
        request,
        patient=None,
        redirect_success="landing",
        success_message=(
            "Votre demande a été enregistrée. Le secrétariat vous contactera pour confirmer le créneau."
        ),
    )


def _patient_or_redirect(request: HttpRequest) -> Patient | None:
    """Profil Patient (créé si manquant pour les comptes rôle patient)."""
    p = ensure_patient_for_user(request.user)
    if p is None:
        messages.error(request, "Cette page est réservée aux patients.")
    return p


@login_required
def patient_portal(request: HttpRequest) -> HttpResponse:
    if not is_patient(request.user):
        role = getattr(request.user, "role", None)
        if role == "doctor":
            return redirect("doctor_desk")
        if role == "secretary":
            return redirect("secretary_desk")
        return redirect("login")

    p = _patient_or_redirect(request)
    if p is None:
        return redirect("landing")
    last_score = (
        ScoreCardiovasculaire.objects.filter(patient=p).order_by("-date_calcul").first()
    )
    cab = StatutCabinet.get_solo()
    notifs = list(
        Notification.objects.filter(destinataire_patient=p, lu=False)[:20]
    )
    ctx = {
        "patient": p,
        "user": request.user,
        "last_score": last_score,
        "cabinet_statut": cab.statut,
        "notifications": notifs,
        "unread_count": Notification.objects.filter(
            destinataire_patient=p, lu=False
        ).count(),
        "nav_active": "dashboard",
    }
    return render(request, "accounts/patient_portal.html", ctx)


@login_required
def patient_profil(request: HttpRequest) -> HttpResponse:
    p = _patient_or_redirect(request)
    if p is None:
        return redirect("landing")
    u = request.user
    dob_max = timezone.localdate().isoformat()

    if request.method == "POST":
        first_name = (request.POST.get("first_name") or "").strip()
        last_name = (request.POST.get("last_name") or "").strip()
        email = (request.POST.get("email") or "").strip()
        telephone = (request.POST.get("telephone") or "").strip()
        adresse = (request.POST.get("adresse") or "").strip()
        dnais = (request.POST.get("date_naissance") or "").strip()
        groupe = (request.POST.get("groupe_sanguin") or "NS").strip()
        genre = (request.POST.get("genre") or "").strip()
        cin = (request.POST.get("cin") or "").strip()[:32]
        new_password1 = (request.POST.get("new_password1") or "").strip()
        new_password2 = (request.POST.get("new_password2") or "").strip()
        pwd_change_requested = bool(new_password1 or new_password2)

        errs: list[str] = []
        if not email:
            errs.append("L’e-mail est requis.")
        elif (
            User.objects.filter(email__iexact=email)
            .exclude(pk=u.pk)
            .exists()
        ):
            errs.append("Cet e-mail est déjà utilisé par un autre compte.")
        if not telephone:
            errs.append("Le téléphone est requis.")

        birth, derr = _validate_birth_date(dnais)
        if derr:
            errs.append(derr)

        valid_gs = {c[0] for c in Patient.GROUPE_SANGUIN}
        if groupe not in valid_gs:
            groupe = "NS"

        valid_genre = {c[0] for c in Patient.GENRE}
        if genre not in valid_genre:
            genre = ""

        pwd_changed = False
        if pwd_change_requested:
            from accounts.views_email import require_password_change_email_verified

            verify_err = require_password_change_email_verified(request, u)
            if verify_err:
                errs.append(verify_err)
            if not new_password1:
                errs.append("Saisissez le nouveau mot de passe.")
            elif new_password1 != new_password2:
                errs.append("Les deux saisies du nouveau mot de passe ne correspondent pas.")
            else:
                try:
                    validate_password(new_password1, u)
                except ValidationError as exc:
                    errs.extend(str(m) for m in exc.messages)

        form_values = {
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "telephone": telephone,
            "adresse": adresse,
            "date_naissance": dnais,
            "groupe_sanguin": groupe,
            "genre": genre,
            "cin": cin,
        }

        if errs:
            for e in errs:
                messages.error(request, e)
            return render(
                request,
                "accounts/patient_account.html",
                {
                    "patient": p,
                    "u": u,
                    "nav_active": "compte",
                    "form_values": form_values,
                    "groupe_choices": Patient.GROUPE_SANGUIN,
                    "genre_choices": Patient.GENRE,
                    "dob_max": dob_max,
                },
            )

        u.first_name = first_name
        u.last_name = last_name
        u.email = email

        if pwd_change_requested:
            u.set_password(new_password1)
            pwd_changed = True

        uploaded = request.FILES.get("avatar")
        if uploaded:
            if getattr(uploaded, "size", 0) > _AVATAR_MAX_BYTES:
                messages.error(request, "Image trop volumineuse (maximum 2 Mo).")
                return render(
                    request,
                    "accounts/patient_account.html",
                    {
                        "patient": p,
                        "u": u,
                        "nav_active": "compte",
                        "form_values": form_values,
                        "groupe_choices": Patient.GROUPE_SANGUIN,
                        "genre_choices": Patient.GENRE,
                        "dob_max": dob_max,
                    },
                )
            u.avatar = uploaded

        u.save()

        if pwd_changed:
            update_session_auth_hash(request, u)
            request.session.pop(f"pwd_change_verified:{u.pk}", None)

        p.telephone = telephone
        p.adresse = adresse
        p.date_naissance = birth
        p.groupe_sanguin = groupe
        p.genre = genre
        p.cin = cin
        p.save(
            update_fields=[
                "telephone",
                "adresse",
                "date_naissance",
                "groupe_sanguin",
                "genre",
                "cin",
            ]
        )
        if pwd_changed:
            messages.success(
                request,
                "Vos informations personnelles ont été enregistrées et votre mot de passe a été mis à jour.",
            )
        else:
            messages.success(request, "Vos informations personnelles ont été enregistrées.")
        return redirect("patient_profil")

    return render(
        request,
        "accounts/patient_account.html",
        {
            "patient": p,
            "u": u,
            "nav_active": "compte",
            "groupe_choices": Patient.GROUPE_SANGUIN,
            "genre_choices": Patient.GENRE,
            "dob_max": dob_max,
        },
    )


@login_required
def patient_rendez_vous(request: HttpRequest) -> HttpResponse:
    p = _patient_or_redirect(request)
    if p is None:
        return redirect("landing")
    rdvs = (
        RendezVous.objects.filter(patient=p)
        .select_related("medecin__user")
        .order_by("-date_heure")
    )
    return render(
        request, "patients/patient_rendez_vous.html", {"rdvs": rdvs, "patient": p, "nav_active": "rdv"}
    )


@login_required
def patient_rendez_vous_detail(request: HttpRequest, pk: int) -> HttpResponse:
    p = _patient_or_redirect(request)
    if p is None:
        return redirect("landing")
    rdv = get_object_or_404(
        RendezVous.objects.select_related("medecin__user"),
        pk=pk,
        patient=p,
    )
    doc_items = _items_documents_pour_rdv(rdv)
    back_url, back_label = _patient_page_back(request)
    return render(
        request,
        "patients/patient_rdv_detail.html",
        {
            "rdv": rdv,
            "patient": p,
            "doc_items": doc_items,
            "back_url": back_url,
            "back_label": back_label,
            "nav_active": "ordonnances"
            if (request.GET.get("from") or "").strip().lower() == "ordonnances"
            else "rdv",
        },
    )


@login_required
@ensure_csrf_cookie
def patient_rendez_vous_nouveau(request: HttpRequest) -> HttpResponse:
    p = _patient_or_redirect(request)
    if p is None:
        return redirect("landing")
    medecins = medecins_for_appointments()
    if request.method == "POST":
        return process_rdv_booking_post(
            request,
            patient=p,
            redirect_success="patient_space",
            success_message=(
                "Votre demande de rendez-vous a été enregistrée (en attente de confirmation)."
            ),
        )
    return render(
        request,
        "patients/patient_rdv_nouveau.html",
        {
            "medecins": medecins,
            "alternatives": [],
            "form_data": {},
            "date_min": timezone.localdate().isoformat(),
            "nav_active": "rdv",
        },
    )


@login_required
def patient_rendez_vous_annuler(request: HttpRequest, pk: int) -> HttpResponse:
    p = _patient_or_redirect(request)
    if p is None:
        return redirect("landing")
    rdv = get_object_or_404(RendezVous, pk=pk, patient=p)
    if rdv.statut in ("annulé", "terminé"):
        messages.warning(request, "Ce rendez-vous ne peut plus être modifié.")
        return redirect("patient_space")
    lim = timezone.now() + timedelta(hours=24)
    if rdv.date_heure <= lim:
        messages.error(request, MSG_ANNUL_24H)
        return redirect("patient_space")
    if request.method == "POST":
        rdv.statut = "annulé"
        rdv.save()
        from cabinet.notify import notify_all_secretaries

        notify_all_secretaries(
            f"Le patient {p.user.get_full_name() or p.user.username} a annulé un rendez-vous "
            f"le {rdv.date_heure.strftime('%d/%m/%Y %H:%M')}.",
            "rdv",
        )
        messages.success(request, "Rendez-vous annulé.")
        return redirect("patient_space")
    return render(
        request,
        "patients/patient_rdv_confirmer_annuler.html",
        {"rdv": rdv, "nav_active": "rdv"},
    )


def _medecin_nom_affiche(medecin: Medecin) -> str:
    u = medecin.user
    return (u.get_full_name() or u.username or "Médecin").strip()


def _items_documents_pour_rdv(rdv: RendezVous) -> list[dict]:
    """Liste unifiée des pièces PDF liées à un rendez-vous."""
    items: list[dict] = []
    for o in (
        Ordonnance.objects.filter(rendez_vous=rdv)
        .prefetch_related("medicaments")
        .order_by("-date_creation")
    ):
        n_med = o.medicaments.count()
        items.append(
            {
                "label": "Ordonnance médicamenteuse",
                "hint": f"{n_med} médicament{'s' if n_med != 1 else ''}",
                "date": o.date_creation,
                "download_name": "telecharger_ordonnance",
                "pk": o.pk,
            }
        )
    for d in DocumentMedical.objects.filter(rendez_vous=rdv).order_by(
        "-date_creation"
    ):
        items.append(
            {
                "label": d.titre_court(),
                "hint": "",
                "date": d.date_creation,
                "download_name": "telecharger_document_medical",
                "pk": d.pk,
            }
        )
    items.sort(key=lambda x: x["date"], reverse=True)
    return items


def _items_documents_sans_rdv(patient: Patient) -> list[dict]:
    """Ordonnances / documents créés sans rendez-vous lié (affichage dossier dédié)."""
    items: list[dict] = []
    for o in (
        Ordonnance.objects.filter(patient=patient, rendez_vous__isnull=True)
        .select_related("medecin__user")
        .prefetch_related("medicaments")
        .order_by("-date_creation")
    ):
        n_med = o.medicaments.count()
        items.append(
            {
                "label": "Ordonnance médicamenteuse",
                "hint": f"{n_med} médicament{'s' if n_med != 1 else ''}",
                "date": o.date_creation,
                "download_name": "telecharger_ordonnance",
                "pk": o.pk,
            }
        )
    for d in (
        DocumentMedical.objects.filter(patient=patient, rendez_vous__isnull=True)
        .select_related("medecin__user")
        .order_by("-date_creation")
    ):
        items.append(
            {
                "label": d.titre_court(),
                "hint": "",
                "date": d.date_creation,
                "download_name": "telecharger_document_medical",
                "pk": d.pk,
            }
        )
    items.sort(key=lambda x: x["date"], reverse=True)
    return items


def _build_dossiers_medicaux_patient(patient: Patient) -> list[dict]:
    """Un dossier par rendez-vous du patient (+ documents non liés à un RDV)."""
    rdvs = RendezVous.objects.filter(patient=patient).select_related(
        "medecin__user"
    ).order_by("-date_heure")

    dossiers: list[dict] = []
    for rdv in rdvs:
        items = _items_documents_pour_rdv(rdv)
        med_label = _medecin_nom_affiche(rdv.medecin)
        total = len(items)
        if total == 0:
            doc_part = "Aucun document"
        else:
            doc_part = f"{total} document{'s' if total > 1 else ''}"
        dossiers.append(
            {
                "rdv_pk": rdv.pk,
                "label": rdv.date_heure.strftime("Rendez-vous du %d/%m/%Y à %H:%M"),
                "subtitle": f"Dr {med_label} · {rdv.get_statut_display()} · {doc_part}",
                "items": items,
                "total": total,
                "sort_key": rdv.date_heure,
            }
        )

    hors_rdv = _items_documents_sans_rdv(patient)
    if hors_rdv:
        n = len(hors_rdv)
        dossiers.append(
            {
                "rdv_pk": None,
                "label": "Documents sans rendez-vous lié",
                "subtitle": (
                    f"{n} document{'s' if n > 1 else ''} — "
                    "non rattachés à une date de consultation"
                ),
                "items": hors_rdv,
                "total": n,
                "sort_key": hors_rdv[0]["date"],
            }
        )

    return dossiers


@login_required
def patient_ordonnances(request: HttpRequest) -> HttpResponse:
    p = _patient_or_redirect(request)
    if p is None:
        return redirect("landing")
    dossiers = _build_dossiers_medicaux_patient(p)
    return render(
        request,
        "patients/patient_ordonnances.html",
        {
            "dossiers": dossiers,
            "patient": p,
            "nav_active": "ordonnances",
        },
    )


@login_required
def telecharger_ordonnance(request: HttpRequest, pk: int) -> HttpResponse:
    p = _patient_or_redirect(request)
    if p is None:
        return redirect("landing")
    ordonnance = get_object_or_404(
        Ordonnance.objects.select_related("patient__user", "medecin__user").prefetch_related(
            "medicaments"
        ),
        pk=pk,
        patient=p,
    )
    try:
        data = build_ordonnance_pdf(ordonnance)
    except Exception:
        messages.error(
            request,
            "Impossible de générer le PDF de cette ordonnance. Réessayez ou contactez le cabinet.",
        )
        return redirect("patient_ordonnances")
    buffer = BytesIO(data)
    buffer.seek(0)
    resp = FileResponse(
        buffer, as_attachment=True, filename=f"ordonnance_{pk}.pdf"
    )
    resp["Content-Type"] = "application/pdf"
    return resp


@login_required
def telecharger_document_medical(request: HttpRequest, pk: int) -> HttpResponse:
    p = _patient_or_redirect(request)
    if p is None:
        return redirect("landing")
    document = get_object_or_404(
        DocumentMedical.objects.select_related("patient__user", "medecin__user"),
        pk=pk,
        patient=p,
    )
    try:
        data = build_document_medical_pdf(document)
    except Exception:
        messages.error(
            request,
            "Impossible de générer le PDF de ce document. Réessayez ou contactez le cabinet.",
        )
        return redirect("patient_ordonnances")
    buffer = BytesIO(data)
    buffer.seek(0)
    slug = {
        DocumentMedical.KIND_BILAN: "bilan_biologique",
        DocumentMedical.KIND_EXAMENS: "demande_examens",
        DocumentMedical.KIND_CERTIFICAT: "certificat",
    }.get(document.kind, "document")
    resp = FileResponse(
        buffer, as_attachment=True, filename=f"{slug}_{pk}.pdf"
    )
    resp["Content-Type"] = "application/pdf"
    return resp
