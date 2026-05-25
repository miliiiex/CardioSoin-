"""
Remplit les fiches présentoir (spécialité, ligne sous le nom, bio & expertises)
pour les cardiologues de démonstration décrits sur la landing.

  python manage.py cardiosoin_seed_demo_cardiologists

Prérequis : comptes User actifs avec role=doctor, prénom/nom comme ci‑dessous.
Après ajout du champ qualification_display : migrate accounts avant la commande.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from accounts.models import Medecin

_PROFILES: list[dict] = [
    {
        "name_keys": [
            ("Tarik", "Bentahir"),
            ("Karim", "Benali"),
        ],
        "specialite": "Cardiologue interventionnel",
        "qualification_display": "Cardiologue — Spécialiste en cardiologie interventionnelle",
        "intro": (
            "Fort d'une expertise reconnue en cardiologie interventionnelle, le Dr. Bentahir prend en "
            "charge les pathologies coronariennes complexes. Formé dans les centres universitaires de "
            "référence, il allie technicité de pointe et écoute attentive pour offrir à chaque patient "
            "une prise en charge personnalisée et sécurisée."
        ),
        "expertise": [
            "Coronarographie et angioplastie",
            "Insuffisance cardiaque",
            "Syndromes coronariens aigus",
            "Pose de stents et dispositifs intra-vasculaires",
        ],
        "who": "Dr. Tarik Bentahir",
    },
    {
        "name_keys": [
            ("Salma", "Yaaqoub"),
            ("Salma", "Yaakoub"),
        ],
        "specialite": "Cardiologie rythmologique",
        "qualification_display": "Cardiologue — Spécialiste en rythmologie et imagerie cardiaque",
        "intro": (
            "Le Dr. Yaaqoub se consacre avec passion à l'exploration des troubles du rythme cardiaque et à "
            "l'imagerie cardiovasculaire avancée. Grâce à une approche rigoureuse et empathique, elle "
            "assure un suivi global et préventif, particulièrement auprès des patients porteurs de troubles "
            "du rythme ou d'anomalies structurelles cardiaques."
        ),
        "expertise": [
            "Troubles du rythme et de la conduction",
            "Holter ECG et explorations électrophysiologiques",
            "Échocardiographie et imagerie avancée",
            "Cardiologie préventive et suivi chronique",
        ],
        "who": "Dr. Salma Yaaqoub",
    },
]


def _find_medecin(variants: list[tuple[str, str]]) -> Medecin | None:
    for fn, ln in variants:
        m = (
            Medecin.objects.select_related("user")
            .filter(
                user__role="doctor",
                user__is_active=True,
                user__first_name__iexact=fn.strip(),
                user__last_name__iexact=ln.strip(),
            )
            .first()
        )
        if m is not None:
            return m
    return None


class Command(BaseCommand):
    help = "Enregistre les textes vitrine des Dr Bentahir & Yaaqoub (si comptes trouvés)."

    def handle(self, *args, **options) -> None:
        from accounts.medecin_utils import ensure_medecin_for_doctor_users

        ensure_medecin_for_doctor_users()
        n_ok = 0
        for block in _PROFILES:
            med = _find_medecin(block["name_keys"])
            if med is None:
                self.stdout.write(
                    self.style.WARNING(
                        f"Compte médecin introuvable ({block['who']}) — vérifiez prénom, nom "
                        "et rôle « Médecin » sur le User."
                    )
                )
                continue
            u = med.user
            lf = (u.first_name or "").strip().lower()
            ll = (u.last_name or "").strip().lower()
            # Compte démo souvent encore « Karim Benali » : alignement nom affiché = Dr Tarik Bentahir.
            if lf == "karim" and ll == "benali" and block["who"] == "Dr. Tarik Bentahir":
                u.first_name = "Tarik"
                u.last_name = "Bentahir"
                u.save(update_fields=["first_name", "last_name"])
            # Orthographe « Yaakoub » → « Yaaqoub ».
            if lf == "salma" and ll == "yaakoub" and block["who"] == "Dr. Salma Yaaqoub":
                u.last_name = "Yaaqoub"
                u.save(update_fields=["last_name"])

            bio = block["intro"].strip() + "\n---\n" + "\n".join(block["expertise"])
            med.specialite = block["specialite"]
            med.qualification_display = block["qualification_display"]
            med.bio = bio
            med.save(
                update_fields=["specialite", "qualification_display", "bio"],
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"Profil à jour — {block['who']} ({med.user.get_username()})"
                )
            )
            n_ok += 1
        if n_ok == 0:
            self.stdout.write(
                "Aucune fiche mise à jour. Créez les utilisateurs médecins "
                "(prénoms/noms exacts) puis relancez la commande."
            )
