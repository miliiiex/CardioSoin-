from django.contrib import admin
from .models import Absence, ECGAnalyse, Notification, ScoreCardiovasculaire, StatutCabinet


@admin.register(Absence)
class AbsenceAdmin(admin.ModelAdmin):
    list_display = ("medecin", "date_absence", "signalee_par")


@admin.register(ScoreCardiovasculaire)
class ScoreCardiovasculaireAdmin(admin.ModelAdmin):
    list_display = ("patient", "medecin", "risk_percent", "niveau", "date_calcul")


@admin.register(ECGAnalyse)
class ECGAnalyseAdmin(admin.ModelAdmin):
    list_display = ("patient", "medecin", "dataset", "record_id", "risk_percent", "niveau", "date_analyse")


@admin.register(StatutCabinet)
class StatutCabinetAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return not StatutCabinet.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("type", "destinataire_patient", "destinataire_secretaire", "lu", "date_creation")
    list_filter = ("type", "lu")
