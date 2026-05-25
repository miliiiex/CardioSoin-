from django.contrib import admin
from .models import DossierMedical, Patient


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ("user", "date_naissance", "telephone", "cin")


@admin.register(DossierMedical)
class DossierMedicalAdmin(admin.ModelAdmin):
    list_display = ("patient", "date_modification")
