"""Transactionele e-mail via Resend — bestelling als PDF-bijlage + HTML-body.

Gebruik:
    from email_service import verzend_bestelling
    ok, fout = verzend_bestelling(lev_naam, df_lev, datum, lev_config, tenant_slug, manager_email)
"""
from __future__ import annotations

import io
import logging
import os
from datetime import date

import pandas as pd

logger = logging.getLogger(__name__)

# ── PDF generatie (reportlab) ──────────────────────────────────────────────

def _genereer_pdf(
    leverancier: str,
    df_lev: pd.DataFrame,
    bestel_datum: str,
    aanhef: str,
) -> bytes:
    """Genereer een simpele PDF-bestelbon. Geeft de raw bytes terug."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    heading = ParagraphStyle("Heading", parent=styles["Heading1"], fontSize=16, spaceAfter=6)
    body    = styles["Normal"]

    story = []

    # Titel
    story.append(Paragraph(f"Bestelling – {leverancier}", heading))
    story.append(Paragraph(f"Leverdatum: {bestel_datum}", body))
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph(aanhef, body))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph("Hierbij onze bestelling:", body))
    story.append(Spacer(1, 0.5 * cm))

    # Tabel
    col_naam     = "naam"     if "naam"     in df_lev.columns else df_lev.columns[0]
    col_eenheid  = "eenheid"  if "eenheid"  in df_lev.columns else ""
    col_advies   = "besteladvies" if "besteladvies" in df_lev.columns else df_lev.columns[-1]

    header = ["Artikel", "Eenheid", "Aantal"]
    data   = [header]
    for _, row in df_lev.iterrows():
        naam    = str(row.get(col_naam, ""))
        eenheid = str(row.get(col_eenheid, "")) if col_eenheid else ""
        aantal  = str(int(row[col_advies])) if pd.notna(row[col_advies]) else "0"
        data.append([naam, eenheid, aantal])

    tbl = Table(data, colWidths=[9 * cm, 4 * cm, 3 * cm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, 0), colors.HexColor("#2E5AAC")),
        ("TEXTCOLOR",   (0, 0), (-1, 0), colors.white),
        ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, 0), 10),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F3F4F6")]),
        ("GRID",        (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("FONTSIZE",    (0, 1), (-1, -1), 9),
        ("TOPPADDING",  (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(tbl)

    story.append(Spacer(1, 0.8 * cm))
    story.append(Paragraph("Graag bevestiging van ontvangst.", body))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph("Met vriendelijke groet,<br/>Restaurant Besteltool", body))

    doc.build(story)
    return buffer.getvalue()


# ── HTML body ──────────────────────────────────────────────────────────────

def _genereer_html_body(
    leverancier: str,
    df_lev: pd.DataFrame,
    bestel_datum: str,
    aanhef: str,
) -> str:
    col_naam    = "naam"        if "naam"        in df_lev.columns else df_lev.columns[0]
    col_eenheid = "eenheid"     if "eenheid"     in df_lev.columns else ""
    col_advies  = "besteladvies" if "besteladvies" in df_lev.columns else df_lev.columns[-1]

    rijen = ""
    for _, row in df_lev.iterrows():
        naam    = str(row.get(col_naam, ""))
        eenheid = str(row.get(col_eenheid, "")) if col_eenheid else ""
        aantal  = int(row[col_advies]) if pd.notna(row[col_advies]) else 0
        rijen += f"<tr><td>{naam}</td><td>{eenheid}</td><td><strong>{aantal}</strong></td></tr>"

    return f"""
<html><body style="font-family:sans-serif;color:#111827;max-width:600px;margin:0 auto">
<h2 style="color:#2E5AAC">Bestelling – {leverancier}</h2>
<p><strong>Leverdatum:</strong> {bestel_datum}</p>
<p>{aanhef}</p>
<p>Hierbij onze bestelling:</p>
<table border="0" cellspacing="0" cellpadding="6"
       style="border-collapse:collapse;width:100%">
  <thead>
    <tr style="background:#2E5AAC;color:white">
      <th align="left">Artikel</th><th align="left">Eenheid</th><th align="left">Aantal</th>
    </tr>
  </thead>
  <tbody>{rijen}</tbody>
</table>
<p style="margin-top:24px">Graag bevestiging van ontvangst.</p>
<p>Met vriendelijke groet,<br/><strong>Restaurant Besteltool</strong></p>
</body></html>
"""


# ── Resend verzending ──────────────────────────────────────────────────────

def verzend_bestelling(
    leverancier:    str,
    df_lev:         pd.DataFrame,
    bestel_datum:   str,
    lev_config:     dict,
    tenant_slug:    str,
    manager_email:  str | None = None,
) -> tuple[bool, str]:
    """
    Verzend de bestelling als e-mail via Resend.

    Parameters
    ----------
    leverancier   : naam van de leverancier
    df_lev        : DataFrame met bestelregels (bevat 'naam', 'eenheid', 'besteladvies')
    bestel_datum  : ISO-datumstring voor het onderwerp
    lev_config    : dict met 'email' en 'aanhef' van de leverancier
    tenant_slug   : slug van de tenant (voor afzender-adres)
    manager_email : BCC-adres voor de manager (optioneel)

    Returns
    -------
    (True, "")         als de e-mail is verzonden
    (False, foutmelding) als er iets misging
    """
    try:
        import resend  # type: ignore
    except ImportError:
        return False, "resend niet geïnstalleerd — voer 'pip install resend' uit"

    api_key = _lees_resend_key()
    if not api_key:
        return False, "RESEND_API_KEY niet ingesteld in secrets of omgevingsvariabelen"

    resend.api_key = api_key

    to_email = lev_config.get("email", "").strip()
    if not to_email:
        return False, f"Geen e-mailadres geconfigureerd voor {leverancier}"

    aanhef       = lev_config.get("aanhef", "Beste leverancier,")
    afzender     = f"no-reply@{tenant_slug}.besteltool.nl"
    onderwerp    = f"Bestelling – {leverancier} – {bestel_datum}"

    # PDF als bijlage
    try:
        pdf_bytes = _genereer_pdf(leverancier, df_lev, bestel_datum, aanhef)
    except Exception as pdf_err:
        logger.warning("PDF generatie mislukt, verzend zonder bijlage: %s", pdf_err)
        pdf_bytes = None

    html_body = _genereer_html_body(leverancier, df_lev, bestel_datum, aanhef)

    params: dict = {
        "from":    afzender,
        "to":      [to_email],
        "subject": onderwerp,
        "html":    html_body,
    }
    if manager_email:
        params["bcc"] = [manager_email]

    if pdf_bytes:
        import base64
        params["attachments"] = [
            {
                "filename":    f"bestelling_{bestel_datum}_{leverancier.replace(' ', '_')}.pdf",
                "content":     base64.b64encode(pdf_bytes).decode(),
                "content_type": "application/pdf",
            }
        ]

    try:
        response = resend.Emails.send(params)
        email_id = getattr(response, "id", None) or str(response)
        logger.info(
            "email_verzonden",
            extra={"leverancier": leverancier, "to": to_email, "resend_id": email_id},
        )
        return True, email_id
    except Exception as e:
        logger.error("email_fout: %s", e)
        return False, str(e)


# ── Helpers ────────────────────────────────────────────────────────────────

def _lees_resend_key() -> str | None:
    """Lees de Resend API key uit st.secrets of omgevingsvariabelen."""
    # Eerst proberen via Streamlit secrets (productie op Streamlit Cloud)
    try:
        import streamlit as st
        return st.secrets.get("resend", {}).get("api_key") or os.getenv("RESEND_API_KEY")
    except Exception:
        return os.getenv("RESEND_API_KEY")
