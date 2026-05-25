from django.db import models


class RendezVous(models.Model):
    STATUT_CHOICES = (
        ("en_attente", "En attente"),
        ("confirmé", "Confirmé"),
        ("annulé", "Annulé"),
        ("terminé", "Terminé"),
    )
    CREE_PAR_CHOICES = (
        ("patient", "Patient"),
        ("visiteur", "Visiteur (site public)"),
        ("secretaire", "Secrétaire"),
    )

    patient = models.ForeignKey(
        "patients.Patient",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="rendez_vous",
    )
    guest_nom_complet = models.CharField(
        "Nom du demandeur (hors portail)",
        max_length=200,
        blank=True,
    )
    guest_email = models.EmailField("E-mail demandeur", blank=True)
    guest_telephone = models.CharField(
        "Téléphone demandeur",
        max_length=32,
        blank=True,
    )
    medecin = models.ForeignKey(
        "accounts.Medecin",
        on_delete=models.CASCADE,
        related_name="rendez_vous",
    )
    date_heure = models.DateTimeField()
    motif = models.TextField(blank=True)
    statut = models.CharField(
        max_length=20, choices=STATUT_CHOICES, default="en_attente"
    )
    cree_par = models.CharField(
        max_length=20, choices=CREE_PAR_CHOICES, default="patient"
    )
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["date_heure"]
        verbose_name = "Rendez-vous"
        verbose_name_plural = "Rendez-vous"

    @property
    def demandeur_nom_affiche(self) -> str:
        if self.patient_id:
            u = self.patient.user
            return (u.get_full_name() or u.username or "Patient").strip()
        nom = (self.guest_nom_complet or "").strip()
        return nom or "Demandeur (site)"

    def __str__(self):
        return (
            f"{self.demandeur_nom_affiche} — {self.date_heure:%Y-%m-%d %H:%M} ({self.statut})"
        )
