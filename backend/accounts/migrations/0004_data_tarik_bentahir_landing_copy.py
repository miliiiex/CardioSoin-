# Données vitrine landing — Dr Tarik Bentahir (texte carte + renommer démo « Karim Benali »).

from django.db import migrations
from django.db.models import Q


def forwards(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    Medecin = apps.get_model("accounts", "Medecin")

    intro = (
        "Fort d'une expertise reconnue en cardiologie interventionnelle, le Dr. Bentahir prend en charge "
        "les pathologies coronariennes complexes. Formé dans les centres universitaires de référence, "
        "il allie technicité de pointe et écoute attentive pour offrir à chaque patient une prise "
        "en charge personnalisée et sécurisée."
    )
    expertise_lines = [
        "Coronarographie et angioplastie",
        "Insuffisance cardiaque",
        "Syndromes coronariens aigus",
        "Pose de stents et dispositifs intra-vasculaires",
    ]
    bio = intro.strip() + "\n---\n" + "\n".join(expertise_lines)

    specialite = "Cardiologue interventionnel"
    qualification_display = "Cardiologue — Spécialiste en cardiologie interventionnelle"

    users_qs = User.objects.filter(
        role="doctor",
        is_active=True,
    ).filter(
        Q(first_name__iexact="Tarik", last_name__iexact="Bentahir")
        | Q(first_name__iexact="Karim", last_name__iexact="Benali")
    )

    for u in list(users_qs):
        fn = (u.first_name or "").strip().lower()
        ln = (u.last_name or "").strip().lower()
        if fn == "karim" and ln == "benali":
            User.objects.filter(pk=u.pk).update(first_name="Tarik", last_name="Bentahir")

        med, _ = Medecin.objects.get_or_create(
            user=u,
            defaults={"specialite": specialite},
        )
        Medecin.objects.filter(pk=med.pk).update(
            specialite=specialite,
            qualification_display=qualification_display,
            bio=bio,
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_medecin_qualification_display"),
    ]

    operations = [
        migrations.RunPython(forwards, noop_reverse),
    ]
