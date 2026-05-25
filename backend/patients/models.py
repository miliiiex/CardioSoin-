from django.conf import settings
from django.db import models
from encrypted_model_fields.fields import EncryptedTextField


class Patient(models.Model):
    GROUPE_SANGUIN = (
        ("A+", "A+"),
        ("A-", "A-"),
        ("B+", "B+"),
        ("B-", "B-"),
        ("AB+", "AB+"),
        ("AB-", "AB-"),
        ("O+", "O+"),
        ("O-", "O-"),
        ("NS", "Non spécifié"),
    )
    GENRE = (
        ("", "—"),
        ("F", "Femme"),
        ("M", "Homme"),
        ("A", "Autre"),
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profil_patient",
    )
    date_naissance = models.DateField("Date de naissance")
    telephone = models.CharField(max_length=20)
    adresse = models.TextField(blank=True)
    cin = models.CharField(
        "C.I.N.",
        max_length=32,
        blank=True,
        default="",
        help_text="Numéro de la carte d'identité nationale (optionnel).",
    )
    groupe_sanguin = models.CharField(
        max_length=5, choices=GROUPE_SANGUIN, default="NS", blank=True
    )
    genre = models.CharField(
        max_length=1, choices=GENRE, default="", blank=True, verbose_name="Genre"
    )

    class Meta:
        verbose_name = "Patient"
        verbose_name_plural = "Patients"

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username}"


class DossierMedical(models.Model):
    patient = models.OneToOneField(
        Patient, on_delete=models.CASCADE, related_name="dossier"
    )
    antecedents = EncryptedTextField(blank=True)
    allergies = EncryptedTextField(blank=True)
    notes_generales = EncryptedTextField(blank=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Dossier médical"
        verbose_name_plural = "Dossiers médicaux"

    def __str__(self):
        return f"Dossier — {self.patient}"
