"""Genereert PDF-versies van de 3 intake-formulieren voor klantgesprekken."""
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER

# ── Brand kleuren (Ink Indigo palet) ──────────────────────────────────────
INK_INDIGO   = colors.HexColor("#2E5AAC")
CHARCOAL     = colors.HexColor("#111827")
MUTED        = colors.HexColor("#4B5563")
PAGE_BG      = colors.HexColor("#F9FAFB")
SURFACE      = colors.white
BORDER       = colors.HexColor("#CBD5E1")
SUBTLE       = colors.HexColor("#F3F4F6")
SUCCESS      = colors.HexColor("#16734A")
SUCCESS_BG   = colors.HexColor("#DCFCE7")
WARNING      = colors.HexColor("#B45309")
WARNING_BG   = colors.HexColor("#FEF3C7")

W, H = A4
MARGIN = 2 * cm


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "title", fontName="Helvetica-Bold", fontSize=20,
            textColor=CHARCOAL, spaceAfter=4, leading=24,
        ),
        "subtitle": ParagraphStyle(
            "subtitle", fontName="Helvetica", fontSize=10,
            textColor=MUTED, spaceAfter=16,
        ),
        "h2": ParagraphStyle(
            "h2", fontName="Helvetica-Bold", fontSize=13,
            textColor=INK_INDIGO, spaceBefore=16, spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "body", fontName="Helvetica", fontSize=9,
            textColor=CHARCOAL, leading=14,
        ),
        "label": ParagraphStyle(
            "label", fontName="Helvetica-Bold", fontSize=8,
            textColor=MUTED, spaceAfter=2,
        ),
        "tip": ParagraphStyle(
            "tip", fontName="Helvetica-Oblique", fontSize=8,
            textColor=MUTED, leading=12, spaceBefore=4, spaceAfter=8,
        ),
        "footer": ParagraphStyle(
            "footer", fontName="Helvetica", fontSize=7,
            textColor=MUTED, alignment=TA_CENTER,
        ),
    }


def _header_table(doc_title: str, subtitle: str, s) -> list:
    """Blauwe header-balk bovenaan elke pagina."""
    header_data = [[Paragraph(doc_title, s["title"])],
                   [Paragraph(subtitle,  s["subtitle"])]]
    t = Table([[Paragraph(doc_title, s["title"])],
               [Paragraph(subtitle,  s["subtitle"])]],
              colWidths=[W - 2 * MARGIN])
    t.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, -1), SURFACE),
        ("LINEBELOW",   (0, 1), (-1, 1),  1.5, INK_INDIGO),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 8),
    ]))
    return [t, Spacer(1, 0.4 * cm)]


def _invulrij(label: str, breedte: float = W - 2 * MARGIN, s=None) -> Table:
    """Één invulregel met label + grijze onderstreep."""
    t = Table(
        [[Paragraph(label, s["label"]), ""]],
        colWidths=[breedte * 0.38, breedte * 0.62],
    )
    t.setStyle(TableStyle([
        ("LINEBELOW",     (1, 0), (1, 0),  0.8, BORDER),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING",    (0, 0), (-1, -1), 2),
        ("VALIGN",        (0, 0), (-1, -1), "BOTTOM"),
    ]))
    return t


def _sectie_tabel(headers: list[str], rijen: int,
                  col_widths: list[float] | None = None, s=None) -> Table:
    """Tabel met header-rij + lege invulrijen."""
    breedte = W - 2 * MARGIN
    if col_widths is None:
        n = len(headers)
        col_widths = [breedte / n] * n

    header_row = [Paragraph(h, s["label"]) for h in headers]
    data = [header_row] + [[""] * len(headers) for _ in range(rijen)]

    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0),  SUBTLE),
        ("LINEBELOW",     (0, 0), (-1, 0),  1,   INK_INDIGO),
        ("LINEBELOW",     (0, 1), (-1, -1), 0.5, BORDER),
        ("LINEBEFORE",    (0, 0), (-1, -1), 0.4, BORDER),
        ("LINEAFTER",     (-1, 0),(-1, -1), 0.4, BORDER),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [SURFACE, SUBTLE]),
        ("FONTSIZE",      (0, 0), (-1, -1), 8),
        ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTNAME",      (0, 1), (-1, -1), "Helvetica"),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 4),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return t


def _meta_row(s) -> Table:
    """Klant / datum / ingevuld-door bovenaan elk formulier."""
    labels = ["Klant:", "Datum gesprek:", "Ingevuld door:"]
    data = [[Paragraph(l, s["label"]), ""] for l in labels]
    cols = [(W - 2 * MARGIN) / 3] * 3
    flat = []
    for lbl, val in data:
        flat += [lbl, val]
    t = Table([flat], colWidths=[c * 0.35 for _ in range(3)] + [c * 0.65 for _ in range(3)])
    # simpeler: drie kolommen naast elkaar
    rows = [[Paragraph(l, s["label"]), ""] for l in labels]
    breedte = W - 2 * MARGIN
    t = Table(rows, colWidths=[breedte * 0.18, breedte * 0.15] * 3 if len(rows) > 1 else
              [breedte * 0.2, breedte * 0.8])
    # Gebruik gewoon drie losse invulrijen
    return None  # wordt vervangen door losse _invulrij calls


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(MUTED)
    canvas.drawCentredString(W / 2, 1.2 * cm,
        "Restaurant Forecast & Besteladvies — Intake Formulier  |  Vertrouwelijk")
    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN, 1.5 * cm, W - MARGIN, 1.5 * cm)
    canvas.restoreState()


# ─────────────────────────────────────────────────────────────────────────────
# FORMULIER 1 — Klantprofiel & Operationeel
# ─────────────────────────────────────────────────────────────────────────────

def build_form1(path: str) -> None:
    s = _styles()
    doc = SimpleDocTemplate(
        path, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=2 * cm,
    )
    breedte = W - 2 * MARGIN
    story = []

    story += _header_table(
        "Intake Formulier 1",
        "Klantprofiel & Operationeel Profiel — in te vullen vóór het eerste klantgesprek",
        s,
    )

    # Meta
    for lbl in ["Klant / restaurantnaam:", "Datum gesprek:", "Gesproken met:", "Ingevuld door:"]:
        story.append(_invulrij(lbl, breedte, s))
    story.append(Spacer(1, 0.3 * cm))

    # Sectie 1
    story.append(Paragraph("1. Restaurantgegevens", s["h2"]))
    for lbl in ["Naam restaurant:", "Adres:", "Contactpersoon (manager):",
                "E-mailadres:", "Telefoonnummer:"]:
        story.append(_invulrij(lbl, breedte, s))

    # Sectie 2 — Openingstijden
    story.append(Paragraph("2. Openingstijden & Services", s["h2"]))
    tabel_open = _sectie_tabel(
        ["Dag", "Open? (ja/nee)", "Van", "Tot", "Services (lunch/diner/alleen diner)"],
        7,
        [breedte * 0.14, breedte * 0.14, breedte * 0.10,
         breedte * 0.10, breedte * 0.52],
        s,
    )
    dagen_data = [
        [Paragraph("Dag", s["label"]),
         Paragraph("Open?", s["label"]),
         Paragraph("Van", s["label"]),
         Paragraph("Tot", s["label"]),
         Paragraph("Services", s["label"])],
    ]
    for dag in ["Maandag","Dinsdag","Woensdag","Donderdag","Vrijdag","Zaterdag","Zondag"]:
        dagen_data.append([Paragraph(dag, s["body"]), "", "", "", ""])
    t = Table(dagen_data, colWidths=[
        breedte * 0.14, breedte * 0.14, breedte * 0.10, breedte * 0.10, breedte * 0.52
    ], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0),  SUBTLE),
        ("LINEBELOW",     (0, 0), (-1, 0),  1,   INK_INDIGO),
        ("LINEBELOW",     (0, 1), (-1, -1), 0.5, BORDER),
        ("LINEBEFORE",    (0, 0), (-1, -1), 0.4, BORDER),
        ("LINEAFTER",     (-1,0), (-1, -1), 0.4, BORDER),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [SURFACE, SUBTLE]),
        ("FONTSIZE",      (0, 0), (-1, -1), 8),
        ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTNAME",      (0, 1), (-1, -1), "Helvetica"),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 4),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.2 * cm))
    story.append(_invulrij("Vaste sluitingsweken per jaar (bijv. zomervakantie):", breedte, s))

    # Sectie 3 — Bezetting
    story.append(Paragraph("3. Gemiddelde bezetting per dag (couverts)", s["h2"]))
    story.append(Paragraph(
        "Schatting van het aantal gasten op een rustige, gemiddelde en drukke dag.",
        s["tip"],
    ))
    bez_data = [
        [Paragraph(h, s["label"]) for h in
         ["Dag", "Rustig", "Gemiddeld", "Druk", "Max. capaciteit"]],
    ]
    for dag in ["Maandag","Dinsdag","Woensdag","Donderdag","Vrijdag","Zaterdag","Zondag"]:
        bez_data.append([Paragraph(dag, s["body"]), "", "", "", ""])
    t2 = Table(bez_data, colWidths=[breedte*0.2, breedte*0.2, breedte*0.2,
                                     breedte*0.2, breedte*0.2], repeatRows=1)
    t2.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,0), SUBTLE),
        ("LINEBELOW",     (0,0),(-1,0), 1, INK_INDIGO),
        ("LINEBELOW",     (0,1),(-1,-1), 0.5, BORDER),
        ("LINEBEFORE",    (0,0),(-1,-1), 0.4, BORDER),
        ("LINEAFTER",     (-1,0),(-1,-1), 0.4, BORDER),
        ("ROWBACKGROUNDS",(0,1),(-1,-1), [SURFACE, SUBTLE]),
        ("FONTSIZE",      (0,0),(-1,-1), 8),
        ("FONTNAME",      (0,0),(-1,0),  "Helvetica-Bold"),
        ("FONTNAME",      (0,1),(-1,-1), "Helvetica"),
        ("TOPPADDING",    (0,0),(-1,-1), 5),
        ("BOTTOMPADDING", (0,0),(-1,-1), 5),
        ("LEFTPADDING",   (0,0),(-1,-1), 4),
    ]))
    story.append(t2)
    story.append(Spacer(1, 0.2 * cm))
    story.append(_invulrij("Gemiddelde omzet per couvert (€):", breedte, s))

    # Sectie 4 — Seizoen
    story.append(Paragraph("4. Seizoenspatronen", s["h2"]))
    for lbl in [
        "Druk seizoen (bijv. zomer, december):",
        "Hoeveel % drukker dan normaal?:",
        "Rustig seizoen:",
        "Hoeveel % rustiger dan normaal?:",
    ]:
        story.append(_invulrij(lbl, breedte, s))

    # Sectie 5 — Reserveringen
    story.append(Paragraph("5. Reserveringen", s["h2"]))
    story.append(_invulrij("Werkt het restaurant met reserveringen? (ja/nee):", breedte, s))
    story.append(_invulrij("Reserveringssysteem (bijv. DISH, TheFork, eigen formulier):", breedte, s))
    story.append(_invulrij("Gemiddeld % gasten dat reserveert:", breedte, s))
    story.append(_invulrij("Groepsarrangementen aangeboden? (ja/nee + voor hoeveel personen):", breedte, s))

    # Sectie 6 — Bestellen
    story.append(Paragraph("6. Bestelgewoonten & Leveranciers", s["h2"]))
    story.append(_invulrij("Hoe vaak per week wordt er besteld?:", breedte, s))
    story.append(_invulrij("Op welke dag(en) wordt er besteld?:", breedte, s))
    story.append(Spacer(1, 0.2 * cm))

    lev_data = [
        [Paragraph(h, s["label"]) for h in
         ["Leverancier naam", "Type (groothandel/vers/dranken)", "Levertijd (dagen)"]],
    ] + [["", "", ""] for _ in range(5)]
    t3 = Table(lev_data, colWidths=[breedte*0.42, breedte*0.38, breedte*0.20], repeatRows=1)
    t3.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,0), SUBTLE),
        ("LINEBELOW",     (0,0),(-1,0), 1, INK_INDIGO),
        ("LINEBELOW",     (0,1),(-1,-1), 0.5, BORDER),
        ("LINEBEFORE",    (0,0),(-1,-1), 0.4, BORDER),
        ("LINEAFTER",     (-1,0),(-1,-1), 0.4, BORDER),
        ("ROWBACKGROUNDS",(0,1),(-1,-1), [SURFACE, SUBTLE]),
        ("FONTSIZE",      (0,0),(-1,-1), 8),
        ("FONTNAME",      (0,0),(-1,0),  "Helvetica-Bold"),
        ("FONTNAME",      (0,1),(-1,-1), "Helvetica"),
        ("TOPPADDING",    (0,0),(-1,-1), 5),
        ("BOTTOMPADDING", (0,0),(-1,-1), 8),
        ("LEFTPADDING",   (0,0),(-1,-1), 4),
    ]))
    story.append(t3)

    # Aantekeningen
    story.append(Paragraph("Aantekeningen", s["h2"]))
    for _ in range(4):
        story.append(_invulrij("", breedte, s))

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    print(f"OK: {path}")


# ─────────────────────────────────────────────────────────────────────────────
# FORMULIER 2 — Producten & Leveranciers
# ─────────────────────────────────────────────────────────────────────────────

def build_form2(path: str) -> None:
    s = _styles()
    doc = SimpleDocTemplate(
        path, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=2 * cm,
    )
    breedte = W - 2 * MARGIN
    story = []

    story += _header_table(
        "Intake Formulier 2",
        "Producten & Leveranciers — vul in met leverancierslijst of inkoopfacturen erbij",
        s,
    )
    for lbl in ["Klant / restaurantnaam:", "Datum gesprek:"]:
        story.append(_invulrij(lbl, breedte, s))
    story.append(Spacer(1, 0.3 * cm))

    # Instructie
    story.append(Paragraph("Instructie", s["h2"]))
    instructie = [
        ["SKU-code", "Code zoals in het systeem van de leverancier staat (bijv. SKU-001 of eigen artikelnummer)"],
        ["Productnaam", "Naam zoals op de factuur (bijv. 'Friet diepvries 9mm')"],
        ["Eenheid", "Hoe meet je het? → kg / stuk / liter / doos"],
        ["Verpakkingsgrootte", "Hoeveel zit er in één besteleenheid? (bijv. 10 kg per zak)"],
        ["Houdbaarheid", "Laag = weken/maanden  |  Midden = dagen  |  Hoog = <1 dag"],
        ["Leverancier", "Naam van de leverancier"],
        ["Verbruik/gast", "Hoeveel gebruik je gemiddeld per couvert? (bijv. 0.2 kg)"],
        ["Min. voorraad", "Wat wil je altijd minimaal op voorraad hebben?"],
        ["Buffer %", "Extra veiligheidsmarge bovenop de verwachte vraag (standaard: 15–20%)"],
        ["Hele dozen", "Mag je een halve verpakking bestellen? Nee = altijd hele dozen"],
    ]
    t_inst = Table(instructie, colWidths=[breedte * 0.22, breedte * 0.78])
    t_inst.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,-1), SUBTLE),
        ("ROWBACKGROUNDS",(0,0),(-1,-1), [SUBTLE, SURFACE]),
        ("LINEBELOW",     (0,0),(-1,-1), 0.4, BORDER),
        ("FONTSIZE",      (0,0),(-1,-1), 7.5),
        ("FONTNAME",      (0,0),(0,-1),  "Helvetica-Bold"),
        ("FONTNAME",      (1,0),(1,-1),  "Helvetica"),
        ("TOPPADDING",    (0,0),(-1,-1), 3),
        ("BOTTOMPADDING", (0,0),(-1,-1), 3),
        ("LEFTPADDING",   (0,0),(-1,-1), 4),
        ("VALIGN",        (0,0),(-1,-1), "TOP"),
    ]))
    story.append(t_inst)
    story.append(Spacer(1, 0.4 * cm))

    # Productlijst tabel
    story.append(Paragraph("Productlijst", s["h2"]))
    hdrs = ["#", "SKU-code", "Productnaam", "Eenh.", "Verp.grootte",
            "Houdbaarh.", "Leverancier", "Verbr./gast", "Min.vrd.", "Buffer%", "Hele doz."]
    cw = [breedte * p for p in [0.04, 0.09, 0.20, 0.06, 0.09,
                                  0.08, 0.13, 0.08, 0.07, 0.07, 0.09]]
    prod_data = [[Paragraph(h, s["label"]) for h in hdrs]]
    for i in range(1, 22):
        prod_data.append([str(i)] + [""] * (len(hdrs) - 1))

    t_prod = Table(prod_data, colWidths=cw, repeatRows=1)
    t_prod.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,0), SUBTLE),
        ("LINEBELOW",     (0,0),(-1,0), 1, INK_INDIGO),
        ("LINEBELOW",     (0,1),(-1,-1), 0.4, BORDER),
        ("LINEBEFORE",    (0,0),(-1,-1), 0.3, BORDER),
        ("LINEAFTER",     (-1,0),(-1,-1), 0.3, BORDER),
        ("ROWBACKGROUNDS",(0,1),(-1,-1), [SURFACE, SUBTLE]),
        ("FONTSIZE",      (0,0),(-1,-1), 7),
        ("FONTNAME",      (0,0),(-1,0),  "Helvetica-Bold"),
        ("FONTNAME",      (0,1),(-1,-1), "Helvetica"),
        ("TOPPADDING",    (0,0),(-1,-1), 4),
        ("BOTTOMPADDING", (0,0),(-1,-1), 7),
        ("LEFTPADDING",   (0,0),(-1,-1), 3),
        ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
    ]))
    story.append(t_prod)
    story.append(Spacer(1, 0.4 * cm))

    # Leverancierscontacten
    story.append(Paragraph("Leverancierscontacten & E-mailadressen voor bestellingen", s["h2"]))
    story.append(Paragraph(
        "De besteltool stuurt bestellingen via e-mail. Vul per leverancier het besteladres in.",
        s["tip"],
    ))
    mail_data = [
        [Paragraph(h, s["label"]) for h in
         ["Leverancier", "E-mailadres bestellingen", "T.a.v. / aanhef", "Opmerkingen"]],
    ] + [["", "", "", ""] for _ in range(6)]
    t_mail = Table(mail_data, colWidths=[breedte*0.24, breedte*0.30, breedte*0.22, breedte*0.24], repeatRows=1)
    t_mail.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,0), SUBTLE),
        ("LINEBELOW",     (0,0),(-1,0), 1, INK_INDIGO),
        ("LINEBELOW",     (0,1),(-1,-1), 0.5, BORDER),
        ("LINEBEFORE",    (0,0),(-1,-1), 0.3, BORDER),
        ("LINEAFTER",     (-1,0),(-1,-1), 0.3, BORDER),
        ("ROWBACKGROUNDS",(0,1),(-1,-1), [SURFACE, SUBTLE]),
        ("FONTSIZE",      (0,0),(-1,-1), 8),
        ("FONTNAME",      (0,0),(-1,0),  "Helvetica-Bold"),
        ("FONTNAME",      (0,1),(-1,-1), "Helvetica"),
        ("TOPPADDING",    (0,0),(-1,-1), 5),
        ("BOTTOMPADDING", (0,0),(-1,-1), 8),
        ("LEFTPADDING",   (0,0),(-1,-1), 4),
    ]))
    story.append(t_mail)

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    print(f"OK: {path}")


# ─────────────────────────────────────────────────────────────────────────────
# FORMULIER 3 — Historische data & Bijzondere dagen
# ─────────────────────────────────────────────────────────────────────────────

def build_form3(path: str) -> None:
    s = _styles()
    doc = SimpleDocTemplate(
        path, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=2 * cm,
    )
    breedte = W - 2 * MARGIN
    story = []

    story += _header_table(
        "Intake Formulier 3",
        "Historische Data & Bijzondere Dagen — minimaal 4 weken data nodig, 3–6 maanden ideaal",
        s,
    )
    for lbl in ["Klant / restaurantnaam:", "Datum gesprek:"]:
        story.append(_invulrij(lbl, breedte, s))
    story.append(Spacer(1, 0.3 * cm))

    # Sectie 1 — Beschikbare data
    story.append(Paragraph("1. Beschikbare historische data", s["h2"]))
    for lbl in [
        "POS / kassasysteem aanwezig? (ja/nee) — zo ja, welk systeem?:",
        "Export omzet per dag mogelijk? (ja/nee):",
        "Export aantal gasten (couverts) per dag mogelijk? (ja/nee):",
        "Hoe ver gaat de beschikbare data terug?:",
        "In welk formaat beschikbaar? (Excel/CSV/PDF/papier):",
        "Wie levert de data aan? (naam + e-mail):",
        "Deadline aanlevering data:",
    ]:
        story.append(_invulrij(lbl, breedte, s))

    # Sectie 2 — Startvoorraad
    story.append(Paragraph("2. Startvoorraad — nulmeting plannen", s["h2"]))
    story.append(Paragraph(
        "Bij het instellen van de tool tellen we de huidige voorraad in. "
        "Plan een moment vóór de eerste besteldag.",
        s["tip"],
    ))
    for lbl in [
        "Datum nulmeting (voorraadinventarisatie):",
        "Tijdstip:",
        "Wie telt de voorraad in?:",
        "Recent voorraadoverzicht beschikbaar? (ja/nee + datum):",
    ]:
        story.append(_invulrij(lbl, breedte, s))

    # Sectie 3 — Vaste events
    story.append(Paragraph("3. Vaste jaarlijkse events & feestdagen", s["h2"]))
    story.append(Paragraph(
        "Vaste events beïnvloeden de forecast. Geef per event het verwachte effect op het aantal gasten.",
        s["tip"],
    ))
    event_data = [
        [Paragraph(h, s["label"]) for h in
         ["Event / Feestdag", "Datum of periode", "Effect gasten (+/- %)", "Opmerkingen"]],
        ["Moederdag (2e zondag mei)", "", "", ""],
        ["Valentijnsdag (14 feb)", "", "", ""],
        ["Kerst (24–26 december)", "", "", ""],
        ["Oud & Nieuw (31 dec / 1 jan)", "", "", ""],
        ["Lokaal evenement:", "", "", ""],
        ["Lokaal evenement:", "", "", ""],
        ["Schoolvakantie zomer", "Juli–augustus", "", ""],
        ["Schoolvakantie kerst", "December", "", ""],
        ["Vaste sluitingsdag:", "", "— gesloten —", ""],
        ["Overig:", "", "", ""],
    ]
    t_ev = Table(event_data, colWidths=[breedte*0.32, breedte*0.22, breedte*0.18, breedte*0.28], repeatRows=1)
    t_ev.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,0), SUBTLE),
        ("LINEBELOW",     (0,0),(-1,0), 1, INK_INDIGO),
        ("LINEBELOW",     (0,1),(-1,-1), 0.5, BORDER),
        ("LINEBEFORE",    (0,0),(-1,-1), 0.3, BORDER),
        ("LINEAFTER",     (-1,0),(-1,-1), 0.3, BORDER),
        ("ROWBACKGROUNDS",(0,1),(-1,-1), [SURFACE, SUBTLE]),
        ("FONTSIZE",      (0,0),(-1,-1), 7.5),
        ("FONTNAME",      (0,0),(-1,0),  "Helvetica-Bold"),
        ("FONTNAME",      (0,1),(-1,-1), "Helvetica"),
        ("TOPPADDING",    (0,0),(-1,-1), 4),
        ("BOTTOMPADDING", (0,0),(-1,-1), 7),
        ("LEFTPADDING",   (0,0),(-1,-1), 4),
    ]))
    story.append(t_ev)
    story.append(Spacer(1, 0.3 * cm))

    # Sectie 4 — Seizoensgebonden producten
    story.append(Paragraph("4. Seizoensgebonden producten", s["h2"]))
    story.append(Paragraph(
        "Producten die in bepaalde periodes meer of minder worden gebruikt.",
        s["tip"],
    ))
    sz_data = [
        [Paragraph(h, s["label"]) for h in
         ["Product", "Meer of minder?", "Periode", "Geschat verschil (%)"]],
    ] + [["", "", "", ""] for _ in range(5)]
    t_sz = Table(sz_data, colWidths=[breedte*0.34, breedte*0.18, breedte*0.24, breedte*0.24], repeatRows=1)
    t_sz.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,0), SUBTLE),
        ("LINEBELOW",     (0,0),(-1,0), 1, INK_INDIGO),
        ("LINEBELOW",     (0,1),(-1,-1), 0.5, BORDER),
        ("LINEBEFORE",    (0,0),(-1,-1), 0.3, BORDER),
        ("LINEAFTER",     (-1,0),(-1,-1), 0.3, BORDER),
        ("ROWBACKGROUNDS",(0,1),(-1,-1), [SURFACE, SUBTLE]),
        ("FONTSIZE",      (0,0),(-1,-1), 8),
        ("FONTNAME",      (0,0),(-1,0),  "Helvetica-Bold"),
        ("FONTNAME",      (0,1),(-1,-1), "Helvetica"),
        ("TOPPADDING",    (0,0),(-1,-1), 4),
        ("BOTTOMPADDING", (0,0),(-1,-1), 7),
        ("LEFTPADDING",   (0,0),(-1,-1), 4),
    ]))
    story.append(t_sz)

    # Sectie 5 — Niet-representatieve periodes
    story.append(Paragraph("5. Niet-representatieve periodes in historische data", s["h2"]))
    story.append(Paragraph(
        "Periodes die buiten de forecast moeten worden gehouden "
        "(bijv. verbouwing, tijdelijk gesloten, corona).",
        s["tip"],
    ))
    nr_data = [
        [Paragraph(h, s["label"]) for h in ["Van", "Tot", "Reden"]],
    ] + [["", "", ""] for _ in range(3)]
    t_nr = Table(nr_data, colWidths=[breedte*0.20, breedte*0.20, breedte*0.60], repeatRows=1)
    t_nr.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,0), SUBTLE),
        ("LINEBELOW",     (0,0),(-1,0), 1, INK_INDIGO),
        ("LINEBELOW",     (0,1),(-1,-1), 0.5, BORDER),
        ("LINEBEFORE",    (0,0),(-1,-1), 0.3, BORDER),
        ("LINEAFTER",     (-1,0),(-1,-1), 0.3, BORDER),
        ("ROWBACKGROUNDS",(0,1),(-1,-1), [SURFACE, SUBTLE]),
        ("FONTSIZE",      (0,0),(-1,-1), 8),
        ("FONTNAME",      (0,0),(-1,0),  "Helvetica-Bold"),
        ("FONTNAME",      (0,1),(-1,-1), "Helvetica"),
        ("TOPPADDING",    (0,0),(-1,-1), 4),
        ("BOTTOMPADDING", (0,0),(-1,-1), 8),
        ("LEFTPADDING",   (0,0),(-1,-1), 4),
    ]))
    story.append(t_nr)

    # Aantekeningen
    story.append(Paragraph("Aantekeningen", s["h2"]))
    for _ in range(5):
        story.append(_invulrij("", breedte, s))

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    print(f"OK: {path}")


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import os
    base = os.path.dirname(os.path.abspath(__file__))

    build_form1(os.path.join(base, "Intake-1-Klantprofiel.pdf"))
    build_form2(os.path.join(base, "Intake-2-Producten-Leveranciers.pdf"))
    build_form3(os.path.join(base, "Intake-3-Historische-Data.pdf"))
    print("\nAlle PDFs gegenereerd in docs/intake/")
