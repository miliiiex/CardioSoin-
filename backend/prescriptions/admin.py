from django.contrib import admin
from .models import DocumentMedical, Medicament, Ordonnance


class MedicamentInline(admin.TabularInline):
    model = Medicament
    extra = 0


@admin.register(DocumentMedical)
class DocumentMedicalAdmin(admin.ModelAdmin):
    list_display = ("kind", "patient", "medecin", "date_creation", "rendez_vous")
    list_filter = ("kind",)
    search_fields = ("patient__user__username", "commentaire")


@admin.register(Ordonnance)
class OrdonnanceAdmin(admin.ModelAdmin):
    list_display = ("patient", "medecin", "date_creation")
    inlines = [MedicamentInline]
