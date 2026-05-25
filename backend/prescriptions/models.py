from django.db import models


class DocumentMedical(models.Model):
    """Bilan biologique, demande d'examens ou certificat, lié optionnellement à un RDV."""

    KIND_BILAN = "bilan_biologique"
    KIND_EXAMENS = "demande_examens"
    KIND_CERTIFICAT = "certificat"

    KIND_CHOICES = (
        (KIND_BILAN, "Demande d'analyses / bilan biologique"),
        (KIND_EXAMENS, "Demande d'examens"),
        (KIND_CERTIFICAT, "Certificat médical"),
    )

    patient = models.ForeignKey(
        "patients.Patient",
        on_delete=models.CASCADE,
        related_name="documents_medicaux",
    )
    medecin = models.ForeignKey(
        "accounts.Medecin",
        on_delete=models.CASCADE,
        related_name="documents_medicaux_delivres",
    )
    rendez_vous = models.ForeignKey(
        "appointments.RendezVous",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documents_medicaux",
    )
    kind = models.CharField(max_length=32, choices=KIND_CHOICES)
    certificat_type = models.CharField(
        max_length=40,
        blank=True,
        help_text="Code du type de certificat si kind=certificat.",
    )
    items = models.JSONField(
        default=list,
        blank=True,
        help_text="Liste de clés (analyses ou examens cochés).",
    )
    commentaire = models.TextField(blank=True)
    certificat_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Mentions, finalités, lieu, n° dossier (certificats cardiologie).",
    )
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_creation"]
        verbose_name = "Document médical"
        verbose_name_plural = "Documents médicaux"

    def __str__(self) -> str:
        return f"{self.get_kind_display()} — {self.patient} ({self.date_creation:%d/%m/%Y})"

    def titre_court(self) -> str:
        """Libellé pour l’espace patient (liste / PDF)."""
        if self.kind == self.KIND_CERTIFICAT:
            from prescriptions.documents_catalog import label_for_certificat_type

            return label_for_certificat_type(self.certificat_type)
        return str(self.get_kind_display())

    def certificat_payload(self) -> dict:
        """Données structurées du certificat (rétrocompat. commentaire seul)."""
        data = dict(self.certificat_data or {})
        if self.commentaire and not data.get("probleme") and not data.get("corps_libre"):
            data["probleme"] = self.commentaire
        if self.commentaire and not data.get("corps_libre"):
            data["corps_libre"] = self.commentaire
        data.setdefault("probleme", "")
        data.setdefault("duree_jours", 0)
        data.setdefault("date_debut", "")
        data.setdefault("precisions", "")
        data.setdefault("texte_genere", "")
        data.setdefault("mentions", [])
        data.setdefault("finalites", [])
        data.setdefault("lieu", "France")
        data.setdefault("numero_dossier", "")
        return data


class Ordonnance(models.Model):
    patient = models.ForeignKey(
        "patients.Patient",
        on_delete=models.CASCADE,
        related_name="ordonnances",
    )
    medecin = models.ForeignKey(
        "accounts.Medecin",
        on_delete=models.CASCADE,
        related_name="ordonnances",
    )
    rendez_vous = models.ForeignKey(
        "appointments.RendezVous",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ordonnances",
    )
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_creation"]
        verbose_name = "Ordonnance"
        verbose_name_plural = "Ordonnances"

    def __str__(self):
        return f"Ordonnance {self.patient} — {self.date_creation:%d/%m/%Y}"


class Medicament(models.Model):
    ordonnance = models.ForeignKey(
        Ordonnance, on_delete=models.CASCADE, related_name="medicaments"
    )
    nom = models.CharField(max_length=200)
    dosage = models.CharField(max_length=200, blank=True)
    duree = models.CharField("Durée", max_length=200, blank=True)
    instructions = models.TextField(blank=True)

    class Meta:
        verbose_name = "Médicament"
        verbose_name_plural = "Médicaments"

    def __str__(self):
        return self.nom
