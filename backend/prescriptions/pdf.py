from __future__ import annotations

from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from accounts.models import Medecin
from patients.models import Patient
from prescriptions.documents_catalog import (
    CABINET_ADRESSE,
    CABINET_EMAIL,
    CABINET_FAX,
    CABINET_NOM,
    CABINET_TELEPHONE,
    label_for_bilan,
    label_for_certificat_finalite,
    label_for_certificat_mention,
    label_for_certificat_type,
    label_for_examen,
)
from prescriptions.models import DocumentMedical, Ordonnance
from prescriptions.pdf_certificat import build_certificat_pdf

_TEAL = colors.HexColor("#0d9488")
_TEAL_DARK = colors.HexColor("#0f766e")
_LINE_GREY = colors.HexColor("#e2e8f0")


def _para(text: str, style: ParagraphStyle) -> Paragraph:
    """Texte brut uniquement : tout est échappé (pas de balises HTML dans `text`)."""
    safe = escape(text or "").replace("\n", "<br/>")
    return Paragraph(safe, style)


def _bold_title(text: str, style: ParagraphStyle) -> Paragraph:
    """Titre en gras : balises contrôlées par le code, libellé échappé."""
    return Paragraph("<b>" + escape(text) + "</b>", style)


def _signature_medecin_block(
    story,
    *,
    heading: str,
    h2,
    body,
    small,
    med_u,
    mention_obligatoire: bool = True,
) -> None:
    """Zone signature : ligne pour paraphe manuscrit + nom du médecin."""
    story.append(_para(heading, h2))
    if mention_obligatoire:
        story.append(
            Paragraph(
                "<i>Document sans valeur sans signature et cachet du médecin.</i>",
                small,
            )
        )
        story.append(Spacer(1, 5 * mm))
    story.append(Spacer(1, 4 * mm))
    ligne = "_" * 52
    nom_doc = escape(med_u.get_full_name() or med_u.last_name or "Médecin")
    story.append(
        Paragraph(
            f"{escape(ligne)}<br/><br/><b>Dr {nom_doc}</b>",
            body,
        )
    )


def _base_story_styles():
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "cs_title",
        parent=styles["Heading1"],
        fontSize=20,
        textColor=_TEAL_DARK,
        spaceAfter=8,
        borderPadding=0,
    )
    subtitle = ParagraphStyle(
        "cs_sub",
        parent=styles["Normal"],
        fontSize=9.5,
        textColor=colors.HexColor("#64748b"),
        spaceAfter=4,
    )
    h2 = ParagraphStyle(
        "cs_h2",
        parent=styles["Heading2"],
        fontSize=12,
        textColor=_TEAL_DARK,
        spaceBefore=10,
        spaceAfter=6,
    )
    body = ParagraphStyle(
        "cs_body",
        parent=styles["Normal"],
        fontSize=10,
        leading=13,
        spaceAfter=4,
    )
    small = ParagraphStyle(
        "cs_small",
        parent=styles["Normal"],
        fontSize=8.5,
        textColor=colors.HexColor("#64748b"),
        leading=11,
    )
    cell = ParagraphStyle(
        "cs_cell",
        parent=styles["Normal"],
        fontSize=8.5,
        leading=11,
        spaceAfter=2,
    )
    cell_hdr = ParagraphStyle(
        "cs_cell_hdr",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
        textColor=colors.white,
        fontName="Helvetica-Bold",
    )
    return styles, title, subtitle, h2, body, small, cell, cell_hdr


def _header_block(story, title_style, subtitle_style, doc_title: str):
    story.append(
        Table(
            [[_bold_title(CABINET_NOM, title_style)]],
            colWidths=[170 * mm],
            style=TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f0fdfa")),
                    ("BOX", (0, 0), (-1, -1), 1, _TEAL),
                    ("LEFTPADDING", (0, 0), (-1, -1), 12),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                    ("TOPPADDING", (0, 0), (-1, -1), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ]
            ),
        )
    )
    story.append(Spacer(1, 3 * mm))
    story.append(_para(CABINET_ADRESSE, subtitle_style))
    story.append(Spacer(1, 6 * mm))
    story.append(_bold_title(doc_title, title_style))
    story.append(
        Table(
            [[""]],
            colWidths=[174 * mm],
            style=TableStyle(
                [
                    ("LINEABOVE", (0, 0), (-1, -1), 0.5, _LINE_GREY),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            ),
        )
    )


def build_ordonnance_pdf(ordonnance: Ordonnance) -> bytes:
    p: Patient = ordonnance.patient
    m: Medecin = ordonnance.medecin
    u = p.user
    med_u = m.user
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=18 * mm,
    )
    _, title, subtitle, h2, body, small, cell, cell_hdr = _base_story_styles()
    story = []
    _header_block(story, title, subtitle, "Ordonnance médicale")

    story.append(_para("Médecin prescripteur", h2))
    story.append(
        _para(
            f"Dr {med_u.get_full_name() or med_u.username}",
            body,
        )
    )
    story.append(_para(f"N° d'ordre : {m.numero_ordre or '—'}", small))
    story.append(_para(f"Téléphone : {m.telephone or '—'}", small))
    story.append(Spacer(1, 2 * mm))
    story.append(_para("Patient", h2))
    story.append(_para(f"{u.get_full_name() or u.username}", body))
    dn = p.date_naissance
    dn_txt = dn.strftime("%d/%m/%Y") if dn else "—"
    story.append(_para(f"Date de naissance : {dn_txt}", small))
    if ordonnance.rendez_vous_id:
        rdv = ordonnance.rendez_vous
        if rdv:
            story.append(
                _para(
                    f"Consultation liée : {rdv.date_heure.strftime('%d/%m/%Y %H:%M')}",
                    small,
                )
            )
    story.append(Spacer(1, 4 * mm))

    meds = list(ordonnance.medicaments.all())
    data: list[list[Paragraph]] = [
        [
            _para("Médicament", cell_hdr),
            _para("Dosage", cell_hdr),
            _para("Durée", cell_hdr),
            _para("Instructions", cell_hdr),
        ]
    ]
    if meds:
        for med in meds:
            data.append(
                [
                    _para(med.nom or "—", cell),
                    _para(med.dosage or "—", cell),
                    _para(med.duree or "—", cell),
                    _para(med.instructions or "—", cell),
                ]
            )
    else:
        data.append(
            [
                _para("—", cell),
                _para("—", cell),
                _para("—", cell),
                _para("Aucun médicament enregistré.", cell),
            ]
        )

    # Largeurs adaptées à A4 avec marges : total ~ 170mm
    col_w = [42 * mm, 32 * mm, 28 * mm, 68 * mm]
    t = Table(data, colWidths=col_w, repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), _TEAL_DARK),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOX", (0, 0), (-1, -1), 0.75, _LINE_GREY),
                ("GRID", (0, 0), (-1, -1), 0.35, _LINE_GREY),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
            ]
        )
    )
    story.append(t)
    story.append(Spacer(1, 12 * mm))
    _signature_medecin_block(
        story,
        heading="Signature du médecin",
        h2=h2,
        body=body,
        small=small,
        med_u=med_u,
    )
    story.append(
        _para(
            f"Édité le {ordonnance.date_creation.strftime('%d/%m/%Y à %H:%M')}",
            small,
        )
    )
    doc.build(story)
    return buffer.getvalue()


def _append_certificat_cardio_pdf(
    story: list,
    document: DocumentMedical,
    *,
    title_style,
    subtitle_style,
    h2,
    body,
    small,
) -> None:
    """Certificat cardiologique structuré (en-tête cabinet, patient, corps, forme)."""
    p: Patient = document.patient
    m: Medecin = document.medecin
    u = p.user
    med_u = m.user
    payload = document.certificat_payload()
    titre_cert = (
        label_for_certificat_type(document.certificat_type)
        if document.certificat_type
        else "Certificat médical"
    )

    _header_block(story, title_style, subtitle_style, titre_cert)

    story.append(_para("En-tête du cabinet", h2))
    story.append(_bold_title(CABINET_NOM, body))
    story.append(_para(CABINET_ADRESSE, small))
    titre_med = m.specialite or "Cardiologie"
    qualif = (m.qualification_display or "").strip()
    ligne_titre = f"Spécialiste en {titre_med}"
    if qualif:
        ligne_titre = qualif
    story.append(
        _para(
            f"Dr {med_u.get_full_name() or med_u.username} — {ligne_titre}",
            body,
        )
    )
    email_med = getattr(med_u, "email", "") or CABINET_EMAIL
    story.append(
        _para(
            f"Téléphone : {m.telephone or CABINET_TELEPHONE} · "
            f"Fax : {CABINET_FAX} · E-mail : {email_med}",
            small,
        )
    )
    story.append(_para(f"N° d'ordre : {m.numero_ordre or '—'}", small))
    story.append(Spacer(1, 5 * mm))

    story.append(_para("Informations sur le patient", h2))
    nom = (u.last_name or "").strip()
    prenom = (u.first_name or "").strip()
    if nom or prenom:
        story.append(_para(f"Nom : {nom or '—'}", body))
        story.append(_para(f"Prénom : {prenom or '—'}", body))
    else:
        story.append(_para(f"{u.get_full_name() or u.username}", body))
    dn = p.date_naissance
    dn_txt = dn.strftime("%d/%m/%Y") if dn else "—"
    story.append(_para(f"Date de naissance : {dn_txt}", small))
    dossier = (payload.get("numero_dossier") or "").strip() or str(p.pk)
    story.append(_para(f"N° de dossier : {dossier}", small))
    story.append(Spacer(1, 5 * mm))

    story.append(_para("Corps médical (cardiologique)", h2))
    mentions: list[str] = list(payload.get("mentions") or [])
    finalites: list[str] = list(payload.get("finalites") or [])
    if mentions:
        parts_m = [escape(f"• {label_for_certificat_mention(k)}") for k in mentions]
        story.append(Paragraph("<br/>".join(parts_m), body))
    if finalites:
        story.append(Spacer(1, 2 * mm))
        story.append(_para("Finalité :", body))
        parts_f = [escape(f"• {label_for_certificat_finalite(k)}") for k in finalites]
        story.append(Paragraph("<br/>".join(parts_f), body))
    corps = (payload.get("corps_libre") or document.commentaire or "").strip()
    if corps:
        story.append(Spacer(1, 3 * mm))
        story.append(_para(corps, body))
    if not mentions and not finalites and not corps:
        story.append(
            _para(
                "Certificat établi après examen cardiologique dans le respect du secret médical.",
                body,
            )
        )

    story.append(Spacer(1, 8 * mm))
    lieu = (payload.get("lieu") or "France").strip() or "France"
    date_txt = document.date_creation.strftime("%d/%m/%Y")
    story.append(_para(f"Fait à {lieu}, le {date_txt}", body))
    story.append(Spacer(1, 10 * mm))
    _signature_medecin_block(
        story,
        heading="Signature et cachet du cardiologue",
        h2=h2,
        body=body,
        small=small,
        med_u=med_u,
    )


def build_document_medical_pdf(document: DocumentMedical) -> bytes:
    p: Patient = document.patient
    m: Medecin = document.medecin
    u = p.user
    med_u = m.user
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=18 * mm,
    )
    _, title, subtitle, h2, body, small, cell, _ = _base_story_styles()

    story: list = []

    if document.kind == DocumentMedical.KIND_CERTIFICAT:
        return build_certificat_pdf(document)

    if document.kind == DocumentMedical.KIND_BILAN:
        doc_title = "Demande d'analyses — Bilan biologique"
    else:
        doc_title = "Demande d'examens"
    _header_block(story, title, subtitle, doc_title)

    story.append(_para("Médecin", h2))
    story.append(_para(f"Dr {med_u.get_full_name() or med_u.username}", body))
    story.append(_para(f"N° d'ordre : {m.numero_ordre or '—'}", small))
    story.append(_para(f"Téléphone : {m.telephone or '—'}", small))

    story.append(_para("Patient", h2))
    story.append(_para(f"{u.get_full_name() or u.username}", body))
    dn = p.date_naissance
    dn_txt = dn.strftime("%d/%m/%Y") if dn else "—"
    story.append(_para(f"Date de naissance : {dn_txt}", small))
    if document.rendez_vous_id and document.rendez_vous:
        rdv = document.rendez_vous
        story.append(
            _para(
                f"Consultation liée : {rdv.date_heure.strftime('%d/%m/%Y %H:%M')}",
                small,
            )
        )

    story.append(Spacer(1, 4 * mm))
    story.append(_para("Éléments prescrits", h2))
    keys: list[str] = list(document.items or [])
    if not keys:
        story.append(_para("—", body))
    else:
        if document.kind == DocumentMedical.KIND_BILAN:
            parts = [escape(f"• {label_for_bilan(k)}") for k in keys]
        else:
            parts = [escape(f"• {label_for_examen(k)}") for k in keys]
        story.append(Paragraph("<br/>".join(parts), body))

    if document.commentaire.strip():
        story.append(Spacer(1, 3 * mm))
        story.append(_para("Précisions / remarques", h2))
        story.append(_para(document.commentaire, body))

    story.append(Spacer(1, 14 * mm))
    _signature_medecin_block(
        story,
        heading="Signature et cachet du médecin",
        h2=h2,
        body=body,
        small=small,
        med_u=med_u,
    )
    story.append(
        _para(
            f"Édité le {document.date_creation.strftime('%d/%m/%Y à %H:%M')}",
            small,
        )
    )
    doc.build(story)
    return buffer.getvalue()
