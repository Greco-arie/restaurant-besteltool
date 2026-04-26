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
    restaurant_naam: str = "Restaurant Besteltool",
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
    story.append(Paragraph(f"Met vriendelijke groet,<br/>{restaurant_naam}", body))

    doc.build(story)
    return buffer.getvalue()


# ── HTML body ──────────────────────────────────────────────────────────────

def _genereer_html_body(
    leverancier: str,
    df_lev: pd.DataFrame,
    bestel_datum: str,
    aanhef: str,
    restaurant_naam: str = "Restaurant Besteltool",
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
<p>Met vriendelijke groet,<br/><strong>{restaurant_naam}</strong></p>
</body></html>
"""


# ── Afzender-keuze (per-tenant) ────────────────────────────────────────────

_SANDBOX_AFZENDER = "onboarding@resend.dev"


def _kies_afzender(tenant_slug: str, label: str = "no-reply") -> str:
    """Kies de Resend-afzender op basis van per-tenant verified domains.

    Logica (in volgorde):
    1. ``RESEND_VERIFIED_DOMAINS`` (CSV) bevat ``{slug}.besteltool.nl`` →
       ``{label}@{slug}.besteltool.nl`` (whitespace-tolerant, case-insensitive).
    2. Anders: legacy ``RESEND_DOMEIN_GEVERIFIEERD=true`` → blanket allow op
       ``{label}@{slug}.besteltool.nl`` met deprecation-warning.
    3. Anders: sandbox-fallback ``onboarding@resend.dev`` met warning.
    """
    slug = tenant_slug.strip().lower()
    verwacht_domein = f"{slug}.besteltool.nl"

    csv_raw = os.getenv("RESEND_VERIFIED_DOMAINS", "")
    verified = {d.strip().lower() for d in csv_raw.split(",") if d.strip()}
    if verwacht_domein in verified:
        return f"{label}@{verwacht_domein}"

    legacy = os.getenv("RESEND_DOMEIN_GEVERIFIEERD", "false").lower() == "true"
    if legacy:
        logger.warning(
            "resend_legacy_flag_deprecated",
            extra={
                "reden": "RESEND_DOMEIN_GEVERIFIEERD is deprecated; "
                "gebruik RESEND_VERIFIED_DOMAINS (CSV) per-tenant",
                "tenant_slug": slug,
            },
        )
        return f"{label}@{verwacht_domein}"

    logger.warning(
        "resend_sandbox_afzender",
        extra={
            "reden": (
                f"{verwacht_domein} niet in RESEND_VERIFIED_DOMAINS en "
                "geen legacy-flag actief — fallback naar sandbox"
            ),
            "tenant_slug": slug,
        },
    )
    return _SANDBOX_AFZENDER


# ── Resend verzending ──────────────────────────────────────────────────────

def verzend_bestelling(
    leverancier:    str,
    df_lev:         pd.DataFrame,
    bestel_datum:   str,
    lev_config:     dict,
    tenant_slug:    str,
    manager_email:  str | None = None,
    restaurant_naam: str | None = None,
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

    aanhef        = lev_config.get("aanhef", "Beste leverancier,")
    naam_afzender = restaurant_naam or tenant_slug
    afzender     = _kies_afzender(tenant_slug)
    onderwerp    = f"Bestelling – {leverancier} – {bestel_datum}"

    # PDF als bijlage
    try:
        pdf_bytes = _genereer_pdf(leverancier, df_lev, bestel_datum, aanhef, naam_afzender)
    except Exception as pdf_err:
        logger.warning("PDF generatie mislukt, verzend zonder bijlage: %s", pdf_err)
        pdf_bytes = None

    html_body = _genereer_html_body(leverancier, df_lev, bestel_datum, aanhef, naam_afzender)

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


# ── Password reset e-mail ──────────────────────────────────────────────────

def verzend_reset_mail(
    to_email:        str,
    token:           str,
    restaurant_naam: str,
    gebruikersnaam:  str,
    reset_url:       str | None = None,
) -> tuple[bool, str]:
    """
    Stuur een wachtwoord-reset link naar de gebruiker.

    Parameters
    ----------
    to_email        : e-mailadres van de ontvanger
    token           : plain reset-token (fallback als reset_url None is)
    restaurant_naam : naam/slug van het restaurant (voor onderwerpveld)
    gebruikersnaam  : gebruikersnaam van de ontvanger
    reset_url       : volledige URL inclusief ?token=... (optioneel)
    """
    try:
        import resend  # type: ignore
    except ImportError:
        return False, "resend niet geïnstalleerd"

    api_key = _lees_resend_key()
    if not api_key:
        return False, "RESEND_API_KEY niet ingesteld"
    resend.api_key = api_key

    # `restaurant_naam` is op caller-niveau de tenant_slug (zie page_password_reset.py).
    afzender = _kies_afzender(restaurant_naam)

    if reset_url:
        link_blok = f"""
<p style="text-align:center;margin:32px 0">
  <a href="{reset_url}" style="background:#2E5AAC;color:white;padding:12px 28px;
     border-radius:8px;text-decoration:none;font-weight:600;display:inline-block">
    Wachtwoord instellen
  </a>
</p>
<p style="color:#6B7280;font-size:0.85rem">
  Of kopieer deze link: <code>{reset_url}</code>
</p>"""
    else:
        link_blok = f"""
<p>Gebruik dit token in de Besteltool (plak het in het veld "Reset-token"):</p>
<p style="font-family:monospace;background:#F3F4F6;padding:12px;border-radius:6px;
   word-break:break-all">{token}</p>"""

    html = f"""
<html><body style="font-family:sans-serif;color:#111827;max-width:560px;margin:0 auto">
<h2 style="color:#2E5AAC">Wachtwoord resetten — {restaurant_naam}</h2>
<p>Hallo {gebruikersnaam},</p>
<p>We hebben een verzoek ontvangen om je wachtwoord te resetten.
   Klik op de knop hieronder. De link is <strong>1 uur geldig</strong>.</p>
{link_blok}
<p style="color:#6B7280;font-size:0.85rem">
  Heb jij dit niet aangevraagd? Dan hoef je niets te doen — je wachtwoord blijft ongewijzigd.
</p>
</body></html>"""

    try:
        resp = resend.Emails.send({
            "from":    afzender,
            "to":      [to_email],
            "subject": f"Wachtwoord resetten – {restaurant_naam}",
            "html":    html,
        })
        return True, getattr(resp, "id", "") or str(resp)
    except Exception as e:
        logger.error("reset_mail_fout: %s", e)
        return False, str(e)


# ── Welkomstmail ───────────────────────────────────────────────────────────

def verzend_welkomstmail(
    to_email:        str,
    gebruikersnaam:  str,
    restaurant_naam: str,
    tenant_slug:     str,
) -> tuple[bool, str]:
    """Stuur een welkomstmail naar een nieuwe tenant-admin."""
    try:
        import resend  # type: ignore
    except ImportError:
        return False, "resend niet geïnstalleerd"

    api_key = _lees_resend_key()
    if not api_key:
        return False, "RESEND_API_KEY niet ingesteld"
    resend.api_key = api_key

    afzender = _kies_afzender(tenant_slug, label="welkom")

    html = f"""
<html><body style="font-family:sans-serif;color:#111827;max-width:560px;margin:0 auto">
<h2 style="color:#2E5AAC">Welkom bij de Besteltool!</h2>
<p>Hallo {gebruikersnaam},</p>
<p>Je account voor <strong>{restaurant_naam}</strong> is aangemaakt.
   Hier zijn je inloggegevens:</p>
<table style="border-collapse:collapse;width:100%;margin:16px 0">
  <tr>
    <td style="padding:8px;border:1px solid #CBD5E1;font-weight:600">Restaurant (slug)</td>
    <td style="padding:8px;border:1px solid #CBD5E1;font-family:monospace">{tenant_slug}</td>
  </tr>
  <tr>
    <td style="padding:8px;border:1px solid #CBD5E1;font-weight:600">Gebruikersnaam</td>
    <td style="padding:8px;border:1px solid #CBD5E1;font-family:monospace">{gebruikersnaam}</td>
  </tr>
</table>
<p style="color:#B45309;background:#FEF3C7;padding:10px;border-radius:6px">
  <strong>Let op:</strong> je hebt een tijdelijk wachtwoord ontvangen van je beheerder.
  Verander dit zo snel mogelijk via "Wachtwoord vergeten" op het inlogscherm.
</p>
<p style="color:#6B7280;font-size:0.85rem;margin-top:24px">
  Vragen? Neem contact op met je beheerder.
</p>
</body></html>"""

    try:
        resp = resend.Emails.send({
            "from":    afzender,
            "to":      [to_email],
            "subject": f"Welkom bij de Besteltool – {restaurant_naam}",
            "html":    html,
        })
        return True, getattr(resp, "id", "") or str(resp)
    except Exception as e:
        logger.error("welkomstmail_fout: %s", e)
        return False, str(e)


# ── Lage voorraad alert ────────────────────────────────────────────────────

def verzend_lage_voorraad_alert(
    to_email:        str,
    restaurant_naam: str,
    producten:       list[dict],
) -> tuple[bool, str]:
    """
    Stuur een lage-voorraad alert naar de manager na het opslaan van de sluitstock.

    producten: lijst van dicts met keys naam, current_stock, minimumvoorraad, eenheid
    """
    try:
        import resend  # type: ignore
    except ImportError:
        return False, "resend niet geïnstalleerd"

    api_key = _lees_resend_key()
    if not api_key:
        return False, "RESEND_API_KEY niet ingesteld"
    resend.api_key = api_key

    _domein_geverifieerd = os.getenv("RESEND_DOMEIN_GEVERIFIEERD", "false").lower() == "true"
    afzender = "no-reply@besteltool.nl" if _domein_geverifieerd else "onboarding@resend.dev"

    rijen = "".join(
        f"<tr><td>{p['naam']}</td><td>{p.get('current_stock', 0):.1f} {p.get('eenheid','')}</td>"
        f"<td>{p.get('minimumvoorraad', 0):.1f} {p.get('eenheid','')}</td></tr>"
        for p in producten
    )
    html = f"""
<html><body style="font-family:sans-serif;color:#111827;max-width:600px;margin:0 auto">
<h2 style="color:#B45309">&#9888; Lage voorraad — {restaurant_naam}</h2>
<p>Na het opslaan van de sluitstock staan de volgende producten <strong>onder hun minimumvoorraad</strong>:</p>
<table border="0" cellspacing="0" cellpadding="6"
       style="border-collapse:collapse;width:100%">
  <thead>
    <tr style="background:#B45309;color:white">
      <th align="left">Artikel</th><th align="left">Huidige voorraad</th><th align="left">Minimum</th>
    </tr>
  </thead>
  <tbody>{rijen}</tbody>
</table>
<p style="margin-top:20px;color:#6B7280;font-size:0.85rem">
  Controleer het besteladvies in de Besteltool.
</p>
</body></html>"""

    try:
        resp = resend.Emails.send({
            "from":    afzender,
            "to":      [to_email],
            "subject": f"Lage voorraad alert – {restaurant_naam}",
            "html":    html,
        })
        return True, getattr(resp, "id", "") or str(resp)
    except Exception as e:
        logger.error("lage_voorraad_alert_fout: %s", e)
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
