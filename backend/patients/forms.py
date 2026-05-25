from __future__ import annotations

from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q

from .models import Patient

User = get_user_model()


class PatientForm(forms.ModelForm):
    """Fiche patient secrétariat : identité sur le compte utilisateur (plus de liste déroulante « User »)."""

    first_name = forms.CharField(label="Prénom", max_length=150)
    last_name = forms.CharField(label="Nom", max_length=150)
    email = forms.EmailField(
        label="E-mail",
        help_text="Sert aussi d’identifiant de connexion (identique au nom d’utilisateur).",
    )

    class Meta:
        model = Patient
        fields = [
            "date_naissance",
            "telephone",
            "adresse",
            "groupe_sanguin",
            "genre",
            "cin",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            u = self.instance.user
            self.fields["first_name"].initial = u.first_name
            self.fields["last_name"].initial = u.last_name
            self.fields["email"].initial = u.email

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if not email:
            raise ValidationError("L’e-mail est requis.")
        conflicts = User.objects.filter(Q(email__iexact=email) | Q(username__iexact=email))
        if self.instance.pk:
            conflicts = conflicts.exclude(pk=self.instance.user_id)
        if conflicts.exists():
            raise ValidationError(
                "Un compte utilise déjà cet e-mail ou cet identifiant."
            )
        return email

    @transaction.atomic
    def save(self, commit=True):
        first_name = (self.cleaned_data.get("first_name") or "").strip()
        last_name = (self.cleaned_data.get("last_name") or "").strip()
        email = self.cleaned_data["email"]

        if self.instance.pk:
            u = self.instance.user
            u.first_name = first_name
            u.last_name = last_name
            u.email = email
            u.username = email
            u.save()
            return super().save(commit=commit)

        u = User(
            username=email,
            email=email,
            first_name=first_name,
            last_name=last_name,
            role="patient",
        )
        u.set_unusable_password()
        u.save()
        patient = u.profil_patient
        patient.date_naissance = self.cleaned_data["date_naissance"]
        patient.telephone = self.cleaned_data["telephone"]
        patient.adresse = self.cleaned_data.get("adresse") or ""
        patient.groupe_sanguin = self.cleaned_data.get("groupe_sanguin") or "NS"
        patient.genre = self.cleaned_data.get("genre") or ""
        patient.cin = (self.cleaned_data.get("cin") or "").strip()[:32]
        patient.save()
        self.instance = patient
        return patient
