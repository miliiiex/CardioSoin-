"""
Catalogues d'analyses, d'examens et types de certificats (prescriptions médecin / PDF patient).
Les clés sont stockées en JSON sur DocumentMedical ; les libellés servent à l'UI et aux PDF.
"""

from __future__ import annotations

# --- Bilan biologique ---
BILAN_ITEMS: tuple[tuple[str, str], ...] = (
    ("bilan_lipidique", "Bilan lipidique (cholestérol, LDL, HDL, triglycérides)"),
    ("glycemie_jeun", "Glycémie à jeun"),
    ("nfs", "NFS (numération formule sanguine)"),
    ("creatinine_ionogramme", "Créatinine / ionogramme"),
    ("tsh", "TSH"),
    ("d_dimères", "D-dimères (si suspicion d'embolie)"),
    ("troponine", "Troponine (urgence)"),
    ("bnp_nt_probnp", "BNP / NT-proBNP (insuffisance cardiaque)"),
)

# --- Demandes d'examens ---
EXAMEN_ITEMS: tuple[tuple[str, str], ...] = (
    ("ecg", "ECG (électrocardiogramme)"),
    ("echocardiographie", "Échocardiographie"),
    ("holter_ecg", "Holter ECG"),
    ("holter_tensionnel", "Holter tensionnel"),
    ("epreuve_effort", "Épreuve d'effort"),
    ("radio_thorax", "Radiographie thoracique"),
    ("echo_doppler_vasculaire", "Échographie doppler vasculaire"),
    ("scanner_coronaire_irm_cardiaque", "Scanner coronaire / IRM cardiaque"),
)

# --- Certificats (type principal) ---
CERTIFICAT_TYPES: tuple[tuple[str, str], ...] = (
    ("aptitude_sport", "Aptitude à la pratique sportive (loisir ou compétition)"),
    ("aptitude_travail", "Aptitude professionnelle (pilote, militaire, pompier…)"),
    ("bilan_preop", "Bilan pré-opératoire cardiaque"),
    ("declaration_sante", "Déclaration d'état de santé cardiaque (assurance, justice)"),
    ("contre_indication", "Certificat de contre-indication"),
    ("ald", "Certificat pour ALD (affection longue durée)"),
    ("hospitalisation", "Certificat d'hospitalisation"),
)

# --- Corps médical cardiologique (cases à cocher sur le certificat) ---
CERTIFICAT_MENTION_ITEMS: tuple[tuple[str, str], ...] = (
    ("aptitude_sportive", "Aptitude à la pratique sportive"),
    ("resultats_examens", "Résultats d'examens : ECG, échographie cardiaque, épreuve d'effort"),
    ("pathologie_absence", "Absence de pathologie cardiaque constatée"),
    ("pathologie_sans_detail", "Pathologie cardiaque — sans détail (secret médical)"),
    ("contre_indications", "Contre-indications éventuelles"),
    ("suivi_recommande", "Suivi cardiologique en cours ou recommandé"),
)

# --- Finalités fréquentes (complément au type) ---
CERTIFICAT_FINALITE_ITEMS: tuple[tuple[str, str], ...] = (
    ("fin_sport_competition", "Sport en compétition"),
    ("fin_sport_loisir", "Sport de loisir"),
    ("fin_profession", "Aptitude professionnelle réglementée"),
    ("fin_preop", "Bilan pré-opératoire"),
    ("fin_assurance", "Assurance / mutuelle"),
    ("fin_justice", "Justice / administration"),
)

BILAN_KEY_SET = {k for k, _ in BILAN_ITEMS}
EXAMEN_KEY_SET = {k for k, _ in EXAMEN_ITEMS}
CERTIFICAT_KEY_SET = {k for k, _ in CERTIFICAT_TYPES}
CERTIFICAT_MENTION_KEY_SET = {k for k, _ in CERTIFICAT_MENTION_ITEMS}
CERTIFICAT_FINALITE_KEY_SET = {k for k, _ in CERTIFICAT_FINALITE_ITEMS}

# Coordonnées cabinet (PDF certificat)
CABINET_NOM = "CardioSoin"
CABINET_ADRESSE = "Cabinet de cardiologie — France"
CABINET_TELEPHONE = "—"
CABINET_FAX = "—"
CABINET_EMAIL = "contact@cardiosoin.fr"


def label_for_bilan(key: str) -> str:
    return dict(BILAN_ITEMS).get(key, key)


def label_for_examen(key: str) -> str:
    return dict(EXAMEN_ITEMS).get(key, key)


def label_for_certificat_type(key: str) -> str:
    return dict(CERTIFICAT_TYPES).get(key, key)


def label_for_certificat_mention(key: str) -> str:
    return dict(CERTIFICAT_MENTION_ITEMS).get(key, key)


def label_for_certificat_finalite(key: str) -> str:
    return dict(CERTIFICAT_FINALITE_ITEMS).get(key, key)
