from django.db import models


class Absence(models.Model):
    SIGNALEE_PAR_CHOICES = (
        ("medecin", "Médecin"),
        ("secretaire", "Secrétaire"),
    )
    medecin = models.ForeignKey(
        "accounts.Medecin",
        on_delete=models.CASCADE,
        related_name="absences",
    )
    date_absence = models.DateField()
    motif = models.TextField(blank=True)
    signalee_par = models.CharField(
        max_length=20, choices=SIGNALEE_PAR_CHOICES, default="secretaire"
    )
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_absence"]
        verbose_name = "Absence"
        verbose_name_plural = "Absences"

    def __str__(self):
        return f"Absence Dr {self.medecin} — {self.date_absence}"


class ScoreCardiovasculaire(models.Model):
    NIVEAU_CHOICES = (
        ("faible", "Faible"),
        ("modéré", "Modéré"),
        ("élevé", "Élevé"),
    )
    SEXE_CHOICES = (("M", "Homme"), ("F", "Femme"))

    patient = models.ForeignKey(
        "patients.Patient",
        on_delete=models.CASCADE,
        related_name="scores_cardio",
    )
    medecin = models.ForeignKey(
        "accounts.Medecin",
        on_delete=models.CASCADE,
        related_name="scores_cardio",
    )
    date_calcul = models.DateTimeField(auto_now_add=True)
    age = models.PositiveSmallIntegerField()
    sexe = models.CharField(max_length=1, choices=SEXE_CHOICES)
    cholesterol_total = models.FloatField()
    hdl = models.FloatField()
    tension_systolique = models.PositiveSmallIntegerField()
    traitement_hta = models.BooleanField(default=False)
    tabagisme = models.BooleanField(default=False)
    diabete = models.BooleanField(default=False)
    score_points = models.IntegerField(default=0)
    risk_percent = models.FloatField()
    niveau = models.CharField(max_length=10, choices=NIVEAU_CHOICES)

    class Meta:
        ordering = ["-date_calcul"]
        verbose_name = "Score cardiovasculaire"
        verbose_name_plural = "Scores cardiovasculaires"

    def __str__(self):
        return f"{self.patient} — {self.risk_percent:.1f}% ({self.niveau})"


class ECGAnalyse(models.Model):
    """
    Analyse d’un enregistrement type MIT-BIH (PhysioNet) : onde ECG, annotations,
    indice de risque arythmique pédagogique (non équivalent à un diagnostic clinique).
    """

    NIVEAU_CHOICES = ScoreCardiovasculaire.NIVEAU_CHOICES

    patient = models.ForeignKey(
        "patients.Patient",
        on_delete=models.CASCADE,
        related_name="analyses_ecg",
    )
    medecin = models.ForeignKey(
        "accounts.Medecin",
        on_delete=models.CASCADE,
        related_name="analyses_ecg",
    )
    date_analyse = models.DateTimeField(auto_now_add=True)
    dataset = models.CharField(
        max_length=40,
        default="mitdb",
        help_text="Identifiant PhysioNet (ex. mitdb).",
    )
    record_id = models.CharField(max_length=20, help_text="Ex. 100, 208…")
    fs = models.FloatField(default=360)
    duree_s = models.FloatField(default=0)
    risk_percent = models.FloatField(
        help_text="Indice % affiché (peut combiner ECG + dernier Framingham patient)."
    )
    niveau = models.CharField(max_length=10, choices=NIVEAU_CHOICES)
    risk_ecg_seul = models.FloatField(
        default=0,
        help_text="Indice dérivé uniquement du signal / annotations.",
    )
    metrics = models.JSONField(default=dict, blank=True)
    beat_counts = models.JSONField(default=dict, blank=True)
    waveform = models.JSONField(
        default=list,
        blank=True,
        help_text="Échantillons ECG sous-échantillonnés pour affichage.",
    )

    class Meta:
        ordering = ["-date_analyse"]
        verbose_name = "Analyse ECG"
        verbose_name_plural = "Analyses ECG"

    def __str__(self):
        return f"{self.patient} — {self.dataset}/{self.record_id} ({self.risk_percent:.1f}%)"


class StatutCabinet(models.Model):
    STATUT_CHOICES = (
        ("ouvert", "Ouvert"),
        ("fermé", "Fermé"),
    )
    statut = models.CharField(max_length=10, choices=STATUT_CHOICES, default="ouvert")
    modifie_par = models.ForeignKey(
        "accounts.Secretaire",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="modifications_statut_cabinet",
    )
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Statut du cabinet"
        verbose_name_plural = "Statut du cabinet"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1, defaults={"statut": "ouvert"})
        return obj


class Notification(models.Model):
    TYPE_CHOICES = (
        ("rdv", "Rendez-vous"),
        ("absence", "Absence"),
        ("ordonnance", "Ordonnance"),
        ("document", "Document médical"),
        ("cabinet", "Cabinet"),
    )
    destinataire_patient = models.ForeignKey(
        "patients.Patient",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
    )
    destinataire_secretaire = models.ForeignKey(
        "accounts.Secretaire",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
    )
    message = models.TextField()
    date_creation = models.DateTimeField(auto_now_add=True)
    lu = models.BooleanField(default=False)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="rdv")

    class Meta:
        ordering = ["-date_creation"]
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"

    def __str__(self):
        return self.message[:60]
