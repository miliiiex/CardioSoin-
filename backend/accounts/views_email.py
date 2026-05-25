"""
Vérification e-mail : mot de passe oublié, envoi / confirmation de codes.
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from accounts.email_validation import validate_recipient_email
from accounts.email_verification import (
    PURPOSE_CHANGE_PASSWORD,
    PURPOSE_REGISTER,
    PURPOSE_RESET_PASSWORD,
    clear_email_verification_session,
    is_email_verified_in_session,
    is_password_change_verified_in_session,
    mark_email_verified_in_session,
    mark_password_change_verified,
    send_verification_code,
    verify_submitted_code,
)
from accounts.models import User

SESSION_RESET_EMAIL = "pwd_reset_email"


@never_cache
@ensure_csrf_cookie
def password_forgot(request: HttpRequest) -> HttpResponse:
    """Réinitialisation du mot de passe en 3 étapes (e-mail → code → nouveau MDP)."""
    step = request.session.get("pwd_reset_step", "email")
    email = (request.session.get(SESSION_RESET_EMAIL) or "").strip()

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()

        if action == "send_code":
            email_in = (request.POST.get("email") or "").strip()
            ok, msg = send_verification_code(
                email=email_in, purpose=PURPOSE_RESET_PASSWORD
            )
            if ok:
                request.session[SESSION_RESET_EMAIL] = email_in.lower()
                request.session["pwd_reset_step"] = "code"
                request.session.modified = True
                messages.success(request, msg)
                return redirect("password_forgot")
            messages.error(request, msg)

        elif action == "verify_code":
            email_in = (request.session.get(SESSION_RESET_EMAIL) or "").strip()
            code = (request.POST.get("code") or "").strip()
            ok, msg = verify_submitted_code(
                email=email_in, code=code, purpose=PURPOSE_RESET_PASSWORD
            )
            if ok:
                mark_email_verified_in_session(
                    request, PURPOSE_RESET_PASSWORD, email_in
                )
                request.session["pwd_reset_step"] = "password"
                request.session.modified = True
                messages.success(request, msg)
                return redirect("password_forgot")
            messages.error(request, msg)

        elif action == "reset_password":
            email_in = (request.session.get(SESSION_RESET_EMAIL) or "").strip()
            if not is_email_verified_in_session(
                request, PURPOSE_RESET_PASSWORD, email_in
            ):
                messages.error(
                    request, "Vérifiez d'abord votre e-mail avec le code reçu."
                )
                request.session["pwd_reset_step"] = "code"
                return redirect("password_forgot")

            pwd1 = request.POST.get("new_password1") or ""
            pwd2 = request.POST.get("new_password2") or ""
            if len(pwd1) < 6:
                messages.error(
                    request, "Le mot de passe doit contenir au moins 6 caractères."
                )
            elif pwd1 != pwd2:
                messages.error(request, "Les mots de passe ne correspondent pas.")
            else:
                user = User.objects.filter(email__iexact=email_in).first()
                if not user:
                    messages.error(request, "Compte introuvable.")
                else:
                    user.set_password(pwd1)
                    user.save(update_fields=["password"])
                    for key in (
                        SESSION_RESET_EMAIL,
                        "pwd_reset_step",
                    ):
                        request.session.pop(key, None)
                    clear_email_verification_session(
                        request, PURPOSE_RESET_PASSWORD, email_in
                    )
                    messages.success(
                        request,
                        "Mot de passe mis à jour. Vous pouvez vous connecter.",
                    )
                    if user.role == "patient":
                        return redirect("login")
                    return redirect("staff_login")

        elif action == "restart":
            for key in (SESSION_RESET_EMAIL, "pwd_reset_step"):
                request.session.pop(key, None)
            request.session.modified = True
            return redirect("password_forgot")

    step = request.session.get("pwd_reset_step", "email")
    email = request.session.get(SESSION_RESET_EMAIL, "")
    return render(
        request,
        "accounts/password_forgot.html",
        {"step": step, "reset_email": email},
    )


@require_POST
def email_verification_send(request: HttpRequest) -> HttpResponse:
    """Envoie un code (inscription ou changement de mot de passe en profil)."""
    purpose = (request.POST.get("purpose") or "").strip()
    email = (request.POST.get("email") or "").strip()

    if purpose == PURPOSE_CHANGE_PASSWORD:
        if not request.user.is_authenticated:
            return JsonResponse({"ok": False, "message": "Connexion requise."}, status=403)
        ok_email, err_email, email_norm = validate_recipient_email(email)
        if not ok_email:
            return JsonResponse({"ok": False, "message": err_email}, status=400)
        ok, msg = send_verification_code(
            email=email_norm,
            purpose=purpose,
            user=request.user,
        )
        return JsonResponse({"ok": ok, "message": msg})

    if purpose == PURPOSE_REGISTER:
        ok_email, err_email, email_norm = validate_recipient_email(email)
        if not ok_email:
            return JsonResponse({"ok": False, "message": err_email}, status=400)
        ok, msg = send_verification_code(email=email_norm, purpose=purpose)
        return JsonResponse({"ok": ok, "message": msg})

    return JsonResponse({"ok": False, "message": "Action non reconnue."}, status=400)


@require_POST
def email_verification_confirm(request: HttpRequest) -> HttpResponse:
    """Valide un code et enregistre la vérification en session."""
    purpose = (request.POST.get("purpose") or "").strip()
    code = (request.POST.get("code") or "").strip()
    email = (request.POST.get("email") or "").strip()

    if purpose == PURPOSE_CHANGE_PASSWORD:
        if not request.user.is_authenticated:
            return JsonResponse({"ok": False, "message": "Connexion requise."}, status=403)
        ok_email, err_email, email_norm = validate_recipient_email(email)
        if not ok_email:
            return JsonResponse({"ok": False, "message": err_email}, status=400)
        email = email_norm

    ok, msg = verify_submitted_code(email=email, code=code, purpose=purpose)
    if not ok:
        return JsonResponse({"ok": False, "message": msg})

    if purpose == PURPOSE_CHANGE_PASSWORD and request.user.is_authenticated:
        mark_password_change_verified(request, request.user)
    else:
        mark_email_verified_in_session(request, purpose, email)

    return JsonResponse({"ok": True, "message": msg})


def require_register_email_verified(request: HttpRequest, email: str) -> str | None:
    """Retourne un message d'erreur si l'e-mail n'est pas vérifié, sinon None."""
    if is_email_verified_in_session(request, PURPOSE_REGISTER, email):
        return None
    return (
        "Vérifiez votre adresse e-mail : cliquez sur « Envoyer le code », "
        "puis saisissez le code reçu avant de créer le compte."
    )


def require_password_change_email_verified(
    request: HttpRequest, user: User
) -> str | None:
    if is_password_change_verified_in_session(request, user):
        return None
    return (
        "Pour modifier votre mot de passe, vérifiez d'abord un e-mail : "
        "saisissez l'adresse, envoyez le code, validez-le, puis choisissez le nouveau mot de passe."
    )
