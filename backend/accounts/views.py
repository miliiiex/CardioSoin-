import calendar
import datetime
import re
from typing import Optional, Tuple
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import (
    authenticate,
    get_user_model,
    login,
    logout,
    update_session_auth_hash,
)
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpRequest, HttpResponse
from django.db import IntegrityError
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie
from django.templatetags.static import static

from appointments.models import RendezVous
from cabinet.models import StatutCabinet
from patients.models import Patient
from patients.patient_utils import ensure_patient_for_user
from prescriptions.models import Ordonnance

from .medecin_utils import ensure_medecin_for_single_user, medecins_for_appointments
from .permissions import is_doctor, is_doctor_or_secretary
from .secretary_utils import ensure_secretaire_for_single_user

User = get_user_model()

_STAFF_AVATAR_MAX_BYTES = 2 * 1024 * 1024


def csrf_failure(request, reason=""):
    """
    Page claire si le jeton CSRF est périmé (onglet laissé ouvert, autre connexion, etc.).
    """
    msg = (
        "Le formulaire a expiré. Rechargez la page (touche F5), "
        "puis renvoyez le formulaire."
    )
    path = (request.path or "").lower()
    today = timezone.localdate()
    if "connexion-personnel" in path:
        return render(
            request,
            "accounts/staff_login.html",
            {"error": msg},
            status=403,
        )
    if "/login" in path:
        return render(
            request,
            "accounts/login.html",
            {
                "error": msg,
                "reg_error": None,
                "reg_info": None,
                "open_register": False,
                "register_verify_step": False,
                "pending_reg_email": "",
                "reg_date_max": today.isoformat(),
                "reg_date_min": "1900-01-01",
            },
            status=403,
        )
    return render(
        request,
        "accounts/csrf_failure.html",
        {"message": msg, "reason": reason},
        status=403,
    )


def _patient_safe_redirect(request, fallback: str):
    """Redirige vers `next` si l’URL est sûre (ex. après login depuis « Prendre rendez-vous »)."""
    next_url = (request.POST.get("next") or request.GET.get("next") or "").strip()
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(next_url)
    return redirect(fallback)


def _login_with_backend(request, user):
    """
    Avec plusieurs AUTHENTICATION_BACKENDS, login() exige le backend
    (attribut `user.backend` ou argument explicite). `authenticate` pose
    `user.backend` ; l’inscription par create_user() ne le fait pas.
    """
    backend = getattr(user, "backend", None)
    if not backend:
        backend = settings.AUTHENTICATION_BACKENDS[0]
    login(request, user, backend=backend)


def _resolve_login_user(request, ident: str, password: str):
    """
    Tente d’obtenir un utilisateur valide (mot de passe correct).
    S’appuie sur EmailOrUsernameBackend, avec filets sûrs (plusieurs e-mails, etc.).
    """
    if not ident or not password:
        return None
    ident = ident.strip()
    user = authenticate(request, username=ident, password=password)
    if user is not None:
        return user

    by_email = User.objects.filter(email__iexact=ident)
    n = by_email.count()
    if n == 1:
        u = by_email.first()
        return authenticate(request, username=u.username, password=password) if u else None
    if n > 1:
        return None

    by_username = User.objects.filter(username__iexact=ident)
    if by_username.count() == 1:
        u = by_username.first()
        return authenticate(request, username=u.username, password=password) if u else None
    return None


def _validate_birth_date(dnais: str) -> Tuple[Optional[datetime.date], Optional[str]]:
    s = (dnais or "").strip()
    if not s:
        return None, "La date de naissance est requise."
    parts = s.split("-")
    if len(parts) != 3:
        return None, "Utilisez le format AAAA-MM-JJ."
    y_s, m_s, d_s = parts[0], parts[1], parts[2]
    if len(y_s) != 4 or not y_s.isdigit():
        return None, "L'année doit comporter 4 chiffres."
    if not m_s.isdigit() or not d_s.isdigit():
        return None, "Mois et jour invalides."
    y, m, d = int(y_s), int(m_s), int(d_s)
    if not (1000 <= y <= 9999):
        return None, "L'année doit être comprise entre 1000 et 9999."
    if not (1 <= m <= 12):
        return None, "Le mois doit être compris entre 1 et 12."
    max_day = calendar.monthrange(y, m)[1]
    if not (1 <= d <= max_day):
        return None, (
            f"Le jour doit être valide pour ce mois : entre 1 et {max_day} "
            f"({m:02d}/{y}), pas {d}."
        )
    try:
        birth = datetime.date(y, m, d)
    except ValueError:
        return None, "Cette date n'existe pas."
    today = timezone.localdate()
    if birth > today:
        return None, "La date de naissance ne peut pas être postérieure à aujourd'hui."
    return birth, None


def _clean_expertise_line(raw: str) -> str:
    return re.sub(r"^[\s\-•●·]+", "", (raw or "").strip())


def _split_medecin_bio(bio: str) -> Tuple[str, list[str]]:
    """
    Décompose une biographie facultative pour la grille « équipe » sur la landing.
    Intro = texte avant un séparateur ; lignes suivantes = expertises sans puces dans le template.
      - séparateur explicite : ligne contenant uniquement « --- »
      - ou premier double saut de ligne (\\n\\n) : bloc suivant = une ligne d'expertise par ligne.
    """
    bio = (bio or "").strip()
    if not bio:
        return "", []

    sep_dash = re.compile(r"(?m)^\s*---\s*$")
    if sep_dash.search(bio):
        head, tail = sep_dash.split(bio, maxsplit=1)
        intro = head.strip()
        lines = [_clean_expertise_line(ln) for ln in tail.splitlines()]
        expertise = [ln for ln in lines if ln]
        return intro, expertise

    if "\n\n" in bio:
        head, tail = bio.split("\n\n", 1)
        intro = head.strip()
        lines = [_clean_expertise_line(ln) for ln in tail.splitlines()]
        expertise = [ln for ln in lines if ln]
        return intro, expertise

    return bio, []


_LANDING_VITRINE_TARIK: dict[str, str | list[str]] = {
    "badge": "CARDIOLOGUE INTERVENTIONNEL",
    "subtitle": "Cardiologue — Spécialiste en cardiologie interventionnelle",
    "intro": (
        "Fort d'une expertise reconnue en cardiologie interventionnelle, le Dr. Bentahir prend en charge "
        "les pathologies coronariennes complexes. Formé dans les centres universitaires de référence, "
        "il allie technicité de pointe et écoute attentive pour offrir à chaque patient une prise "
        "en charge personnalisée et sécurisée."
    ),
    "expertise": [
        "Coronarographie et angioplastie",
        "Insuffisance cardiaque",
        "Syndromes coronariens aigus",
        "Pose de stents et dispositifs intra-vasculaires",
    ],
}

_LANDING_VITRINE_SALMA: dict[str, str | list[str]] = {
    "badge": "CARDIOLOGIE RYTHMOLOGIQUE",
    "subtitle": "Cardiologue — Spécialiste en rythmologie et imagerie cardiaque",
    "intro": (
        "Le Dr. Yaaqoub se consacre avec passion à l'exploration des troubles du rythme cardiaque et à "
        "l'imagerie cardiovasculaire avancée. Grâce à une approche rigoureuse et empathique, elle "
        "assure un suivi global et préventif, particulièrement auprès des patients porteurs de troubles "
        "du rythme ou d'anomalies structurelles cardiaques."
    ),
    "expertise": [
        "Troubles du rythme et de la conduction",
        "Holter ECG et explorations électrophysiologiques",
        "Échocardiographie et imagerie avancée",
        "Cardiologie préventive et suivi chronique",
    ],
}


def _landing_demo_vitrine(user) -> dict[str, str | list[str]] | None:
    """Textes officiels carte landing (migrations 0004 / 0005) pour les comptes démo."""
    fn = (user.first_name or "").strip().lower()
    ln = (user.last_name or "").strip().lower()
    if (fn == "tarik" and ln == "bentahir") or (fn == "karim" and ln == "benali"):
        return _LANDING_VITRINE_TARIK
    if fn == "salma" and ln in ("yaaqoub", "yaakoub"):
        return _LANDING_VITRINE_SALMA
    return None


def _landing_team_demo_photo_url(user) -> str | None:
    """
    Photo vitrine landing : avatar uploadé prioritaire, sinon JPG statiques
    `tarik.jpg` / `salma.jpg` à la racine de STATICFILES_DIRS (ex. pfa project/static/).
    """
    if getattr(user, "avatar", None) and user.avatar:
        return user.avatar.url
    fn = (user.first_name or "").strip().lower()
    ln = (user.last_name or "").strip().lower()
    static_name: str | None = None
    if (fn == "tarik" and ln == "bentahir") or (fn == "karim" and ln == "benali"):
        static_name = "tarik.jpg"
    elif fn == "salma" and ln in ("yaaqoub", "yaakoub"):
        static_name = "salma.jpg"
    if static_name:
        return static(static_name)
    return None


def _landing_team_medecins(medecins_qs):
    """
    Grille « équipe » sur la landing : au plus 2 médecins, ordre fixe
    Dr Tarik Bentahir puis Dr Salma Yaaqoub (si présents en base).
    Les autres médecins restent disponibles pour la réservation (liste séparée).
    """
    rows = list(medecins_qs)

    def _find(fn: str, ln: str):
        fn_l, ln_l = fn.lower(), ln.lower()
        for m in rows:
            u = m.user
            ufn = (u.first_name or "").strip().lower()
            uln = (u.last_name or "").strip().lower()
            if ufn == fn_l and uln == ln_l:
                return m
        return None

    out = []
    t = _find("tarik", "bentahir")
    if t:
        out.append(t)
    s = _find("salma", "yaaqoub") or _find("salma", "yaakoub")
    if s:
        out.append(s)
    return out


def _landing_medecin_cards(queryset):
    """Données prêtes pour le template grille médecins (initiales, intro, lignes expertise)."""
    cards = []
    for m in queryset:
        user = m.user
        if user.first_name and user.last_name:
            initials = f"{user.first_name[0]}{user.last_name[0]}".upper()
        elif user.first_name:
            initials = user.first_name[:2].upper()
        elif user.last_name:
            initials = user.last_name[:2].upper()
        else:
            initials = (user.username[:2] or "DR").upper()

        intro, expertise = _split_medecin_bio(m.bio)
        default_intro = (
            "Consultations cardiologiques, suivi attentif et coordination des soins "
            "au sein du cabinet CardioSoin."
        )
        if not intro.strip():
            intro = default_intro

        badge_raw = (m.specialite or "Cardiologie").strip().upper()
        subtitle_raw = (m.qualification_display or m.specialite or "Cardiologie").strip()

        demo = _landing_demo_vitrine(user)
        if demo:
            spec_l = (m.specialite or "").strip().lower()
            qual_ok = bool((m.qualification_display or "").strip())
            weak_body = (
                not m.bio.strip()
                or not expertise
                or intro.strip() == default_intro.strip()
            )
            if weak_body:
                intro = str(demo["intro"])
                expertise = list(demo["expertise"])  # type: ignore[arg-type]
            if not qual_ok or spec_l in ("", "cardiologie"):
                subtitle_raw = str(demo["subtitle"])
            if spec_l in ("", "cardiologie"):
                badge_raw = str(demo["badge"])

        cards.append(
            {
                "medecin": m,
                "initials": initials,
                "photo_url": _landing_team_demo_photo_url(user),
                "nom_affiche": user.get_full_name() or user.username,
                "subtitle": subtitle_raw,
                "badge": badge_raw[:72] + ("…" if len(badge_raw) > 72 else ""),
                "intro": intro,
                "expertise_lines": expertise,
            }
        )
    return cards


@ensure_csrf_cookie
def landing(request):
    landing_rdv_auto_open = (
        "landing_rdv_form" in request.session
        or "landing_rdv_alternatives" in request.session
    )
    landing_rdv_form = request.session.pop("landing_rdv_form", {})
    landing_rdv_alt = request.session.pop("landing_rdv_alternatives", [])
    if landing_rdv_form.get("medecin") is not None:
        landing_rdv_form["medecin"] = str(landing_rdv_form["medecin"]).strip()
    landing_date_min = timezone.localdate().isoformat()
    landing_rdv_medecins = medecins_for_appointments()
    landing_medecins_cards = _landing_medecin_cards(_landing_team_medecins(landing_rdv_medecins))

    return render(
        request,
        "accounts/landing.html",
        {
            "landing_rdv_medecins": landing_rdv_medecins,
            "landing_medecins_cards": landing_medecins_cards,
            "landing_date_min": landing_date_min,
            "landing_rdv_form": landing_rdv_form,
            "landing_rdv_alt": landing_rdv_alt,
            "landing_rdv_auto_open": landing_rdv_auto_open,
        },
    )

@never_cache
@ensure_csrf_cookie
def staff_login(request):
    """Connexion dédiée médecins / secrétaires (décorateurs `login_url='staff_login'`)."""
    if request.user.is_authenticated:
        role = getattr(request.user, "role", None)
        if role == "doctor":
            return redirect("doctor_desk")
        if role == "secretary":
            return redirect("secretary_desk")
        if role == "patient":
            return redirect("patient_space")
        return redirect("landing")

    error = None
    if request.method == "POST":
        ident = (request.POST.get("email") or request.POST.get("username") or "").strip()
        password = request.POST.get("password") or ""
        if not ident or not password:
            error = "E-mail et mot de passe requis."
        else:
            user = _resolve_login_user(request, ident, password)
            if user is not None and user.is_active:
                role = getattr(user, "role", None)
                if role not in ("doctor", "secretary"):
                    error = "Ce compte n'est pas un compte personnel du cabinet (médecin ou secrétaire)."
                else:
                    _login_with_backend(request, user)
                    messages.success(request, "Bienvenue.")
                    if role == "doctor":
                        return redirect("doctor_desk")
                    return redirect("secretary_desk")
            elif user is not None and not user.is_active:
                error = "Ce compte est désactivé. Contactez l’administrateur."
            else:
                error = "Identifiant ou mot de passe incorrect."
    return render(
        request,
        "accounts/staff_login.html",
        {
            "error": error,
        },
    )


@never_cache
@ensure_csrf_cookie
def login_view(request):
    # 🔁 si déjà connecté
    if request.user.is_authenticated:
        role = getattr(request.user, "role", None)
        if role == "patient":
            return _patient_safe_redirect(request, "patient_space")
        if role == "doctor":
            return redirect("doctor_desk")
        if role == "secretary":
            return redirect("secretary_desk")
        return redirect("landing")

    error = None
    reg_error = None
    reg_info = None

    if request.method == "POST":
        action = request.POST.get("action", "login")

        # =========================
        # 🔐 LOGIN
        # =========================
        if action in ("login", ""):
            ident = (request.POST.get("email") or request.POST.get("username") or "").strip()
            password = request.POST.get("password") or ""

            if not ident or not password:
                error = "E-mail (ou identifiant) et mot de passe requis."
            else:
                user = _resolve_login_user(request, ident, password)

                if user is not None and user.is_active:
                    role = getattr(user, "role", None)
                    # Cette page est l’espace patient : on ne connecte que les comptes patients.
                    if role == "patient":
                        _login_with_backend(request, user)
                        messages.success(request, "Bienvenue.")
                        return _patient_safe_redirect(request, "patient_space")
                    if role in ("doctor", "secretary"):
                        error = (
                            "Les comptes du cabinet (médecin / secrétariat) se connectent via "
                            "« Connexion personnel » sur la page d’accueil, pas depuis l’espace patient."
                        )
                    else:
                        error = "Ce compte ne peut pas accéder à l’espace patient."
                elif user is not None and not user.is_active:
                    error = "Ce compte est désactivé."
                else:
                    error = "Identifiant ou mot de passe incorrect."

        # =========================
        # 📝 INSCRIPTION (données → code e-mail → compte)
        # =========================
        elif action == "register_confirm":
            from accounts.email_verification import (
                PURPOSE_REGISTER,
                clear_email_verification_session,
                verify_submitted_code,
            )
            from accounts.registration_pending import (
                clear_pending_registration,
                get_pending_registration,
            )

            pending = get_pending_registration(request)
            if not pending:
                reg_error = "Session expirée. Remplissez à nouveau le formulaire d'inscription."
            else:
                code = (request.POST.get("reg_code") or "").strip()
                email = pending.get("email") or ""
                ok, msg = verify_submitted_code(
                    email=email, code=code, purpose=PURPOSE_REGISTER
                )
                if not ok:
                    reg_error = msg
                else:
                    birth_iso = pending.get("date_naissance") or ""
                    birth, date_err = _validate_birth_date(birth_iso)
                    if date_err:
                        reg_error = date_err
                        clear_pending_registration(request)
                    else:
                        try:
                            user = User.objects.create_user(
                                username=pending["username"],
                                email=email,
                                password=pending["password"],
                                role="patient",
                                first_name=pending.get("first_name") or "",
                                last_name=pending.get("last_name") or "",
                            )
                        except IntegrityError:
                            reg_error = (
                                "Ce nom d'utilisateur ou cet e-mail existe déjà. "
                                "Recommencez l'inscription."
                            )
                            clear_pending_registration(request)
                        else:
                            p = user.profil_patient
                            p.date_naissance = birth
                            p.telephone = pending.get("telephone") or ""
                            p.adresse = pending.get("adresse") or ""
                            p.save()
                            clear_email_verification_session(
                                request, PURPOSE_REGISTER, email
                            )
                            clear_pending_registration(request)
                            _login_with_backend(request, user)
                            messages.success(
                                request,
                                "Compte créé. Bienvenue dans votre espace patient.",
                            )
                            return _patient_safe_redirect(request, "patient_space")

        elif action == "register_resend":
            from accounts.email_verification import (
                PURPOSE_REGISTER,
                send_verification_code,
            )
            from accounts.registration_pending import get_pending_registration

            pending = get_pending_registration(request)
            if not pending:
                reg_error = "Session expirée. Recommencez l'inscription."
            else:
                ok, msg = send_verification_code(
                    email=pending["email"], purpose=PURPOSE_REGISTER
                )
                if ok:
                    reg_info = msg
                else:
                    reg_error = msg

        elif action == "register_cancel":
            from accounts.registration_pending import clear_pending_registration

            clear_pending_registration(request)
            return redirect("login?inscription=1")

        elif action == "register":
            from accounts.email_validation import validate_recipient_email
            from accounts.email_verification import (
                PURPOSE_REGISTER,
                send_verification_code,
            )
            from accounts.registration_pending import save_pending_registration

            username = (request.POST.get("reg_username") or "").strip()
            email_raw = (request.POST.get("reg_email") or "").strip()
            password = request.POST.get("reg_password") or ""
            password2 = request.POST.get("reg_password2") or ""
            first_name = (request.POST.get("reg_first_name") or "").strip()
            last_name = (request.POST.get("reg_last_name") or "").strip()
            dnais = (request.POST.get("reg_date_naissance") or "").strip()
            tel = (request.POST.get("reg_telephone") or "").strip()
            adresse = (request.POST.get("reg_adresse") or "").strip()

            ok_email, err_email, email = validate_recipient_email(email_raw)
            if not username or not password:
                reg_error = "Nom d'utilisateur et mot de passe requis."
            elif not ok_email:
                reg_error = err_email
            elif password != password2:
                reg_error = "Les mots de passe ne correspondent pas."
            elif len(password) < 6:
                reg_error = "Le mot de passe doit contenir au moins 6 caractères."
            elif not dnais or not tel:
                reg_error = "Date de naissance et téléphone requis."
            elif User.objects.filter(username__iexact=username).exists():
                reg_error = "Ce nom d'utilisateur existe déjà."
            elif User.objects.filter(email__iexact=email).exists():
                reg_error = "Cet e-mail est déjà associé à un compte."
            else:
                birth, date_err = _validate_birth_date(dnais)
                if date_err:
                    reg_error = date_err
                else:
                    sent, send_msg = send_verification_code(
                        email=email, purpose=PURPOSE_REGISTER
                    )
                    if not sent:
                        reg_error = send_msg
                    else:
                        save_pending_registration(
                            request,
                            {
                                "username": username,
                                "email": email,
                                "password": password,
                                "first_name": first_name,
                                "last_name": last_name,
                                "date_naissance": birth.isoformat(),
                                "telephone": tel,
                                "adresse": adresse,
                            },
                        )
                        reg_info = send_msg

    today = timezone.localdate()

    from accounts.registration_pending import get_pending_registration

    pending_reg = get_pending_registration(request)
    register_verify_step = pending_reg is not None

    open_register = bool(reg_error) or bool(reg_info) or register_verify_step or (
        request.method == "GET" and (request.GET.get("inscription") == "1")
    )
    return render(
        request,
        "accounts/login.html",
        {
            "error": error,
            "reg_error": reg_error,
            "reg_info": reg_info,
            "open_register": open_register,
            "register_verify_step": register_verify_step,
            "pending_reg_email": (pending_reg or {}).get("email", ""),
            "reg_date_max": today.isoformat(),
            "reg_date_min": "1900-01-01",
        },
    )

@login_required(login_url="login")
def patient_space(request):
    if getattr(request.user, "role", None) != "patient":
        messages.info(request, "Espace réservé aux patients.")
        return redirect("landing")
    u = request.user
    if getattr(u, "role", None) == "patient":
        ensure_patient_for_user(u)
    try:
        profil = u.profil_patient
    except Patient.DoesNotExist:
        profil = None

    rdvs = RendezVous.objects.none()
    ordonnances = Ordonnance.objects.none()
    rdv_date_marks: list[str] = []
    next_rdv = None

    if profil is not None:
        rdvs = (
            RendezVous.objects.filter(patient=profil)
            .exclude(statut="annulé")
            .select_related("medecin__user")
            .order_by("date_heure")
        )
        rdv_date_marks = sorted({r.date_heure.date().isoformat() for r in rdvs})
        next_rdv = (
            rdvs.filter(date_heure__gte=timezone.now()).order_by("date_heure").first()
        )
        ordonnances = (
            Ordonnance.objects.filter(patient=profil)
            .select_related("medecin__user")
            .order_by("-date_creation")[:24]
        )

    cab = StatutCabinet.get_solo()

    return render(
        request,
        "accounts/patient_dashboard.html",
        {
            "u": u,
            "profil": profil,
            "rdvs": rdvs,
            "rdv_date_marks": rdv_date_marks,
            "next_rdv": next_rdv,
            "ordonnances": ordonnances,
            "nav_active": "dashboard",
            "cabinet_statut": cab.statut,
        },
    )


def logout_view(request):
    logout(request)
    messages.info(request, "Vous avez été déconnecté(e).")
    return redirect("landing")


def doctor_dashboard(request):
    return render(request, "accounts/doctor_dashboard.html")


def secretary_dashboard(request):
    return render(request, "accounts/secretary_dashboard.html")


@login_required(login_url="staff_login")
@user_passes_test(is_doctor_or_secretary)
@ensure_csrf_cookie
def staff_profil(request: HttpRequest) -> HttpResponse:
    user = request.user
    med = ensure_medecin_for_single_user(user)
    sec = ensure_secretaire_for_single_user(user)
    role_label = "Médecin" if med else "Secrétariat"

    if request.method == "POST":
        first_name = (request.POST.get("first_name") or "").strip()[:150]
        last_name = (request.POST.get("last_name") or "").strip()[:150]
        email = (request.POST.get("email") or "").strip()[:254]
        cin = (request.POST.get("cin") or "").strip()[:32]
        telephone = (request.POST.get("telephone") or "").strip()[:20]
        specialite = (request.POST.get("specialite") or "").strip()[:200]
        numero_ordre = (request.POST.get("numero_ordre") or "").strip()[:50]
        bio = (request.POST.get("bio") or "").strip()[:2000]
        new_password1 = (request.POST.get("new_password1") or "").strip()
        new_password2 = (request.POST.get("new_password2") or "").strip()
        pwd_change_requested = bool(new_password1 or new_password2)

        errs: list[str] = []
        if email and User.objects.filter(email__iexact=email).exclude(pk=user.pk).exists():
            errs.append("Cet e-mail est déjà utilisé par un autre compte.")

        uploaded = request.FILES.get("avatar")
        if uploaded and getattr(uploaded, "size", 0) > _STAFF_AVATAR_MAX_BYTES:
            errs.append("Image trop volumineuse (maximum 2 Mo).")
            uploaded = None

        pwd_changed = False
        if pwd_change_requested:
            from accounts.views_email import require_password_change_email_verified

            verify_err = require_password_change_email_verified(request, user)
            if verify_err:
                errs.append(verify_err)
            if not new_password1:
                errs.append("Saisissez le nouveau mot de passe.")
            elif new_password1 != new_password2:
                errs.append(
                    "Les deux saisies du nouveau mot de passe ne correspondent pas."
                )
            else:
                try:
                    validate_password(new_password1, user)
                except ValidationError as exc:
                    errs.extend(str(m) for m in exc.messages)

        form_sticky = {
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "cin": cin,
            "telephone": telephone,
            "specialite": specialite,
            "numero_ordre": numero_ordre,
            "bio": bio,
        }

        if errs:
            for e in errs:
                messages.error(request, e)
            ctx = {
                "med": med,
                "sec": sec,
                "role_label": role_label,
                "form_sticky": form_sticky,
            }
            tpl_err = (
                "cabinet/staff_profil_doctor.html"
                if is_doctor(user)
                else "cabinet/staff_profil_secretary.html"
            )
            return render(request, tpl_err, ctx)

        user.first_name = first_name
        user.last_name = last_name
        if email:
            user.email = email

        if pwd_change_requested:
            user.set_password(new_password1)
            pwd_changed = True

        if uploaded:
            user.avatar = uploaded

        user.save()
        if pwd_changed:
            update_session_auth_hash(request, user)
            request.session.pop(f"pwd_change_verified:{user.pk}", None)

        if med:
            med.telephone = (request.POST.get("telephone") or "").strip()[:20]
            med.specialite = (request.POST.get("specialite") or "Cardiologie").strip()[:200]
            med.numero_ordre = (request.POST.get("numero_ordre") or "").strip()[:50]
            med.bio = (request.POST.get("bio") or "").strip()[:2000]
            med.cin = cin
            med.save()
        if sec:
            sec.telephone = telephone
            sec.cin = cin
            sec.save()

        messages.success(request, "Profil enregistré.")
        return redirect("staff_profil")
    tpl = (
        "cabinet/staff_profil_doctor.html"
        if is_doctor(user)
        else "cabinet/staff_profil_secretary.html"
    )
    return render(
        request,
        tpl,
        {
            "med": med,
            "sec": sec,
            "role_label": role_label,
        },
    )
