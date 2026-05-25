from django.conf import settings

from django.contrib.auth.hashers import identify_hasher

from django.core.exceptions import ImproperlyConfigured

from django.db import models

from django.contrib.auth.models import AbstractUser





def password_looks_django_hashed(value: str) -> bool:

    if not value:

        return True

    try:

        identify_hasher(value)

        return True

    except (ImproperlyConfigured, ValueError):

        # Chaîne en clair ou hash non reconnu : identify_hasher lève ValueError

        # (ex. premier segment avant « $ » interprété comme algorithme).

        return False





class User(AbstractUser):

    ROLE_CHOICES = (

        ("doctor", "Médecin"),

        ("secretary", "Secrétaire"),

        ("patient", "Patient"),

    )



    role = models.CharField(max_length=20, choices=ROLE_CHOICES)



    groups = models.ManyToManyField(

        "auth.Group",

        related_name="accounts_users",

        blank=True,

    )



    user_permissions = models.ManyToManyField(

        "auth.Permission",

        related_name="accounts_user_permissions",

        blank=True,

    )



    def __str__(self):

        return f"{self.get_full_name() or self.username} ({self.role})"



    avatar = models.ImageField(

        "Photo de profil",

        upload_to="staff_avatars/%Y/%m/",

        blank=True,

        null=True,

    )



    def save(self, *args, **kwargs):

        if self.password and not password_looks_django_hashed(self.password):

            self.set_password(self.password)

        super().save(*args, **kwargs)





class EmailVerificationCode(models.Model):

    """Code à usage limité envoyé par e-mail (inscription, reset MDP, profil)."""



    email = models.CharField(max_length=191, db_index=True)

    purpose = models.CharField(max_length=32, db_index=True)

    code_hash = models.CharField(max_length=128)

    user = models.ForeignKey(

        settings.AUTH_USER_MODEL,

        on_delete=models.CASCADE,

        null=True,

        blank=True,

        related_name="email_verification_codes",

    )

    created_at = models.DateTimeField(auto_now_add=True)

    expires_at = models.DateTimeField()

    used_at = models.DateTimeField(null=True, blank=True)

    attempts = models.PositiveSmallIntegerField(default=0)



    class Meta:

        ordering = ["-created_at"]

        verbose_name = "Code de vérification e-mail"

        verbose_name_plural = "Codes de vérification e-mail"

        indexes = [
            models.Index(fields=["purpose", "-created_at"]),
        ]



    def __str__(self) -> str:

        return f"{self.email} — {self.purpose} ({self.created_at:%d/%m/%Y %H:%M})"





class Medecin(models.Model):

    user = models.OneToOneField(

        settings.AUTH_USER_MODEL,

        on_delete=models.CASCADE,

        related_name="profil_medecin",

    )

    specialite = models.CharField(max_length=200, default="Cardiologie")

    qualification_display = models.CharField(

        "Ligne sous le nom",

        max_length=300,

        blank=True,

        help_text="Texte court en italique sous le nom sur l'accueil (ex. « Cardiologue — Spécialiste en… »). Vide = la spécialité est réutilisée.",

    )

    numero_ordre = models.CharField("N° d'ordre", max_length=50, blank=True)

    bio = models.TextField(blank=True)

    telephone = models.CharField(max_length=20, blank=True)

    cin = models.CharField(

        "C.I.N.",

        max_length=32,

        blank=True,

        default="",

        help_text="Carte d'identité nationale (optionnel).",

    )



    class Meta:

        verbose_name = "Médecin"

        verbose_name_plural = "Médecins"



    def __str__(self):

        return f"Dr. {self.user.get_full_name() or self.user.username}"





class Secretaire(models.Model):

    user = models.OneToOneField(

        settings.AUTH_USER_MODEL,

        on_delete=models.CASCADE,

        related_name="profil_secretaire",

    )

    telephone = models.CharField(max_length=20, blank=True)

    salaire = models.DecimalField(

        "Salaire",

        max_digits=12,

        decimal_places=2,

        blank=True,

        null=True,

        help_text="Rémunération mensuelle (optionnel).",

    )

    cin = models.CharField(

        "C.I.N.",

        max_length=32,

        blank=True,

        default="",

        help_text="Carte d'identité nationale (optionnel).",

    )



    class Meta:

        verbose_name = "Secrétaire"

        verbose_name_plural = "Secrétaires"



    def __str__(self):

        return f"{self.user.get_full_name() or self.user.username} (secrétaire)"


