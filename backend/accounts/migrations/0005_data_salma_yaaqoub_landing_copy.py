# Données vitrine landing — Dr Salma Yaaqoub (texte officiel carte).

from django.db import migrations
from django.db.models import Q


def forwards(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    Medecin = apps.get_model("accounts", "Medecin")

    intro = (
        "Le Dr. Yaaqoub se consacre avec passion à l'exploration des troubles du rythme cardiaque et à "
        "l'imagerie cardiovasculaire avancée. Grâce à une approche rigoureuse et empathique, elle "
        "assure un suivi global et préventif, particulièrement auprès des patients porteurs de troubles "
        "du rythme ou d'anomalies structurelles cardiaques."
    )
    expertise_lines = [
        "Troubles du rythme et de la conduction",
        "Holter ECG et explorations électrophysiologiques",
        "Échocardiographie et imagerie avancée",
        "Cardiologie préventive et suivi chronique",
    ]
    bio = intro.strip() + "\n---\n" + "\n".join(expertise_lines)

    specialite = "Cardiologie rythmologique"
    qualification_display = "Cardiologue — Spécialiste en rythmologie et imagerie cardiaque"

    users_qs = User.objects.filter(
        role="doctor",
        is_active=True,
    ).filter(
        Q(first_name__iexact="Salma", last_name__iexact="Yaaqoub")
        | Q(first_name__iexact="Salma", last_name__iexact="Yaakoub")
    )

    for u in list(users_qs):
        fn = (u.first_name or "").strip().lower()
        ln = (u.last_name or "").strip().lower()
        if fn == "salma" and ln == "yaakoub":
            User.objects.filter(pk=u.pk).update(last_name="Yaaqoub")

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
        ("accounts", "0004_data_tarik_bentahir_landing_copy"),
    ]

    operations = [
        migrations.RunPython(forwards, noop_reverse),
    ]
