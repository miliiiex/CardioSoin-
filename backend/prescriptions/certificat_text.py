"""
Rédaction automatique du corps du certificat médical (style certificat professionnel).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from prescriptions.documents_catalog import label_for_certificat_type

if TYPE_CHECKING:
    from accounts.models import Medecin
    from patients.models import Patient
    from prescriptions.models import DocumentMedical

_MOIS_FR = (
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
)
_JOURS_FR = (
    "lundi",
    "mardi",
    "mercredi",
    "jeudi",
    "vendredi",
    "samedi",
    "dimanche",
)


def date_courte_fr(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def date_longue_fr(d: date) -> str:
    return f"{_JOURS_FR[d.weekday()]} {d.day} {_MOIS_FR[d.month - 1]} {d.year}"


def date_debut_affichage_fr(d: date) -> str:
    """Ex. « 11 nov. 2024 » pour le corps du certificat."""
    mois_court = _MOIS_FR[d.month - 1][:3]
    if mois_court == "aoû":
        mois_court = "août"
    return f"{d.day} {mois_court}. {d.year}"


def civilite_patient(patient: Patient) -> str:
    g = (patient.genre or "").strip().upper()
    if g == "F":
        return "Mme"
    if g == "M":
        return "M."
    return "M./Mme"


def nom_patient_affiche(patient: Patient) -> str:
    u = patient.user
    nom = (u.get_full_name() or u.username or "le patient").strip()
    return nom


def nom_medecin_affiche(medecin: Medecin) -> str:
    u = medecin.user
    full = (u.get_full_name() or u.username or "Médecin").strip()
    parts = full.split()
    if len(parts) >= 2:
        return f"Dr. {' '.join(parts[:-1])} {parts[-1].upper()}"
    return f"Dr. {full}"


def _phrase_conclusion_type(certificat_type: str, civilite: str, nom_patient: str) -> str:
    if certificat_type == "aptitude_sport":
        return (
            f"Je certifie, au vu de l'examen cardiologique réalisé ce jour, que "
            f"{civilite} {nom_patient} est apte à la pratique d'une activité sportive "
            f"dans les conditions habituelles de surveillance médicale."
        )
    if certificat_type == "aptitude_travail":
        return (
            f"Je certifie que {civilite} {nom_patient} est apte à l'exercice "
            f"de ses fonctions professionnelles dans l'état cardiovasculaire actuel."
        )
    if certificat_type == "contre_indication":
        return (
            f"Je déconseille, en l'état actuel, la reprise de l'activité envisagée "
            f"pour {civilite} {nom_patient}, sous réserve d'une réévaluation ultérieure."
        )
    if certificat_type == "bilan_preop":
        return (
            f"Le bilan cardiologique pré-opératoire de {civilite} {nom_patient} "
            f"a été réalisé ; les conclusions détaillées figurent au dossier médical."
        )
    if certificat_type == "declaration_sante":
        return (
            f"Le présent certificat atteste de l'état de santé cardiovasculaire de "
            f"{civilite} {nom_patient}, dans le cadre de la demande formulée."
        )
    if certificat_type == "ald":
        return (
            f"Je certifie que {civilite} {nom_patient} est suivi pour une affection "
            f"de longue durée nécessitant un suivi cardiologique régulier."
        )
    if certificat_type == "hospitalisation":
        return (
            f"Je certifie que {civilite} {nom_patient} a nécessité / nécessite une "
            f"prise en charge hospitalière dans le cadre décrit ci-dessus."
        )
    return (
        f"Un suivi cardiologique adapté est recommandé pour {civilite} {nom_patient}."
    )


def build_certificat_redaction(
    document: DocumentMedical,
    patient: Patient,
    medecin: Medecin,
) -> str:
    """
    Texte du corps du certificat (paragraphes), à partir des champs saisis par le médecin.
    """
    payload = document.certificat_payload()
    probleme = (payload.get("probleme") or document.commentaire or "").strip()
    if not probleme:
        probleme = "son état de santé cardiovasculaire"

    civilite = civilite_patient(patient)
    nom_pt = nom_patient_affiche(patient)
    nom_dr = nom_medecin_affiche(medecin)

    date_prise = document.date_creation.date()
    date_debut_raw = payload.get("date_debut")
    if date_debut_raw:
        try:
            date_debut = date.fromisoformat(str(date_debut_raw)[:10])
        except ValueError:
            date_debut = date_prise
    else:
        date_debut = date_prise

    try:
        duree = int(payload.get("duree_jours") or 0)
    except (TypeError, ValueError):
        duree = 0

    p1 = (
        f"Je soussigné(e), {nom_dr}, certifie avoir pris en charge ce jour "
        f"{civilite} {nom_pt}."
    )

    if duree > 0:
        duree_txt = f"{duree:02d}" if duree < 10 else str(duree)
        p2 = (
            f"Compte tenu de {probleme}, son état de santé nécessite un repos "
            f"au domicile pendant une période de {duree_txt} jour"
            f"{'s' if duree > 1 else ''}, à compter du {date_debut_affichage_fr(date_debut)}."
        )
    else:
        p2 = f"Compte tenu de {probleme}, {_phrase_conclusion_type(document.certificat_type or '', civilite, nom_pt)}"

    extra = (payload.get("precisions") or "").strip()
    parts = [p1, p2]
    if extra:
        parts.append(extra)

    texte = "\n\n".join(parts)
    return texte


class _CertificatPreviewDoc:
    """Objet minimal pour générer un aperçu sans sauvegarde."""

    def __init__(
        self,
        *,
        certificat_type: str,
        probleme: str,
        duree_jours: int,
        date_debut: date,
        precisions: str,
        date_prise: date,
    ):
        self.certificat_type = certificat_type
        self.commentaire = probleme
        self.date_creation = datetime.combine(date_prise, datetime.min.time())
        self._payload = {
            "probleme": probleme,
            "duree_jours": duree_jours,
            "date_debut": date_debut.isoformat(),
            "precisions": precisions,
        }

    def certificat_payload(self) -> dict:
        return self._payload


def build_certificat_redaction_from_form(
    *,
    probleme: str,
    duree_jours: int | None,
    date_debut: date | None,
    certificat_type: str,
    patient: Patient,
    medecin: Medecin,
    date_prise: date | None = None,
    precisions: str = "",
) -> str:
    """Prévisualisation côté médecin (sans enregistrement en base)."""
    doc = _CertificatPreviewDoc(
        certificat_type=certificat_type,
        probleme=probleme,
        duree_jours=duree_jours or 0,
        date_debut=date_debut or date.today(),
        precisions=precisions,
        date_prise=date_prise or date.today(),
    )
    return build_certificat_redaction(doc, patient, medecin)  # type: ignore[arg-type]
