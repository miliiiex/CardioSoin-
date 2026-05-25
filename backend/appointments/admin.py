from django.contrib import admin
from .models import RendezVous


@admin.register(RendezVous)
class RendezVousAdmin(admin.ModelAdmin):
    list_display = ("col_demandeur", "medecin", "date_heure", "statut", "cree_par")
    list_filter = ("statut", "cree_par")

    @admin.display(description="Demandeur")
    def col_demandeur(self, obj: RendezVous) -> str:
        return obj.demandeur_nom_affiche
