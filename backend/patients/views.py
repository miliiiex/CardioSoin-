from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import get_object_or_404, redirect, render

from accounts.permissions import is_doctor_or_secretary, is_secretary

from .forms import PatientForm
from .models import Patient


@login_required(login_url="staff_login")
@user_passes_test(is_doctor_or_secretary)
def patient_list(request):
    """Liste des patients : consultation pour le médecin, gestion (CRUD) pour la secrétaire."""
    patients = Patient.objects.select_related("user").order_by(
        "user__last_name", "user__first_name", "user__username"
    )
    template = (
        "patients/list_doctor.html"
        if getattr(request.user, "role", None) == "doctor"
        else (
            "patients/list_secretary.html"
            if getattr(request.user, "role", None) == "secretary"
            else "patients/list.html"
        )
    )
    return render(
        request,
        template,
        {
            "patients": patients,
            "can_manage_patients": is_secretary(request.user),
        },
    )


@login_required(login_url="staff_login")
@user_passes_test(is_secretary)
def patient_create(request):
    form = PatientForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(
            request,
            "Patient enregistré. Définissez un mot de passe via l’administration Django "
            "ou demandez au patient de réinitialiser son accès s’il doit se connecter.",
        )
        return redirect("patient_list")
    return render(request, "patients/form_secretary_add.html", {"form": form})


@login_required(login_url="staff_login")
@user_passes_test(is_secretary)
def patient_update(request, id: int):
    patient = get_object_or_404(Patient, id=id)
    form = PatientForm(request.POST or None, instance=patient)
    if form.is_valid():
        form.save()
        return redirect("patient_list")
    return render(request, "patients/form_secretary_edit.html", {"form": form})


@login_required(login_url="staff_login")
@user_passes_test(is_secretary)
def patient_delete(request, id: int):
    patient = get_object_or_404(Patient, id=id)
    patient.delete()
    return redirect("patient_list")