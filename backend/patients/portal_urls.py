from django.urls import path

from . import portal_views

urlpatterns = [
    path("", portal_views.patient_portal, name="patient_portal"),
    path("compte/", portal_views.patient_profil, name="patient_profil"),
    path("rdv/", portal_views.patient_rendez_vous, name="patient_rendez_vous"),
    path("rdv/nouveau/", portal_views.patient_rendez_vous_nouveau, name="patient_rendez_vous_nouveau"),
    path(
        "rdv/<int:pk>/detail/",
        portal_views.patient_rendez_vous_detail,
        name="patient_rendez_vous_detail",
    ),
    path(
        "rdv/<int:pk>/annuler/",
        portal_views.patient_rendez_vous_annuler,
        name="patient_rendez_vous_annuler",
    ),
    path("ordonnances/", portal_views.patient_ordonnances, name="patient_ordonnances"),
    path(
        "ordonnances/<int:pk>/pdf/",
        portal_views.telecharger_ordonnance,
        name="telecharger_ordonnance",
    ),
    path(
        "documents/<int:pk>/pdf/",
        portal_views.telecharger_document_medical,
        name="telecharger_document_medical",
    ),
]
