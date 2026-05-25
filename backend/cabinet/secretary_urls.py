from django.urls import path

from . import secretary_views

urlpatterns = [
    path("", secretary_views.secretary_desk, name="secretary_desk"),
    path(
        "notifications-patients/",
        secretary_views.secretary_notify_patients,
        name="secretary_notify_patients",
    ),
    path("rdv/creer/", secretary_views.secretary_rdv_creer, name="secretary_rdv_creer"),
    path("statut-cabinet/", secretary_views.secretary_statut_cabinet, name="secretary_statut_cabinet"),
    path("absence/", secretary_views.secretary_absence, name="secretary_absence"),
    path("agenda/", secretary_views.secretary_agenda, name="secretary_agenda"),
    path("patient/<int:patient_id>/dossier/", secretary_views.secretary_patient_dossier, name="secretary_patient_dossier"),
    path("rdv/<int:pk>/action/", secretary_views.secretary_rdv_action, name="secretary_rdv_action"),
]
