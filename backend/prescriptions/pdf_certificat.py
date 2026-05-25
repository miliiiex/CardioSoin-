"""Mise en page PDF du certificat médical (style professionnel)."""

from __future__ import annotations

from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from django.utils import timezone

from accounts.models import Medecin
from patients.models import Patient
from prescriptions.certificat_text import (
    build_certificat_redaction,
    civilite_patient,
    date_courte_fr,
    date_longue_fr,
    nom_medecin_affiche,
    nom_patient_affiche,
)
from prescriptions.documents_catalog import (
    CABINET_ADRESSE,
    CABINET_EMAIL,
    CABINET_FAX,
    CABINET_NOM,
    CABINET_TELEPHONE,
)
from prescriptions.models import DocumentMedical

_INK = colors.HexColor("#1e293b")
_MUTED = colors.HexColor("#64748b")
_LINE = colors.HexColor("#e2e8f0")


def build_certificat_pdf(document: DocumentMedical) -> bytes:
    p: Patient = document.patient
    m: Medecin = document.medecin
    u = p.user
    med_u = m.user
    payload = document.certificat_payload()
    texte = (payload.get("texte_genere") or "").strip()
    if not texte:
        texte = build_certificat_redaction(document, p, m)

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=22 * mm,
        leftMargin=22 * mm,
        topMargin=18 * mm,
        bottomMargin=22 * mm,
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "cert_title",
        parent=styles["Heading1"],
        fontSize=18,
        alignment=TA_CENTER,
        textColor=_INK,
        spaceAfter=14,
        fontName="Helvetica-Bold",
    )
    body = ParagraphStyle(
        "cert_body",
        parent=styles["Normal"],
        fontSize=11,
        leading=16,
        textColor=_INK,
        alignment=TA_JUSTIFY,
        spaceAfter=8,
    )
    small = ParagraphStyle(
        "cert_small",
        parent=styles["Normal"],
        fontSize=9.5,
        leading=13,
        textColor=_MUTED,
    )
    small_right = ParagraphStyle(
        "cert_small_r",
        parent=small,
        alignment=TA_RIGHT,
    )
    patient_line = ParagraphStyle(
        "cert_pt",
        parent=body,
        fontSize=11.5,
        leading=16,
        spaceBefore=6,
        spaceAfter=12,
        fontName="Helvetica-Bold",
    )

    story: list = []

    story.append(Paragraph("<b>Certificat médical</b>", title))
    story.append(Spacer(1, 2 * mm))

    created = document.date_creation or timezone.now()
    date_doc = created.date()
    titre_med = (m.qualification_display or "").strip() or (
        f"Spécialiste en {m.specialite or 'Cardiologie'}"
    )
    email_med = getattr(med_u, "email", "") or CABINET_EMAIL
    tel = m.telephone or CABINET_TELEPHONE

    hdr_left = (
        f"<b>{escape(nom_medecin_affiche(m))}</b><br/>"
        f"{escape(titre_med)}<br/>"
        f"<b>{escape(CABINET_NOM)}</b><br/>"
        f"{escape(CABINET_ADRESSE)}<br/>"
        f"Tél. : {escape(tel)} · Fax : {escape(CABINET_FAX)}<br/>"
        f"E-mail : {escape(email_med)}<br/>"
        f"N° d'ordre : {escape(m.numero_ordre or '—')}"
    )
    hdr_right = f"<b>{escape(date_courte_fr(date_doc))}</b>"

    hdr_table = Table(
        [
            [Paragraph(hdr_left, small), Paragraph(hdr_right, small_right)],
        ],
        colWidths=[118 * mm, 48 * mm],
    )
    hdr_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    story.append(hdr_table)
    story.append(Spacer(1, 8 * mm))

    dn = p.date_naissance
    dn_txt = dn.strftime("%d/%m/%Y") if dn else "—"
    civilite = civilite_patient(p)
    nom_pt = nom_patient_affiche(p)
    story.append(
        Paragraph(
            f"Pour <b>{escape(nom_pt)}</b>, né(e) le {escape(dn_txt)}",
            patient_line,
        )
    )

    for bloc in texte.split("\n\n"):
        bloc = bloc.strip()
        if bloc:
            story.append(Paragraph(escape(bloc), body))

    story.append(Spacer(1, 10 * mm))
    lieu = (payload.get("lieu") or "France").strip() or "France"
    story.append(
        Paragraph(
            f"Fait le {escape(date_longue_fr(date_doc))}"
            + (f", à {escape(lieu)}" if lieu else ""),
            body,
        )
    )
    story.append(Spacer(1, 18 * mm))

    story.append(Paragraph(escape("_" * 42), body))
    story.append(Spacer(1, 2 * mm))
    story.append(
        Paragraph(
            f"<b>{escape(nom_medecin_affiche(m))}</b><br/>"
            "<i>Signature et cachet du cardiologue</i>",
            small,
        )
    )
    story.append(Spacer(1, 4 * mm))
    story.append(
        Paragraph(
            "<i>Document sans valeur sans signature et cachet du médecin.</i>",
            small,
        )
    )

    doc.build(story)
    return buffer.getvalue()
