from django.urls import path

from . import doctor_views

urlpatterns = [
    path("", doctor_views.doctor_desk, name="doctor_desk"),
    path("agenda/", doctor_views.doctor_agenda, name="doctor_agenda"),
    path("rdv/<int:pk>/terminer/", doctor_views.doctor_rdv_terminer, name="doctor_rdv_terminer"),
    path(
        "patient/<int:patient_id>/dossier/sauvegarder/",
        doctor_views.doctor_dossier_autosave,
        name="doctor_dossier_autosave",
    ),
    path("patient/<int:patient_id>/dossier/", doctor_views.doctor_dossier, name="doctor_dossier"),
    path("ordonnance/nouvelle/", doctor_views.doctor_ordonnance_nouveau, name="doctor_ordonnance_nouveau"),
    path(
        "ordonnance/apercu-certificat/",
        doctor_views.doctor_certificat_apercu,
        name="doctor_certificat_apercu",
    ),
    path("score-cardio/", doctor_views.doctor_score, name="doctor_score"),
    path(
        "score-cardio/ecg-analyse/",
        doctor_views.doctor_ecg_analyze_api,
        name="doctor_ecg_analyze_api",
    ),
    path("secretaires/", doctor_views.doctor_secretaires, name="doctor_secretaires"),
    path("absence/", doctor_views.doctor_absence, name="doctor_absence"),
]
