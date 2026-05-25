from django.urls import path

from patients.portal_views import (
    landing_rdv_public_submit,
    patient_ordonnances,
    patient_profil,
    patient_rendez_vous,
    patient_rendez_vous_annuler,
    patient_rendez_vous_detail,
    patient_rendez_vous_nouveau,
    telecharger_document_medical,
    telecharger_ordonnance,
)

from .views import landing, login_view, logout_view, patient_space, staff_login, staff_profil
from django.conf import settings

from .views_email import (
    email_verification_confirm,
    email_verification_send,
    password_forgot,
)
from .views_email_setup import email_smtp_setup

urlpatterns = [
    path("", landing, name="landing"),
]

if settings.DEBUG:
    urlpatterns += [
        path("configurer-email/", email_smtp_setup, name="email_smtp_setup"),
    ]

urlpatterns += [
    path("demande-rendez-vous/", landing_rdv_public_submit, name="landing_rdv_public"),
    path("login/", login_view, name="login"),
    path("mot-de-passe-oublie/", password_forgot, name="password_forgot"),
    path(
        "verifier-email/envoyer/",
        email_verification_send,
        name="email_verification_send",
    ),
    path(
        "verifier-email/confirmer/",
        email_verification_confirm,
        name="email_verification_confirm",
    ),
    path("connexion-personnel/", staff_login, name="staff_login"),
    path("personnel/profil/", staff_profil, name="staff_profil"),
    path("espace-patient/rdv/<int:pk>/annuler/", patient_rendez_vous_annuler, name="patient_rendez_vous_annuler"),
    path("espace-patient/rdv/<int:pk>/detail/", patient_rendez_vous_detail, name="patient_rendez_vous_detail"),
    path("espace-patient/rdv/nouveau/", patient_rendez_vous_nouveau, name="patient_rendez_vous_nouveau"),
    path("espace-patient/rdv/", patient_rendez_vous, name="patient_rendez_vous"),
    path("espace-patient/ordonnances/<int:pk>/pdf/", telecharger_ordonnance, name="telecharger_ordonnance"),
    path("espace-patient/documents/<int:pk>/pdf/", telecharger_document_medical, name="telecharger_document_medical"),
    path("espace-patient/ordonnances/liste/", patient_ordonnances, name="patient_ordonnances"),
    path("espace-patient/compte/", patient_profil, name="patient_profil"),
    path("espace-patient/", patient_space, name="patient_space"),
    path("logout/", logout_view, name="logout"),
]
