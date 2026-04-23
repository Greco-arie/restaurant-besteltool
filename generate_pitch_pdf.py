"""Genereert de sales pitch / systeemdocumentatie PDF voor de Restaurant Besteltool."""
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import ListFlowable, ListItem

OUTPUT = "Restaurant_Besteltool_Overzicht.pdf"

# ── Kleuren ───────────────────────────────────────────────────────────────
DONKERBLAUW  = colors.HexColor("#1a2e4a")
MIDDELBLAUW  = colors.HexColor("#2563eb")
LICHTBLAUW   = colors.HexColor("#eff6ff")
ACCENTGROEN  = colors.HexColor("#16a34a")
LICHTGROEN   = colors.HexColor("#f0fdf4")
ACCENTORANJE = colors.HexColor("#ea580c")
LICHTORANJE  = colors.HexColor("#fff7ed")
GRIJS        = colors.HexColor("#6b7280")
LICHTGRIJS   = colors.HexColor("#f9fafb")
RANDGRIJS    = colors.HexColor("#e5e7eb")
WIT          = colors.white

# ── Stijlen ───────────────────────────────────────────────────────────────
styles = getSampleStyleSheet()

def stijl(naam, **kwargs):
    return ParagraphStyle(naam, **kwargs)

S_TITEL = stijl("Titel",
    fontName="Helvetica-Bold", fontSize=28, leading=34,
    textColor=WIT, alignment=TA_CENTER, spaceAfter=6)

S_SUBTITEL = stijl("Subtitel",
    fontName="Helvetica", fontSize=13, leading=18,
    textColor=colors.HexColor("#cbd5e1"), alignment=TA_CENTER, spaceAfter=4)

S_H1 = stijl("H1",
    fontName="Helvetica-Bold", fontSize=16, leading=22,
    textColor=DONKERBLAUW, spaceBefore=18, spaceAfter=8)

S_H2 = stijl("H2",
    fontName="Helvetica-Bold", fontSize=12, leading=16,
    textColor=MIDDELBLAUW, spaceBefore=12, spaceAfter=5)

S_H3 = stijl("H3",
    fontName="Helvetica-Bold", fontSize=10, leading=14,
    textColor=DONKERBLAUW, spaceBefore=8, spaceAfter=3)

S_BODY = stijl("Body",
    fontName="Helvetica", fontSize=9.5, leading=14,
    textColor=colors.HexColor("#374151"), alignment=TA_JUSTIFY, spaceAfter=5)

S_BODY_BOLD = stijl("BodyBold",
    fontName="Helvetica-Bold", fontSize=9.5, leading=14,
    textColor=colors.HexColor("#374151"), spaceAfter=3)

S_KLEIN = stijl("Klein",
    fontName="Helvetica", fontSize=8, leading=11,
    textColor=GRIJS, spaceAfter=3)

S_LABEL = stijl("Label",
    fontName="Helvetica-Bold", fontSize=8, leading=11,
    textColor=MIDDELBLAUW, spaceAfter=2)

S_QUOTE = stijl("Quote",
    fontName="Helvetica-Oblique", fontSize=10, leading=15,
    textColor=DONKERBLAUW, leftIndent=16, spaceAfter=6)

S_WIT = stijl("Wit",
    fontName="Helvetica", fontSize=9.5, leading=14,
    textColor=WIT, spaceAfter=4)

S_WIT_BOLD = stijl("WitBold",
    fontName="Helvetica-Bold", fontSize=11, leading=16,
    textColor=WIT, spaceAfter=3)

S_CENTER = stijl("Center",
    fontName="Helvetica", fontSize=9.5, leading=14,
    textColor=colors.HexColor("#374151"), alignment=TA_CENTER, spaceAfter=4)

S_VOETNOOT = stijl("Voetnoot",
    fontName="Helvetica", fontSize=7.5, leading=11,
    textColor=GRIJS, alignment=TA_CENTER)

PAGE_W, PAGE_H = A4
MARGE = 2.0 * cm

# ── Hulpfuncties ──────────────────────────────────────────────────────────

def hr(kleur=RANDGRIJS, dikte=0.5):
    return HRFlowable(width="100%", thickness=dikte, color=kleur,
                      spaceAfter=6, spaceBefore=6)

def ruimte(h=0.3):
    return Spacer(1, h * cm)

def info_box(tekst, achtergrond=LICHTBLAUW, rand=MIDDELBLAUW):
    """Gekleurde informatiekaart."""
    tbl = Table([[Paragraph(tekst, S_BODY)]], colWidths=[PAGE_W - 2 * MARGE])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), achtergrond),
        ("BOX",        (0, 0), (-1, -1), 0.8, rand),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING",  (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
    ]))
    return tbl

def feature_tabel(rijen, kol_breedtes=None):
    """Tabel met zebra-achtige stijl."""
    if kol_breedtes is None:
        kol_breedtes = [4 * cm, PAGE_W - 2 * MARGE - 4 * cm]
    data = []
    for i, (label, omschrijving) in enumerate(rijen):
        data.append([
            Paragraph(label, S_LABEL),
            Paragraph(omschrijving, S_BODY),
        ])
    tbl = Table(data, colWidths=kol_breedtes)
    style = [
        ("VALIGN",       (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING",   (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 6),
        ("LINEBELOW",    (0, 0), (-1, -2), 0.3, RANDGRIJS),
    ]
    for i in range(0, len(data), 2):
        style.append(("BACKGROUND", (0, i), (-1, i), LICHTGRIJS))
    tbl.setStyle(TableStyle(style))
    return tbl

def stap_kaarten(stappen):
    """Horizontale rij stap-kaartjes."""
    n = len(stappen)
    breedte = (PAGE_W - 2 * MARGE) / n
    data = [[Paragraph(f"<b>{s['nr']}</b><br/>{s['label']}", S_CENTER) for s in stappen]]
    tbl = Table(data, colWidths=[breedte] * n)
    style_list = [
        ("BACKGROUND", (0, 0), (-1, -1), LICHTBLAUW),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
    ]
    for i in range(n):
        style_list.append(("BOX", (i, 0), (i, 0), 0.5, MIDDELBLAUW))
    tbl.setStyle(TableStyle(style_list))
    return tbl

def rol_tabel(rijen):
    """Drie-koloms tabel voor rollen."""
    kop = [
        Paragraph("Rol", S_LABEL),
        Paragraph("Wie", S_LABEL),
        Paragraph("Wat mag deze rol", S_LABEL),
    ]
    data = [kop]
    for r in rijen:
        data.append([Paragraph(c, S_BODY) for c in r])
    breedte = PAGE_W - 2 * MARGE
    tbl = Table(data, colWidths=[2.8*cm, 4*cm, breedte - 6.8*cm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0),  DONKERBLAUW),
        ("TEXTCOLOR",    (0, 0), (-1, 0),  WIT),
        ("FONTNAME",     (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",     (0, 0), (-1, 0),  8),
        ("TOPPADDING",   (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 6),
        ("LEFTPADDING",  (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("VALIGN",       (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS",(0, 1),(-1, -1), [WIT, LICHTGRIJS]),
        ("BOX",          (0, 0), (-1, -1), 0.5, RANDGRIJS),
        ("LINEBELOW",    (0, 0), (-1, -1), 0.3, RANDGRIJS),
    ]))
    return tbl

def header_blok(kleur=DONKERBLAUW):
    """Donkere titelpagina header als tabel."""
    inhoud = [
        Paragraph("Restaurant Besteltool", S_TITEL),
        ruimte(0.3),
        Paragraph("Slimmer bestellen. Minder verspilling. Meer rust.", S_SUBTITEL),
        ruimte(0.5),
        Paragraph("Systeemdocumentatie &amp; productoverzicht", stijl("sub2",
            fontName="Helvetica", fontSize=10, leading=14,
            textColor=colors.HexColor("#94a3b8"), alignment=TA_CENTER)),
    ]
    tbl = Table([[inhoud]], colWidths=[PAGE_W - 2 * MARGE])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, -1), kleur),
        ("TOPPADDING",   (0, 0), (-1, -1), 40),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 40),
        ("LEFTPADDING",  (0, 0), (-1, -1), 20),
        ("RIGHTPADDING", (0, 0), (-1, -1), 20),
    ]))
    return tbl

def highlight_box(titel, tekst, kleur_bg=LICHTGROEN, kleur_rand=ACCENTGROEN):
    inner = [
        Paragraph(titel, stijl("hbt", fontName="Helvetica-Bold", fontSize=9.5,
                                textColor=ACCENTGROEN, spaceAfter=3)),
        Paragraph(tekst, S_BODY),
    ]
    tbl = Table([inner], colWidths=[PAGE_W - 2 * MARGE])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, -1), kleur_bg),
        ("LINEAFTER",    (0, 0), (0, -1),  3, kleur_rand),
        ("TOPPADDING",   (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 8),
        ("LEFTPADDING",  (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
    ]))
    return tbl

def twee_kolom_kaarten(links, rechts):
    """Twee kaartjes naast elkaar."""
    breedte = (PAGE_W - 2 * MARGE - 0.4 * cm) / 2
    def kaart(titel, tekst, bg, rand):
        return Table([[
            Paragraph(f"<b>{titel}</b><br/><br/>{tekst}",
                      stijl("krt", fontName="Helvetica", fontSize=9, leading=13,
                             textColor=colors.HexColor("#374151")))
        ]], colWidths=[breedte])._setStyle(TableStyle([
            ("BACKGROUND",   (0,0),(-1,-1), bg),
            ("BOX",          (0,0),(-1,-1), 0.8, rand),
            ("TOPPADDING",   (0,0),(-1,-1), 10),
            ("BOTTOMPADDING",(0,0),(-1,-1), 10),
            ("LEFTPADDING",  (0,0),(-1,-1), 12),
            ("RIGHTPADDING", (0,0),(-1,-1), 12),
        ])) or Table([[
            Paragraph(f"<b>{titel}</b><br/><br/>{tekst}",
                      stijl("krt2", fontName="Helvetica", fontSize=9, leading=13,
                             textColor=colors.HexColor("#374151")))
        ]], colWidths=[breedte])

    l_tbl = Table([[Paragraph(f"<b>{links[0]}</b><br/><br/>{links[1]}",
                              stijl("kl", fontName="Helvetica", fontSize=9, leading=13,
                                    textColor=colors.HexColor("#374151")))]],
                  colWidths=[breedte])
    l_tbl.setStyle(TableStyle([
        ("BACKGROUND",   (0,0),(-1,-1), links[2]),
        ("BOX",          (0,0),(-1,-1), 0.8, links[3]),
        ("TOPPADDING",   (0,0),(-1,-1), 10),
        ("BOTTOMPADDING",(0,0),(-1,-1), 10),
        ("LEFTPADDING",  (0,0),(-1,-1), 12),
        ("RIGHTPADDING", (0,0),(-1,-1), 12),
    ]))
    r_tbl = Table([[Paragraph(f"<b>{rechts[0]}</b><br/><br/>{rechts[1]}",
                              stijl("kr", fontName="Helvetica", fontSize=9, leading=13,
                                    textColor=colors.HexColor("#374151")))]],
                  colWidths=[breedte])
    r_tbl.setStyle(TableStyle([
        ("BACKGROUND",   (0,0),(-1,-1), rechts[2]),
        ("BOX",          (0,0),(-1,-1), 0.8, rechts[3]),
        ("TOPPADDING",   (0,0),(-1,-1), 10),
        ("BOTTOMPADDING",(0,0),(-1,-1), 10),
        ("LEFTPADDING",  (0,0),(-1,-1), 12),
        ("RIGHTPADDING", (0,0),(-1,-1), 12),
    ]))
    outer = Table([[l_tbl, Spacer(0.4*cm, 1), r_tbl]],
                  colWidths=[breedte, 0.4*cm, breedte])
    outer.setStyle(TableStyle([("VALIGN", (0,0),(-1,-1), "TOP")]))
    return outer

# ── Document opbouwen ─────────────────────────────────────────────────────

def bouw_pdf():
    doc = SimpleDocTemplate(
        OUTPUT,
        pagesize=A4,
        leftMargin=MARGE, rightMargin=MARGE,
        topMargin=MARGE, bottomMargin=MARGE + 0.5*cm,
        title="Restaurant Besteltool — Systeemdocumentatie",
        author="Restaurant Besteltool",
    )

    story = []

    # ════════════════════════════════════════════════════════════════════════
    # PAGINA 1 — TITELPAGINA
    # ════════════════════════════════════════════════════════════════════════
    story.append(header_blok())
    story.append(ruimte(1.0))

    # Kernbelofte
    kern_data = [
        [
            Paragraph("Probleem", stijl("kp", fontName="Helvetica-Bold", fontSize=10,
                                        textColor=ACCENTORANJE, spaceAfter=4)),
            Paragraph("Oplossing", stijl("kop", fontName="Helvetica-Bold", fontSize=10,
                                         textColor=ACCENTGROEN, spaceAfter=4)),
        ],
        [
            Paragraph(
                "Restaurantmanagers bestellen op gevoel. Te veel besteld = verspilling en kosten. "
                "Te weinig besteld = tekort en stress. Geen enkel systeem helpt hen hierbij.",
                S_BODY),
            Paragraph(
                "De Restaurant Besteltool berekent elke ochtend automatisch wat besteld moet worden, "
                "per leverancier, op basis van de verwachte drukte van morgen. "
                "Precies genoeg — niet meer, niet minder.",
                S_BODY),
        ],
    ]
    kern_tbl = Table(kern_data, colWidths=[(PAGE_W - 2*MARGE - 0.5*cm)/2]*2)
    kern_tbl.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (0, -1), LICHTORANJE),
        ("BACKGROUND",   (1, 0), (1, -1), LICHTGROEN),
        ("BOX",          (0, 0), (0, -1), 0.8, ACCENTORANJE),
        ("BOX",          (1, 0), (1, -1), 0.8, ACCENTGROEN),
        ("TOPPADDING",   (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 10),
        ("LEFTPADDING",  (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("VALIGN",       (0, 0), (-1, -1), "TOP"),
        ("COLPADDING",   (0, 0), (-1, -1), 6),
    ]))
    outer_kern = Table([[kern_tbl]], colWidths=[PAGE_W - 2*MARGE])
    outer_kern.setStyle(TableStyle([("LEFTPADDING",(0,0),(-1,-1),0),("RIGHTPADDING",(0,0),(-1,-1),0)]))
    story.append(outer_kern)

    story.append(ruimte(0.8))

    # Drie kerngetallen
    getallen_data = [[
        Paragraph("<b>8 schermen</b><br/>Volledig dagelijks workflow", S_CENTER),
        Paragraph("<b>3 gebruikersrollen</b><br/>Admin / Manager / Medewerker", S_CENTER),
        Paragraph("<b>Meerdere restaurants</b><br/>Multi-tenant architectuur", S_CENTER),
        Paragraph("<b>Automatische e-mail</b><br/>Bestelling direct naar leverancier", S_CENTER),
    ]]
    getallen_tbl = Table(getallen_data, colWidths=[(PAGE_W - 2*MARGE)/4]*4)
    getallen_tbl.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, -1), DONKERBLAUW),
        ("TEXTCOLOR",    (0, 0), (-1, -1), WIT),
        ("FONTNAME",     (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE",     (0, 0), (-1, -1), 9),
        ("TOPPADDING",   (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 14),
        ("ALIGN",        (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("LINEAFTER",    (0, 0), (2, -1),  0.5, colors.HexColor("#334155")),
    ]))
    story.append(getallen_tbl)

    story.append(ruimte(0.8))
    story.append(Paragraph(
        "Dit document geeft een volledig overzicht van alle functionaliteit, "
        "de dagelijkse workflow en de technische architectuur van de Restaurant Besteltool.",
        stijl("intro", fontName="Helvetica", fontSize=9, leading=13,
              textColor=GRIJS, alignment=TA_CENTER)
    ))

    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════════════════
    # PAGINA 2 — DAGELIJKSE WORKFLOW
    # ════════════════════════════════════════════════════════════════════════
    story.append(Paragraph("De dagelijkse workflow", S_H1))
    story.append(hr())
    story.append(Paragraph(
        "De tool is gebouwd rondom één centrale vraag die elke restaurantmanager elke ochtend stelt: "
        "<i>\"Wat moet ik vandaag bestellen?\"</i> De workflow loopt in vijf vaste stappen.",
        S_BODY))
    story.append(ruimte(0.4))

    stappen = [
        {"nr": "1", "label": "Dag afsluiten\n(gisteren)"},
        {"nr": "2", "label": "Forecast\nbeken"},
        {"nr": "3", "label": "Bestelling\nreviewen"},
        {"nr": "4", "label": "Bestelling\nexporteren"},
        {"nr": "5", "label": "Inventaris\nbijhouden"},
    ]
    story.append(stap_kaarten(stappen))
    story.append(ruimte(0.5))

    workflow_stappen = [
        ("Stap 1 — Dag afsluiten",
         "De manager vult het werkelijke aantal gasten (couverts) en de omzet van gisteren in. "
         "Dit zijn de twee kerngetallen die het systeem gebruikt om te leren. "
         "Optioneel: een event of bijzonderheid noteren (bijv. 'verjaardagsfeest 40 pax'). "
         "Het systeem vergelijkt de werkelijke uitkomst met de eerdere forecast en past de "
         "correctiefactor per weekdag automatisch aan."),
        ("Stap 2 — Forecast bekijken",
         "Op basis van historische data berekent het systeem hoeveel gasten morgen verwacht worden. "
         "De manager ziet de voorspelling, de bijbehorende bandbreedte en eventuele "
         "correcties (weersinvloed terras, feestdagen, events). Aanpassen is altijd mogelijk."),
        ("Stap 3 — Bestelling reviewen",
         "Per product verschijnt een besteladvies: hoeveel te bestellen, van welke leverancier, "
         "voor hoeveel dagen. Signaalwaarschuwingen verschijnen bij producten die de afgelopen "
         "30 dagen structureel zijn verspild of te snel op waren. De manager past aan waar nodig."),
        ("Stap 4 — Bestelling exporteren",
         "Met één klik wordt per leverancier een kant-en-klare e-mail geopend met de volledige "
         "bestellijst. Alternatief: download als CSV. Bestelling is gedaan in minder dan een minuut."),
        ("Stap 5 — Inventaris bijhouden",
         "Gedurende de dag kan de manager de voorraad corrigeren als er afwijkingen zijn. "
         "Elke correctie wordt opgeslagen met een reden (verlopen, beschadigd, intern gebruik, etc.). "
         "Deze data voedt het signaalsysteem voor verspillingspatronen."),
    ]

    for titel, tekst in workflow_stappen:
        story.append(KeepTogether([
            Paragraph(titel, S_H2),
            Paragraph(tekst, S_BODY),
            ruimte(0.2),
        ]))

    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════════════════
    # PAGINA 3 — FORECASTENGINE
    # ════════════════════════════════════════════════════════════════════════
    story.append(Paragraph("Hoe werkt de forecast?", S_H1))
    story.append(hr())
    story.append(Paragraph(
        "De forecastengine voorspelt het aantal gasten van morgen. "
        "Het systeem combineert historische data met meerdere correctiefactoren. "
        "Hoe meer data, hoe scherper de voorspelling.",
        S_BODY))
    story.append(ruimte(0.3))

    story.append(info_box(
        "<b>Basisformule:</b><br/>"
        "Forecast = Historisch gemiddelde weekdag × Correctiefactor leren × "
        "Event-multiplier × Weer-multiplier",
        achtergrond=LICHTBLAUW, rand=MIDDELBLAUW))
    story.append(ruimte(0.4))

    story.append(Paragraph("Onderdelen van de forecast", S_H2))
    forecast_rijen = [
        ("Historische baseline",
         "Gemiddeld aantal gasten per weekdag op basis van alle beschikbare dagresultaten. "
         "Het systeem heeft minimaal 3 gelijke weekdagen nodig om te starten. "
         "Daarna groeit de nauwkeurigheid elke week."),
        ("Lerende correctiefactor",
         "Elke keer dat de werkelijkheid afwijkt van de forecast, past het systeem een "
         "correctiefactor aan per weekdag. Na 3 maandagen met 10% meer gasten dan verwacht, "
         "corrigeert het systeem de maandagforecast automatisch omhoog."),
        ("Event-multiplier",
         "De manager kan een event of bijzonderheid invoeren (verjaardagsfeest, sportdag, "
         "feestdag). Het systeem past de forecast procentueel aan op basis van het verwachte "
         "extra bezoekersaantal."),
        ("Weersinvloed terras",
         "Via de Open-Meteo API wordt de weersvoorspelling voor morgen opgehaald. "
         "Bij goed weer (zonnig, > 20 graden) wordt de forecast verhoogd voor restaurants "
         "met een terras. Bij slecht weer wordt deze verlaagd."),
        ("Bandbreedte",
         "Naast de centrale voorspelling toont het systeem een optimistische en "
         "pessimistische variant. Zo weet de manager met welke variatie rekening te houden."),
    ]
    story.append(feature_tabel(forecast_rijen))
    story.append(ruimte(0.4))

    story.append(highlight_box(
        "Voorbeeld uit de praktijk",
        "Het is dinsdag. De manager wil weten hoeveel gasten er woensdag komen. "
        "Het systeem kijkt naar alle vorige woensdagen (gemiddeld 180 gasten), "
        "past de correctiefactor toe (woensdag is historisch 5% beter dan verwacht: factor 1.05), "
        "en ziet dat het morgen 24 graden wordt met zon (terras-bonus +10%). "
        "Forecast: 180 × 1.05 × 1.10 = 208 gasten.",
        kleur_bg=LICHTBLAUW, kleur_rand=MIDDELBLAUW))

    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════════════════
    # PAGINA 4 — BESTELENGINE
    # ════════════════════════════════════════════════════════════════════════
    story.append(Paragraph("Hoe wordt het besteladvies berekend?", S_H1))
    story.append(hr())
    story.append(Paragraph(
        "Per product berekent de bestelengine hoeveel besteld moet worden. "
        "De berekening houdt rekening met verwacht verbruik, huidige voorraad, "
        "het leveringsschema van de leverancier en een instelbare veiligheidsmarge.",
        S_BODY))
    story.append(ruimte(0.3))

    story.append(info_box(
        "<b>Bestelformule (per product):</b><br/>"
        "Verwachte vraag = Verbruik per gast × Forecast gasten × Dagen tot levering<br/>"
        "Buffer = Verwachte vraag × Buffer %<br/>"
        "Besteladvies = max(0, Verwachte vraag + Buffer + Party extra - Huidige voorraad)<br/>"
        "→ Afgerond naar hele verpakkingen (optioneel)",
        achtergrond=LICHTBLAUW, rand=MIDDELBLAUW))
    story.append(ruimte(0.4))

    bestel_rijen = [
        ("Verbruik per gast",
         "Hoeveel van dit product gemiddeld per gast verbruikt wordt. Ingesteld bij "
         "het aanmaken van het product via de wizard. Wordt verfijnd naarmate er meer data is."),
        ("Dagen tot levering",
         "Elke leverancier heeft een vast leveringsschema (bijv. Hanos levert op maandag en donderdag). "
         "Het systeem berekent automatisch hoeveel dagen het duurt tot de eerstvolgende levering "
         "en schaalt de bestelling hierop. Geen levering morgen = meer bestellen voor overmorgen."),
        ("Buffer %",
         "Een instelbare veiligheidsmarge per product. Ingesteld via de wizard op basis van "
         "gebruiksfrequentie: Weinig = 15%, Normaal = 20%, Veel = 25%, Heel veel = 30%. "
         "De manager kan dit altijd aanpassen."),
        ("Party extra",
         "Voor friet, desserts en dranken berekent het systeem een extra hoeveelheid "
         "bij grote groepen (party platters). Dit is automatisch en gebaseerd op het "
         "verwachte aantal gasten."),
        ("Verpakkingsafronden",
         "Optioneel per product: het besteladvies wordt naar boven afgerond op hele "
         "verpakkingen. Een doos van 10 kg friet → altijd hele dozen bestellen."),
        ("Minimumvoorraad",
         "Elk product heeft een instelbare minimumvoorraad die nooit onderschreden mag worden. "
         "Het systeem bestelt bij als de voorraad hieronder dreigt te komen, ook als de "
         "berekende vraag laag is."),
    ]
    story.append(feature_tabel(bestel_rijen))

    story.append(ruimte(0.3))
    story.append(highlight_box(
        "Voorbeeld: friet diepvries",
        "Verbruik: 0.15 kg per gast. Forecast: 208 gasten. Hanos levert in 2 dagen. "
        "Huidige voorraad: 18 kg. Buffer: 25% (Veel). "
        "Verwachte vraag: 0.15 × 208 × 2 = 62.4 kg. "
        "Buffer: 62.4 × 0.25 = 15.6 kg. Totale behoefte: 78 kg. "
        "Besteladvies: max(0, 78 - 18) = 60 kg → afgerond: 60 kg (6 zakken van 10 kg).",
        kleur_bg=LICHTGROEN, kleur_rand=ACCENTGROEN))

    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════════════════
    # PAGINA 5 — PRODUCTBEHEER & WIZARD
    # ════════════════════════════════════════════════════════════════════════
    story.append(Paragraph("Producten toevoegen — de wizard", S_H1))
    story.append(hr())
    story.append(Paragraph(
        "Een nieuw product toevoegen verloopt via een stapsgewijs ontvouwend formulier. "
        "De manager hoeft geen technische kennis te hebben: elke stap stelt één vraag "
        "in begrijpelijke taal. Op basis van de antwoorden worden alle berekeningen automatisch ingevuld.",
        S_BODY))
    story.append(ruimte(0.4))

    wizard_stappen = [
        {"nr": "Stap 1", "label": "Naam &\nLeverancier"},
        {"nr": "Stap 2", "label": "Eenheid\n(kg/stuks/L)"},
        {"nr": "Stap 3", "label": "Verpakkings-\ngrootte"},
        {"nr": "Stap 4", "label": "Gebruiks-\nfrequentie"},
        {"nr": "Stap 5", "label": "Geavanceerd\n(optioneel)"},
        {"nr": "Stap 6", "label": "Controleer\n& opslaan"},
    ]
    story.append(stap_kaarten(wizard_stappen))
    story.append(ruimte(0.4))

    wizard_rijen = [
        ("Stap 1 — Naam & leverancier",
         "De productnaam (zoals op de factuur) en het artikelnummer (SKU). "
         "Leveranciers worden opgehaald uit het systeem — niet hardcoded."),
        ("Stap 2 — Eenheid",
         "Drie grote knoppen: Gewicht (kg) / Stuks / Vloeistof (L). "
         "Bepaalt alle volgende labels en berekeningen."),
        ("Stap 3 — Verpakkingsgrootte",
         "Het label past zich aan: 'Zak van ___ kg' / 'Doos van ___ stuks' / 'Verpakking van ___ L'. "
         "Dit is de eenheid waarmee het systeem afrond bij bestellen."),
        ("Stap 4 — Gebruiksfrequentie",
         "Vier knoppen met toelichting: Weinig (15% buffer) / Normaal (20%) / Veel (25%) / "
         "Heel veel (30%). Het systeem vult automatisch de buffer % en een startwaarde voor "
         "verbruik per gast in."),
        ("Stap 5 — Geavanceerd",
         "Uitklapbaar blok, pre-filled op basis van stap 4. "
         "Buffer %, minimale voorraad, levertijd, houdbaarheid en afrondoptie. "
         "Hoeft de manager normaal niet aan te raken."),
        ("Stap 6 — Samenvatting",
         "Alle ingevulde waarden op een rij. Eén knop: opslaan. "
         "Product is direct beschikbaar in het besteladvies."),
    ]
    story.append(feature_tabel(wizard_rijen))

    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════════════════
    # PAGINA 6 — LEVERANCIERSBEHEER & VERSPILLINGSIGNALEN
    # ════════════════════════════════════════════════════════════════════════
    story.append(Paragraph("Leveranciersbeheer", S_H1))
    story.append(hr())
    story.append(Paragraph(
        "Elk restaurant configureert zijn eigen leveranciers. Per leverancier stel je in "
        "op welke dagen hij levert, wat het e-mailadres is en hoeveel dagen van tevoren besteld moet worden.",
        S_BODY))
    story.append(ruimte(0.3))

    lev_rijen = [
        ("Leverdagen",
         "Per leverancier stel je in op welke weekdagen hij levert (bijv. Hanos: maandag + donderdag). "
         "Het besteladvies houdt hier automatisch rekening mee: als vandaag woensdag is en "
         "de volgende levering is donderdag, bestelt het systeem voor 1 dag. "
         "Is de volgende levering pas maandag, dan bestelt het voor 4 dagen."),
        ("E-mailadres",
         "Het e-mailadres van de leverancier. Na het goedkeuren van de bestelling opent "
         "het systeem automatisch een kant-en-klare e-mail met de volledige bestellijst."),
        ("Levertijd",
         "Hoeveel dagen na het versturen van de bestelling de leverancier levert. "
         "Standaard 1 dag, instelbaar per leverancier."),
        ("Meerdere leveranciers",
         "Een restaurant kan onbeperkt leveranciers aanmaken. Elk product wordt gekoppeld "
         "aan één leverancier. De bestelreview en export zijn per leverancier gegroepeerd."),
    ]
    story.append(feature_tabel(lev_rijen))

    story.append(ruimte(0.5))
    story.append(Paragraph("Verspillingsignalen in de bestelreview", S_H1))
    story.append(hr())
    story.append(Paragraph(
        "Elke handmatige voorraadcorrectie wordt opgeslagen met een gestructureerde reden. "
        "Het systeem analyseert deze redenen en toont waarschuwingen in de bestelreview "
        "als er structurele patronen zijn.",
        S_BODY))
    story.append(ruimte(0.3))

    signaal_data = [
        [
            Paragraph("Geel signaal: marge te hoog", stijl("sg", fontName="Helvetica-Bold",
                fontSize=9, textColor=colors.HexColor("#92400e"))),
            Paragraph("Rood signaal: marge te laag", stijl("sr", fontName="Helvetica-Bold",
                fontSize=9, textColor=colors.HexColor("#7f1d1d"))),
        ],
        [
            Paragraph(
                "Trigger: 3× 'Verspilling — verlopen' of 'Verspilling — beschadigd' "
                "in de afgelopen 30 dagen.<br/><br/>"
                "Bericht: <i>\"Kipfilet — 4× verlopen weggegooid. Huidige marge: 25%. "
                "Overweeg te verlagen naar 20%.\"</i>",
                stijl("sg2", fontName="Helvetica", fontSize=9, leading=13,
                      textColor=colors.HexColor("#374151"))),
            Paragraph(
                "Trigger: 3× 'Sneller op dan verwacht' "
                "in de afgelopen 30 dagen.<br/><br/>"
                "Bericht: <i>\"Verse basilicum — 3× te snel op. Huidige marge: 15%. "
                "Bestel vaker of verhoog naar 20%.\"</i>",
                stijl("sr2", fontName="Helvetica", fontSize=9, leading=13,
                      textColor=colors.HexColor("#374151"))),
        ],
    ]
    signaal_tbl = Table(signaal_data, colWidths=[(PAGE_W - 2*MARGE - 0.4*cm)/2]*2)
    signaal_tbl.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (0, -1), colors.HexColor("#fffbeb")),
        ("BACKGROUND",   (1, 0), (1, -1), colors.HexColor("#fef2f2")),
        ("BOX",          (0, 0), (0, -1), 1, colors.HexColor("#f59e0b")),
        ("BOX",          (1, 0), (1, -1), 1, colors.HexColor("#ef4444")),
        ("TOPPADDING",   (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 10),
        ("LEFTPADDING",  (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("VALIGN",       (0, 0), (-1, -1), "TOP"),
        ("COLPADDING",   (0, 0), (-1, -1), 6),
    ]))
    outer_s = Table([[signaal_tbl]], colWidths=[PAGE_W - 2*MARGE])
    outer_s.setStyle(TableStyle([("LEFTPADDING",(0,0),(-1,-1),0),("RIGHTPADDING",(0,0),(-1,-1),0)]))
    story.append(outer_s)

    story.append(ruimte(0.3))
    story.append(Paragraph(
        "De correctieredenen zijn gestructureerd in drie groepen: voorraad daalt (verspilling, "
        "intern gebruik, portionering, sneller op, telling gecorrigeerd), voorraad stijgt "
        "(levering vergeten, retour, telling gecorrigeerd) en overig.",
        S_BODY))

    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════════════════
    # PAGINA 7 — GEBRUIKERSROLLEN & AUTH
    # ════════════════════════════════════════════════════════════════════════
    story.append(Paragraph("Gebruikersrollen en toegangsbeheer", S_H1))
    story.append(hr())
    story.append(Paragraph(
        "Het systeem heeft een drie-laags autorisatiesysteem. Elke laag voegt rechten toe. "
        "Managers kunnen aanvullende granulaire rechten toewijzen aan individuele medewerkers.",
        S_BODY))
    story.append(ruimte(0.3))

    rol_rijen = [
        ["Admin", "Systeembeheerder\n(jij)", "Volledig beheer over alle restaurants, gebruikers en "
         "systeeminstellingen. Cross-tenant toegang. Nieuwe restaurants aanmaken."],
        ["Manager", "Restaurantmanager", "Volledig dagelijks gebruik. Leveranciers beheren. "
         "Nieuwe medewerkers aanmaken en rechten toewijzen. Productcatalogus beheren."],
        ["Medewerker", "Keukenpersoneel,\nBediening", "Standaard read-only. Manager kan per persoon "
         "extra rechten aanzetten: voorraad wijzigen, bestelling versturen, acties maken."],
    ]
    story.append(rol_tabel(rol_rijen))
    story.append(ruimte(0.4))

    story.append(Paragraph("Granulaire rechten (per medewerker instelbaar)", S_H2))
    rechten_rijen = [
        ("Voorraad wijzigen", "Medewerker mag handmatig de voorraad corrigeren en "
         "correctieredenen invullen."),
        ("Bestelling versturen", "Medewerker mag de bestelling goedkeuren en exporteren "
         "naar de leverancier."),
        ("Acties/campagnes beheren", "Medewerker mag speciale events of acties aanmaken "
         "die de forecast beïnvloeden."),
        ("Recepten beheren", "Medewerker mag recepten aanmaken en koppelen aan producten "
         "(toekomstige functionaliteit)."),
    ]
    story.append(feature_tabel(rechten_rijen, kol_breedtes=[5*cm, PAGE_W - 2*MARGE - 5*cm]))

    story.append(ruimte(0.5))
    story.append(Paragraph("Multi-tenant architectuur", S_H1))
    story.append(hr())
    story.append(Paragraph(
        "Elk restaurant is een eigen 'tenant' in het systeem. Alle data is strikt gescheiden: "
        "een manager van restaurant A ziet nooit data van restaurant B. "
        "De admin kan alle restaurants beheren vanuit één centrale interface.",
        S_BODY))
    story.append(ruimte(0.3))
    story.append(info_box(
        "<b>Wat dit betekent in de praktijk:</b><br/>"
        "Je kunt morgen een tweede restaurant onboarden zonder enige technische aanpassing. "
        "Eigen leveranciers, eigen producten, eigen medewerkers, eigen forecast — "
        "volledig onafhankelijk van alle andere restaurants in het systeem.",
        achtergrond=LICHTGROEN, rand=ACCENTGROEN))

    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════════════════
    # PAGINA 8 — LEERRAPPORT & INVENTARIS
    # ════════════════════════════════════════════════════════════════════════
    story.append(Paragraph("Leerrapport — het systeem wordt slimmer", S_H1))
    story.append(hr())
    story.append(Paragraph(
        "Elke dag dat de manager het werkelijke resultaat invult, leert het systeem. "
        "De correctiefactor per weekdag wordt automatisch toegepast op de volgende forecast. "
        "Na 3 datapunten per weekdag start de automatische correctie.",
        S_BODY))
    story.append(ruimte(0.3))

    leer_rijen = [
        ("Accuraatheid per weekdag",
         "Het leerrapport toont per weekdag de gemiddelde afwijking (%), de absolute fout (%) "
         "en de actieve correctiefactor. Groen = nauwkeurig, rood = systeem leert nog."),
        ("Correctiefactor",
         "Als het systeem structureel te laag of te hoog voorspelt voor een weekdag, "
         "past het de correctiefactor aan. Factor 1.05 = forecast wordt 5% omhoog bijgesteld."),
        ("Verbruikspatronen",
         "Per product: gemiddeld dagverbruik en verbruik per gast, "
         "berekend uit de werkelijke dagresultaten. Helpt bij het verfijnen van de "
         "vraag_per_cover waarden."),
        ("Minimum data",
         "3 gelijke weekdagen zijn nodig om te starten. Het systeem geeft een duidelijke "
         "melding als er te weinig data is voor een betrouwbare forecast."),
    ]
    story.append(feature_tabel(leer_rijen))

    story.append(ruimte(0.5))
    story.append(Paragraph("Inventarisbeheer", S_H1))
    story.append(hr())
    story.append(Paragraph(
        "De inventarispagina geeft een live overzicht van alle voorraden. "
        "Elke aanpassing wordt gelogd in een onveranderlijk audit trail.",
        S_BODY))
    story.append(ruimte(0.3))

    inv_rijen = [
        ("Live voorraad",
         "Actueel overzicht per product: huidige voorraad, status (OK / Laag / Leeg), "
         "kleurgecodeerd. Producten onder minimumvoorraad worden gemarkeerd."),
        ("Handmatige correctie",
         "Manager past voorraad aan met een gestructureerde reden uit een vaste lijst. "
         "Correctie wordt opgeslagen met tijdstip, reden, notitie en wie het deed."),
        ("Audit trail",
         "Elke wijziging is onveranderlijk opgeslagen: was-waarde, nieuwe waarde, delta, "
         "reden, notitie en medewerker. Volledig transparant voor controle en analyse."),
        ("Recente mutaties",
         "Overzicht van de laatste 15 mutaties, direct zichtbaar op de inventarispagina."),
    ]
    story.append(feature_tabel(inv_rijen))

    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════════════════
    # PAGINA 9 — TECHNISCHE ARCHITECTUUR
    # ════════════════════════════════════════════════════════════════════════
    story.append(Paragraph("Technische architectuur", S_H1))
    story.append(hr())
    story.append(Paragraph(
        "De tool is gebouwd op een moderne, cloud-gebaseerde stack. "
        "Geen installatie nodig — werkt in de browser op elke computer of tablet.",
        S_BODY))
    story.append(ruimte(0.3))

    tech_data = [
        [
            Paragraph("Onderdeel", stijl("th", fontName="Helvetica-Bold", fontSize=9,
                                         textColor=WIT)),
            Paragraph("Technologie", stijl("th2", fontName="Helvetica-Bold", fontSize=9,
                                           textColor=WIT)),
            Paragraph("Rol", stijl("th3", fontName="Helvetica-Bold", fontSize=9,
                                   textColor=WIT)),
        ],
        ["Frontend + backend", "Python / Streamlit", "Webinterface, navigatie, sessiebeheer"],
        ["Database", "Supabase (PostgreSQL)", "Alle data: users, tenants, voorraad, correcties, forecast-log"],
        ["Authenticatie", "Supabase Auth + Row Level Security", "Inloggen, sessiebeheer, tenant-isolatie"],
        ["Weerdata", "Open-Meteo API (gratis)", "Dagelijkse weersvoorspelling voor terras-correctie"],
        ["Bestelmail", "mailto: protocol", "Kant-en-klare e-mail naar leverancier"],
        ["Hosting", "Streamlit Cloud", "Gratis tier, altijd online, geen server beheer"],
        ["Dataopslag", "CSV (demo) + Supabase (productie)", "Products.csv voor snelle demo's, database voor live gebruik"],
    ]
    col_w = [(PAGE_W - 2*MARGE) * f for f in [0.25, 0.30, 0.45]]
    tech_tbl = Table(tech_data, colWidths=col_w)
    tech_stijl = [
        ("BACKGROUND",    (0, 0), (-1, 0),  DONKERBLAUW),
        ("TEXTCOLOR",     (0, 0), (-1, 0),  WIT),
        ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, 0),  9),
        ("FONTNAME",      (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",      (0, 1), (-1, -1), 9),
        ("TOPPADDING",    (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [WIT, LICHTGRIJS]),
        ("BOX",           (0, 0), (-1, -1), 0.5, RANDGRIJS),
        ("LINEBELOW",     (0, 0), (-1, -1), 0.3, RANDGRIJS),
        ("TEXTCOLOR",     (0, 1), (-1, -1), colors.HexColor("#374151")),
    ]
    tech_tbl.setStyle(TableStyle(tech_stijl))
    story.append(tech_tbl)

    story.append(ruimte(0.5))
    story.append(Paragraph("Supabase database tabellen", S_H2))
    db_rijen = [
        ("tenants", "Elk restaurant in het systeem. Naam, contactinfo, status."),
        ("users", "Alle gebruikers met rol (admin/manager/user) en granulaire rechtenkolom."),
        ("suppliers", "Leveranciers per tenant: naam, e-mail, leverdagen (7 boolean kolommen), levertijd."),
        ("current_inventory", "Actuele voorraadstand per (tenant, product)."),
        ("inventory_adjustments", "Onveranderlijk audit trail van alle voorraadwijzigingen."),
        ("daily_usage", "Theoretisch verbruik per dag per product — voedt het leermodel."),
        ("closing_log", "Dagresultaten: werkelijke couverts, omzet, event, forecast."),
        ("learning_factors", "Correctiefactoren per weekdag per tenant."),
    ]
    story.append(feature_tabel(db_rijen, kol_breedtes=[4.5*cm, PAGE_W - 2*MARGE - 4.5*cm]))

    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════════════════
    # PAGINA 10 — ROADMAP & AFSLUITING
    # ════════════════════════════════════════════════════════════════════════
    story.append(Paragraph("Wat staat er nog op de roadmap?", S_H1))
    story.append(hr())
    story.append(Paragraph(
        "De huidige versie is volledig functioneel voor dagelijks gebruik. "
        "De volgende fases voegen diepere integraties en automatisering toe.",
        S_BODY))
    story.append(ruimte(0.3))

    roadmap_data = [
        [
            Paragraph("Fase", stijl("rh", fontName="Helvetica-Bold", fontSize=9, textColor=WIT)),
            Paragraph("Wat", stijl("rh2", fontName="Helvetica-Bold", fontSize=9, textColor=WIT)),
            Paragraph("Impact", stijl("rh3", fontName="Helvetica-Bold", fontSize=9, textColor=WIT)),
        ],
        ["Fase 1 (nu live)", "Leveringsschema, drie-laags auth, granulaire rechten, "
         "wizard, verspillingsignalen",
         "Volledige dagelijkse workflow operationeel"],
        ["Fase 2", "Verbeterde forecast: 8-weeks rolling average, feestdagen NL, "
         "regionale correcties (carnaval etc.)",
         "Hogere nauwkeurigheid, minder handmatige aanpassingen"],
        ["Fase 3", "Receptenbeheer + dagimport via kassasysteem (Sitedish API). "
         "Automatische voorraadaftrek na dagafsluiting.",
         "Nul handmatige invoeringen — volledig automatisch"],
        ["Fase 4", "AI-assistent (Claude API): context-aware suggesties per pagina. "
         "Acties/campagnes module.",
         "Systeem denkt mee — proactieve adviezen"],
        ["Fase 5", "Meer kassasystemen (Lightspeed, Mplus, unTill). "
         "Verdere automatisering en integraties.",
         "Breed inzetbaar voor elk type horecabedrijf"],
    ]
    col_w_rm = [(PAGE_W - 2*MARGE) * f for f in [0.18, 0.50, 0.32]]
    rm_tbl = Table(roadmap_data, colWidths=col_w_rm)
    rm_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0),  DONKERBLAUW),
        ("TEXTCOLOR",     (0, 0), (-1, 0),  WIT),
        ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, 0),  9),
        ("FONTNAME",      (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",      (0, 1), (-1, -1), 9),
        ("BACKGROUND",    (0, 1), (-1, 1),  colors.HexColor("#f0fdf4")),
        ("TEXTCOLOR",     (0, 1), (-1, 1),  ACCENTGROEN),
        ("FONTNAME",      (0, 1), (-1, 1),  "Helvetica-Bold"),
        ("ROWBACKGROUNDS",(0, 2), (-1, -1), [WIT, LICHTGRIJS]),
        ("TEXTCOLOR",     (0, 1), (-1, -1), colors.HexColor("#374151")),
        ("TOPPADDING",    (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("BOX",           (0, 0), (-1, -1), 0.5, RANDGRIJS),
        ("LINEBELOW",     (0, 0), (-1, -1), 0.3, RANDGRIJS),
    ]))
    story.append(rm_tbl)

    story.append(ruimte(0.6))
    story.append(hr(kleur=MIDDELBLAUW, dikte=1))
    story.append(ruimte(0.3))

    # Afsluitende pitch
    afsluiting_tbl = Table([[
        Paragraph(
            "<b>Klaar om mee te testen?</b><br/><br/>"
            "De Restaurant Besteltool is momenteel beschikbaar voor een select groep "
            "early adopters. Je krijgt toegang tot de volledige tool, persoonlijke "
            "begeleiding bij de inrichting en directe invloed op de doorontwikkeling.<br/><br/>"
            "Geen installatie, geen contract, geen kosten tijdens de testfase.",
            stijl("af", fontName="Helvetica", fontSize=10, leading=15, textColor=WIT))
    ]], colWidths=[PAGE_W - 2*MARGE])
    afsluiting_tbl.setStyle(TableStyle([
        ("BACKGROUND",   (0,0),(-1,-1), DONKERBLAUW),
        ("TOPPADDING",   (0,0),(-1,-1), 20),
        ("BOTTOMPADDING",(0,0),(-1,-1), 20),
        ("LEFTPADDING",  (0,0),(-1,-1), 20),
        ("RIGHTPADDING", (0,0),(-1,-1), 20),
    ]))
    story.append(afsluiting_tbl)

    story.append(ruimte(0.3))
    story.append(Paragraph(
        "Restaurant Besteltool · Versie 1.0 · Gebouwd voor de Nederlandse horeca",
        S_VOETNOOT))

    # ── Paginanummers ─────────────────────────────────────────────────────
    def voettekst(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(GRIJS)
        canvas.drawCentredString(
            PAGE_W / 2,
            0.7 * cm,
            f"Restaurant Besteltool — Systeemdocumentatie · Pagina {doc.page}"
        )
        canvas.restoreState()

    doc.build(story, onFirstPage=voettekst, onLaterPages=voettekst)
    print(f"PDF aangemaakt: {OUTPUT}")


if __name__ == "__main__":
    bouw_pdf()
