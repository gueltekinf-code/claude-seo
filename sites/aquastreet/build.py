#!/usr/bin/env python3
"""
Static site generator for www.aquastreet.de.

Builds every page of the Aquastreet website into ./dist as plain HTML files
(one folder per page, served as clean URLs), copies hashed CSS/JS, images,
.htaccess, the PHP form handler, robots.txt, sitemap.xml and llms.txt.

All business facts (prices, hours, programs) live in the DATA section below:
change them there and run the build again.

Usage:
    python3 build.py            # build into ./dist
    python3 build.py --out DIR  # build into another folder

Output (JSON on stdout): {"pages": [...], "out": "<dir>", "bytes": <html bytes>}
"""
import argparse
import datetime as dt
import hashlib
import html
import json
import os
import re
import shutil

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = "https://www.aquastreet.de"
TODAY = dt.date.today().isoformat()

# ---------------------------------------------------------------- DATA ----

BIZ = {
    "name": "Aquastreet",
    "legal": "GLT Verwaltungs GmbH",
    "street": "Emmy-Noether-Straße 5",
    "zip": "63755",
    "city": "Alzenau",
    "region": "Bayern",
    "phone_display": "0151 72297295",
    "phone_tel": "+4915172297295",
    "phone_intl": "+49 151 72297295",
    "email": "info@aquastreet.de",
    "instagram": "https://www.instagram.com/aquastreets",
    "tiktok": "https://www.tiktok.com/@aquastreet_alzenau",
    "maps": "https://www.google.com/maps/search/?api=1&query=Aquastreet%2C+Emmy-Noether-Stra%C3%9Fe+5%2C+63755+Alzenau",
}

HOURS = [  # (label, data-day numbers 0=So, value)
    ("Montag – Samstag", "1 2 3 4 5 6", "08:00 – 20:00 Uhr"),
    ("Sonntag", "0", "10:00 – 18:00 Uhr"),
]

PROGRAMS = [
    {
        "id": "expressstreet", "name": "Expressstreet", "price": "12,90", "num": "12.90",
        "tag": "Schnell & gründlich",
        "items": ["Manuelle Vorwäsche", "Aktivschaum (Schmutzlöser)", "Hochdruckwäsche",
                  "Powertrocknung durch 2 Turbogebläse", "Tuchtrocknung mit Aquatextil"],
        "extras": [("Unterbodenkonservierung", "2 €"), ("NANO-Wachsversiegelung", "3 €")],
    },
    {
        "id": "countrystreet", "name": "Countrystreet", "price": "14,90", "num": "14.90",
        "tag": "Mit Felgen- & Intensivwäsche",
        "items": ["Manuelle Vorwäsche", "Aktivschaum (Schmutzlöser)", "Hochdruckwäsche",
                  "Felgengrundreinigung + Intensivschmutzlöser", "Intensivwäsche mit Sensorfil-Textilbürsten",
                  "Powertrocknung durch 2 Turbogebläse", "Tuchtrocknung mit Aquatextil"],
        "extras": [("Unterbodenkonservierung", "2 €"), ("NANO-Wachsversiegelung", "3 €")],
    },
    {
        "id": "highwaystreet", "name": "Highwaystreet", "price": "16,90", "num": "16.90",
        "tag": "Wachs & Hochglanz",
        "items": ["Manuelle Vorwäsche", "Foam-Splash (Schaumwand)", "Hochdruckwäsche",
                  "Felgengrundreinigung + Intensivschmutzlöser", "Intensivwäsche mit Sensorfil-Textilbürsten",
                  "NANO-Wachsversiegelung", "Hochglanzpolitur", "Powertrocknung durch 2 Turbogebläse",
                  "Textiltrocknung mit Seitenbürsten (lackschonend)", "Tuchtrocknung mit Aquatextil"],
        "extras": [("Unterbodenkonservierung", "2 €")],
    },
    {
        "id": "aquastreet", "name": "Aquastreet", "price": "19,90", "num": "19.90",
        "tag": "Das volle Programm", "top": True,
        "items": ["Manuelle Vorwäsche", "Foam-Splash (Schaumwand) + Hochdruckwäsche", "Unterbodenkonservierung",
                  "Felgengrundreinigung + Intensivschmutzlöser", "Hyperjet-Hochdruckfelgenreinigung",
                  "Intensivwäsche mit Sensorfil-Textilbürsten", "NANO-Wachsversiegelung", "Hochglanzpolitur",
                  "Trocknungswachs (Trocknungshilfe)", "Osmosespülung (kalkfrei)",
                  "Powertrocknung durch 2 Turbogebläse", "Textiltrocknung mit Seitenbürsten (lackschonend)",
                  "Tuchtrocknung mit Aquatextil"],
        "extras": [],
    },
]

# Feature matrix for the comparison table: (label, [express, country, highway, aquastreet])
MATRIX = [
    ("Manuelle Vorwäsche", [1, 1, 1, 1]),
    ("Aktivschaum / Foam-Splash-Schaumwand", [1, 1, 1, 1]),
    ("Hochdruckwäsche", [1, 1, 1, 1]),
    ("Felgengrundreinigung + Intensivschmutzlöser", [0, 1, 1, 1]),
    ("Intensivwäsche mit Sensorfil-Textilbürsten", [0, 1, 1, 1]),
    ("Hyperjet-Hochdruckfelgenreinigung", [0, 0, 0, 1]),
    ("NANO-Wachsversiegelung", ["+3 €", "+3 €", 1, 1]),
    ("Hochglanzpolitur", [0, 0, 1, 1]),
    ("Unterbodenkonservierung", ["+2 €", "+2 €", "+2 €", 1]),
    ("Trocknungswachs", [0, 0, 0, 1]),
    ("Osmosespülung (kalkfrei)", [0, 0, 0, 1]),
    ("Powertrocknung (2 Turbogebläse)", [1, 1, 1, 1]),
    ("Textiltrocknung mit Seitenbürsten", [0, 0, 1, 1]),
    ("Tuchtrocknung mit Aquatextil", [1, 1, 1, 1]),
]

SENIOR = [("Aquastreet", "19,90", "16,90"), ("Highwaystreet", "16,90", "13,90"),
          ("Countrystreet", "14,90", "11,90"), ("Expressstreet", "12,90", "9,90")]

INTERIOR_ITEMS = ["Innen- und Kofferraum saugen", "Innen- und Kofferraum mit speziellen Reinigungsmitteln säubern",
                  "Alle Ablageflächen", "Türfalze", "Innere Tankdeckelverkleidung", "Scheibenreinigung",
                  "Geruchsbekämpfung"]

DETAILING = [("Express-Innenreinigung", "40 €"), ("Lederreinigung", "20 € pro Sitz"),
             ("Polsterreinigung", "20 € pro Sitz"), ("Motorraumreinigung", "ab 60 €"),
             ("Cabrio-Verdeck: Imprägnierung / Versiegelung", "ab 70 €"), ("Politur", "ab 150 €"),
             ("Wachsversiegelung", "ab 350 €"), ("Keramikversiegelung", "ab 500 €"),
             ("Graphenversiegelung", "ab 500 €")]

PRODUCTS = [("produkt-aquapremium", "Aquapremium-Tuch", "9,90 €"), ("produkt-handschuh", "Waschhandschuh", "7,90 €"),
            ("produkt-leder", "Ledertuch", "4,90 €"), ("produkt-powertuch", "Powertuch", "3,90 €"),
            ("produkt-mikrofaser", "Mikrofaser-Trocknungstuch", "2,90 €"), ("produkt-baklava", "Baklava-Tuch", "1,90 €")]

GIFTS = [("100 €", "Baklava-Tuch"), ("200 €", "Powertuch oder Mikrofasertuch"),
         ("300 €", "Waschhandschuh oder Aquapremium-Tuch")]

FAQ_HOME = [
    ("Brauche ich einen Termin?",
     "Nein. Waschstraße, SB-Boxen, Staubsauger und Express-Innenreinigung nutzen Sie ohne Termin. Kommen Sie einfach vorbei."),
    ("Wann hat die Waschstraße geöffnet?",
     "Montag bis Samstag von 8 bis 20 Uhr, sonntags von 10 bis 18 Uhr. SB-Boxen und Staubsaugerplätze sind rund um die Uhr nutzbar."),
    ("Was kostet eine Autowäsche?",
     "Die Programme kosten zwischen 12,90 € (Expressstreet) und 19,90 € (Aquastreet, das volle Programm). Mit der Kundenkarte sparen Sie zusätzlich."),
    ("Passt mein Fahrzeug in die Waschstraße?",
     "Ihr Fahrzeug darf höchstens 2,05 m hoch und 2,40 m breit sein und braucht mindestens 8 cm Bodenfreiheit. Bei überstehendem Felgenkranz können Schäden entstehen."),
    ("Kann ich nach der Wäsche saugen?",
     "Ja. Kunden der Waschstraße saugen bis zu 4 Minuten kostenlos. Insgesamt stehen 10 Staubsaugerplätze zur Verfügung."),
    ("Kann ich mit DKV- oder UTA-Karte bezahlen?",
     "Ja. An der Kasse der Waschstraße akzeptieren wir DKV und UTA für Waschleistungen, unsere Pflegeprodukte und den Kauf von Jetons."),
]

FAQ_ABOUT = [
    ("Wo befindet sich Aquastreet?",
     "Aquastreet befindet sich in der Emmy-Noether-Straße 5 in 63755 Alzenau."),
    ("Wie beantrage ich eine Kundenkarte?",
     "Direkt an der Kasse (Sie nehmen die Karte sofort mit) oder online über unser Formular. Online beantragte Karten liegen am nächsten Tag zur Abholung bereit. Bei der Abholung wird die Karte aufgeladen."),
    ("Was macht Aquastreet umweltfreundlich?",
     "Wasserrückgewinnung, eine fachgerechte Abwasserbehandlung, damit keine Chemikalien in die Umwelt gelangen, zielgenau dosierte Reinigungsmittel und energieeffiziente Technik."),
    ("Wie erreiche ich Aquastreet bei Fragen?",
     "Per E-Mail an info@aquastreet.de, telefonisch unter 0151 72297295, über unser Kontaktformular oder direkt vor Ort."),
]

FAQ_FIRMEN = [
    ("Wie viel spart ein Unternehmen mit der Firmenkarte?",
     "Bis zu 20 % bei jeder Wäsche. Die Höhe des Rabatts hängt vom aufgeladenen Betrag ab: Je mehr Sie aufladen, desto mehr sparen Sie."),
    ("Bekommen wir eine Übersicht über alle Fahrzeuge?",
     "Ja. Firmenkunden erhalten einen monatlichen Leistungsbericht mit einer Zusammenfassung aller Fahrzeuge – praktisch für Buchhaltung und Fuhrparkverwaltung."),
    ("Können unsere Fahrer mit Tankkarte bezahlen?",
     "Ja. An der Kasse der Waschstraße akzeptieren wir DKV- und UTA-Karten für Waschleistungen, Pflegeprodukte und Jetons für die SB-Boxen."),
    ("Wie beantragen wir die Firmenkarte?",
     "Online über das Antragsformular oder direkt an der Kasse. Online beantragte Karten liegen am nächsten Tag zur Abholung bereit; bei der Abholung wird die Karte aufgeladen. Die einmalige Gebühr beträgt 2 €."),
    ("Welche Fahrzeuge passen in die Waschstraße?",
     "Fahrzeuge bis 2,05 m Höhe und 2,40 m Breite mit mindestens 8 cm Bodenfreiheit. Größere Transporter können die SB-Boxen nutzen – sprechen Sie uns im Zweifel an."),
]

NAV = [("/waschstrasse/", "Waschstraße & Preise"), ("/sb-waschen/", "SB-Waschen"),
       ("/innenreinigung/", "Innenreinigung"), ("/firmenkunden/", "Firmenkunden"),
       ("/aktionen/", "Aktionen"), ("/kontakt/", "Kontakt")]

# --------------------------------------------------------------- ICONS ----

def ico(name):
    p = {
        "check": '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
        "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
        "pin": '<path d="M12 21s-7-6.2-7-11.5A7 7 0 0 1 19 9.5C19 14.8 12 21 12 21z"/><circle cx="12" cy="9.5" r="2.5"/>',
        "phone": '<path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2z"/>',
        "mail": '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 7l9 6 9-6"/>',
        "drop": '<path d="M12 3s6 6.4 6 11a6 6 0 0 1-12 0c0-4.6 6-11 6-11z"/>',
        "leaf": '<path d="M5 19c0-9 6-14 15-14 0 9-5 15-14 15"/><path d="M5 19l7-7"/>',
        "spark": '<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z"/><path d="M19 16l.7 1.8 1.8.7-1.8.7L19 21l-.7-1.8-1.8-.7 1.8-.7z"/>',
        "car": '<path d="M5 16V11l2-5h10l2 5v5"/><path d="M3 16h18v3H3z"/><circle cx="7.5" cy="13" r=".8"/><circle cx="16.5" cy="13" r=".8"/>',
        "card": '<rect x="2.5" y="5" width="19" height="14" rx="2.5"/><path d="M2.5 10h19M6.5 15h4"/>',
        "shield": '<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/><path d="M8.5 12l2.5 2.5 4.5-5"/>',
        "wind": '<path d="M3 9h11a3 3 0 1 0-3-3M3 15h15a3 3 0 1 1-3 3M3 12h8"/>',
        "calendar": '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4M9 15l6 0"/>',
        "building": '<path d="M4 21V5l8-2v18M12 8l8 2v11M3 21h18M8 9v.01M8 13v.01M8 17v.01M16 13v.01M16 17v.01"/>',
        "gauge": '<path d="M4 18a8 8 0 1 1 16 0"/><path d="M12 18l4-6"/>',
        "gift": '<rect x="3" y="8" width="18" height="5" rx="1"/><path d="M5 13v8h14v-8M12 8v13M12 8S10.5 3 8 4.5 9.5 8 12 8zm0 0s1.5-5 4-3.5S14.5 8 12 8z"/>',
        "arrow": '<path d="M5 12h14M13 6l6 6-6 6"/>',
        "menu": '<path d="M4 7h16M4 12h16M4 17h16"/>',
        "seat": '<path d="M7 3h6l1 9H8z"/><path d="M8 12l-2 6h11l1-6M6 18v3M17 18v3"/>',
        "route": '<circle cx="6" cy="19" r="2"/><circle cx="18" cy="5" r="2"/><path d="M8 19h7a3.5 3.5 0 0 0 0-7H9a3.5 3.5 0 0 1 0-7h7"/>',
        "instagram": '<rect x="3" y="3" width="18" height="18" rx="5"/><circle cx="12" cy="12" r="4"/><path d="M17.5 6.5v.01"/>',
        "tiktok": '<path d="M14 3v11.5a3.5 3.5 0 1 1-3.5-3.5"/><path d="M14 3c.5 2.8 2.3 4.5 5 4.8"/>',
        "chart": '<path d="M4 20V4M4 20h16M8 16v-4M12 16V8M16 16v-6"/>',
    }[name]
    return (f'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">{p}</svg>')


# -------------------------------------------------------------- HELPERS ---

E = html.escape
ASSET = {}  # logical name -> hashed path


def pic(name, alt, sizes="(max-width: 860px) 100vw, 50vw", cls="", eager=False):
    """Responsive <img> from assets/img/<name>-<w>.webp with intrinsic size."""
    d = os.path.join(HERE, "assets", "img")
    widths = sorted(int(f[len(name) + 1:-5]) for f in os.listdir(d)
                    if f.startswith(name + "-") and f.endswith(".webp") and f[len(name) + 1:-5].isdigit())
    if not widths:
        raise SystemExit(f"missing image {name}")
    big = widths[-1]
    w, h = Image.open(os.path.join(d, f"{name}-{big}.webp")).size
    mid = [x for x in widths if x <= 1024][-1]
    srcset = ", ".join(f"/img/{name}-{x}.webp {x}w" for x in widths)
    load = 'fetchpriority="high" decoding="async"' if eager else 'loading="lazy" decoding="async"'
    c = f' class="{cls}"' if cls else ""
    return (f'<img src="/img/{name}-{mid}.webp" srcset="{srcset}" sizes="{sizes}" '
            f'width="{w}" height="{h}" alt="{E(alt)}" {load}{c}>')


def checks(items, cls="checks"):
    return f'<ul class="{cls}">' + "".join(f"<li>{i}</li>" for i in items) + "</ul>"


def ld(obj):
    return ('<script type="application/ld+json">' +
            json.dumps(obj, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/") + "</script>")


def crumbs_ld(trail):
    return {"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "name": n, "item": SITE + u} for i, (u, n) in enumerate(trail)]}


def crumbs_html(trail):
    li = []
    for i, (u, n) in enumerate(trail):
        if i == len(trail) - 1:
            li.append(f'<li><span aria-current="page">{E(n)}</span></li>')
        else:
            li.append(f'<li><a href="{u}">{E(n)}</a></li>')
    return f'<nav class="crumbs" aria-label="Brotkrumen"><ol>{"".join(li)}</ol></nav>'


def page_hero(trail, eyebrow, h1, lead):
    return f"""<section class="page-hero"><div class="wrap">
{crumbs_html(trail)}
<span class="eyebrow">{eyebrow}</span>
<h1>{h1}</h1>
<p class="lead">{lead}</p>
</div></section>"""


def hours_table():
    rows = "".join(f'<tr data-day="{d}"><th scope="row">Waschstraße<br><span class="muted">{l}</span></th><td>{v}</td></tr>' for l, d, v in HOURS)
    return f"""<table class="hours"><caption class="sr-only">Öffnungszeiten</caption><tbody>
{rows}
<tr><th scope="row">Express-Innenreinigung</th><td>Mo – Sa 09:00 – 19:00 Uhr</td></tr>
<tr><th scope="row">SB-Boxen &amp; Staubsauger</th><td>24 Stunden, 7 Tage</td></tr>
</tbody></table>"""


def plan_card(p, compact=False):
    badge = '<span class="plan__badge">Bestseller</span>' if p.get("top") else ""
    items = p["items"] if not compact else p["items"][:5] + ([f"+ {len(p['items']) - 5} weitere Leistungen"] if len(p["items"]) > 5 else [])
    extras = ""
    if p["extras"] and not compact:
        extras = '<div class="plan__extras">Extras: ' + " · ".join(f"{n} <b>{v}</b>" for n, v in p["extras"]) + "</div>"
    return f"""<article class="plan{' plan--top' if p.get('top') else ''}" id="{p['id']}">{badge}
<h3>{p['name']}</h3><p class="plan__tag">{p['tag']}</p>
<p class="plan__price">{p['price']} <small>€</small></p>
{checks(items)}{extras}</article>"""


def location_block():
    return f"""<div class="location">
<div class="location__map">
<svg class="bg" viewBox="0 0 600 400" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#13203a"/><stop offset="1" stop-color="#0a1324"/></linearGradient></defs>
<rect width="600" height="400" fill="url(#g)"/>
<g stroke="#1f3358" stroke-width="14" fill="none" stroke-linecap="round"><path d="M-20 300 C 150 260 260 330 620 250"/><path d="M180 -20 C 200 120 160 260 230 420"/><path d="M380 -20 L 420 420"/></g>
<g stroke="#2a4473" stroke-width="5" fill="none"><path d="M-20 120 L 620 160"/><path d="M60 -20 L 120 420"/><path d="M520 -20 C 480 160 560 260 500 420"/></g>
<circle cx="405" cy="170" r="46" fill="#22b8e8" opacity=".18"/><circle cx="405" cy="170" r="24" fill="#22b8e8" opacity=".35"/>
<path d="M405 186s-15-13-15-25a15 15 0 0 1 30 0c0 12-15 25-15 25z" fill="#22b8e8"/><circle cx="405" cy="161" r="5.5" fill="#0a1324"/>
</svg>
<div><address>Aquastreet<br>{BIZ['street']}<br>{BIZ['zip']} {BIZ['city']}</address>
<a class="btn btn--light" href="{BIZ['maps']}" rel="noopener" target="_blank">{ico('route')} Route planen</a></div>
</div>
<div class="location__info">
<h3>Öffnungszeiten</h3>
<p><span class="status" data-status>Öffnungszeiten</span></p>
{hours_table()}
<div class="btn-row mt-2"><a class="btn btn--outline" href="tel:{BIZ['phone_tel']}">{ico('phone')} {BIZ['phone_display']}</a>
<a class="btn btn--outline" href="mailto:{BIZ['email']}">{ico('mail')} E-Mail</a></div>
</div></div>"""


def faq_block(items):
    out = "".join(f"<details><summary>{E(q)}</summary><div><p>{E(a)}</p></div></details>" for q, a in items)
    return f'<div class="faq">{out}</div>'


def faq_ld(items):
    return {"@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in items]}


def cta(title="Kommen Sie vorbei – ganz ohne Termin.",
        text="Mitten in Alzenau, direkt an der Emmy-Noether-Straße. Waschstraße täglich geöffnet, SB-Boxen rund um die Uhr."):
    return f"""<section class="section"><div class="wrap"><div class="cta">
<h2>{title}</h2><p>{text}</p>
<div class="btn-row"><a class="btn btn--light" href="{BIZ['maps']}" rel="noopener" target="_blank">{ico('route')} Route planen</a>
<a class="btn btn--ghost" href="/kundenkarte/">{ico('card')} Kundenkarte beantragen</a></div>
</div></div></section>"""


DIM_SVG = {
    "h": '<svg viewBox="0 0 64 64" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14 46V32l5-10h20l6 10v14"/><path d="M10 46h44"/><path d="M56 12v34M52 16l4-4 4 4M52 42l4 4 4-4"/></svg>',
    "b": '<svg viewBox="0 0 64 64" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="16" y="18" width="32" height="26" rx="6"/><path d="M22 44v6M42 44v6M16 30h32"/><path d="M8 56h48M12 52l-4 4 4 4M52 52l4 4-4 4"/></svg>',
    "c": '<svg viewBox="0 0 64 64" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M8 36l6-12h34l8 12v8H8z"/><circle cx="18" cy="44" r="5"/><circle cx="46" cy="44" r="5"/><path d="M4 58h56M32 49v9M29 52l3-3 3 3M29 55l3 3 3-3"/></svg>',
}


def dims_block():
    return f"""<div class="dims">
<div class="dim">{DIM_SVG['h']}<strong>max. 2,05 m</strong><span>Durchfahrtshöhe</span></div>
<div class="dim">{DIM_SVG['b']}<strong>max. 2,40 m</strong><span>Durchfahrtsbreite</span></div>
<div class="dim">{DIM_SVG['c']}<strong>min. 8 cm</strong><span>Bodenfreiheit</span></div>
</div>
<p class="note">Bei überstehendem Felgenkranz können Beschädigungen auftreten. Einige Fahrzeuge sind von der Haftung ausgeschlossen oder können nicht in der Waschstraße gewaschen werden – fragen Sie im Zweifel vor Ort nach.</p>"""


# --------------------------------------------------------------- LAYOUT ---

def business_ld(full=True):
    o = {
        "@type": "AutoWash", "@id": SITE + "/#business", "name": BIZ["name"],
        "legalName": BIZ["legal"], "url": SITE + "/", "logo": SITE + "/img/logo.png",
        "image": [SITE + "/img/og-aquastreet.jpg", SITE + "/img/waschstrasse-schaumvorhang-1440.webp"],
        "telephone": BIZ["phone_intl"], "email": BIZ["email"],
        "address": {"@type": "PostalAddress", "streetAddress": BIZ["street"], "postalCode": BIZ["zip"],
                    "addressLocality": BIZ["city"], "addressRegion": BIZ["region"], "addressCountry": "DE"},
        "hasMap": BIZ["maps"],
        "openingHoursSpecification": [
            {"@type": "OpeningHoursSpecification",
             "dayOfWeek": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
             "opens": "08:00", "closes": "20:00"},
            {"@type": "OpeningHoursSpecification", "dayOfWeek": "Sunday", "opens": "10:00", "closes": "18:00"}],
        "priceRange": "12,90 € – 19,90 €",
        "paymentAccepted": "DKV-Karte, UTA-Karte, Aquastreet-Kundenkarte",
        "sameAs": [BIZ["instagram"], BIZ["tiktok"]],
        "areaServed": [{"@type": "City", "name": c} for c in ["Alzenau", "Hanau", "Aschaffenburg", "Frankfurt am Main"]],
    }
    if full:
        o["description"] = ("Waschpark in Alzenau mit 30-Meter-Waschstraße, 4 SB-Waschboxen, 10 Staubsaugerplätzen, "
                            "Express-Innenreinigung und Fahrzeugaufbereitung. Ohne Termin.")
        o["amenityFeature"] = [{"@type": "LocationFeatureSpecification", "name": n, "value": True} for n in
                               ["SB-Waschboxen 24/7", "Staubsaugerplätze 24/7", "Mattenreiniger", "Express-Innenreinigung"]]
        o["hasOfferCatalog"] = {"@type": "OfferCatalog", "name": "Waschprogramme", "itemListElement": [
            {"@type": "Offer", "name": p["name"], "price": p["num"], "priceCurrency": "EUR",
             "url": f"{SITE}/waschstrasse/#{p['id']}",
             "itemOffered": {"@type": "Service", "name": f"Autowäsche {p['name']}"}} for p in PROGRAMS]}
    return o


def layout(path, title, desc, body, schema=(), og_image="/img/og-aquastreet.jpg", preload=None, noindex=False):
    url = SITE + path
    cur = ' aria-current="page"'
    nav = "".join(f'<a href="{u}"{cur if path.startswith(u) else ""}>{n}</a>' for u, n in NAV)
    graph = [{"@type": "WebSite", "@id": SITE + "/#website", "url": SITE + "/", "name": "Aquastreet",
              "inLanguage": "de-DE", "publisher": {"@id": SITE + "/#business"}}] if path == "/" else []
    graph += list(schema)
    schema_html = ld({"@context": "https://schema.org", "@graph": graph}) if graph else ""
    pre = ""
    if preload:
        pre = f'<link rel="preload" as="image" type="image/webp" imagesrcset="{preload[0]}" imagesizes="{preload[1]}" fetchpriority="high">'
    robots = '<meta name="robots" content="noindex, follow">' if noindex else '<meta name="robots" content="index, follow, max-image-preview:large">'
    return f"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{E(title)}</title>
<meta name="description" content="{E(desc)}">
{robots}
<link rel="canonical" href="{url}">
<link rel="stylesheet" href="{ASSET['css']}">
{pre}
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="icon" href="/favicon-32.png" sizes="32x32" type="image/png">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="manifest" href="/site.webmanifest">
<meta name="theme-color" content="#0a1324">
<meta property="og:type" content="website">
<meta property="og:locale" content="de_DE">
<meta property="og:site_name" content="Aquastreet">
<meta property="og:title" content="{E(title)}">
<meta property="og:description" content="{E(desc)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{SITE}{og_image}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="geo.region" content="DE-BY">
<meta name="geo.placename" content="Alzenau">
{schema_html}
<script src="{ASSET['js']}" defer></script>
</head>
<body>
<a class="skip" href="#inhalt">Zum Inhalt springen</a>
<div class="topbar"><div class="wrap">
<div class="topbar__info"><span class="status" data-status>Mo – Sa 8 – 20 Uhr · So 10 – 18 Uhr</span>
<span class="topbar__hide-sm">SB-Boxen &amp; Staubsauger 24/7</span></div>
<div class="topbar__info"><a href="tel:{BIZ['phone_tel']}">{BIZ['phone_display']}</a><a class="topbar__mail" href="mailto:{BIZ['email']}">{BIZ['email']}</a></div>
</div></div>
<header class="header"><div class="wrap">
<a class="logo" href="/" aria-label="Aquastreet – zur Startseite"><img src="/img/logo-172.webp" srcset="/img/logo-172.webp 172w, /img/logo-344.webp 344w" sizes="172px" width="172" height="48" alt="Aquastreet – Gut für dein Auto, besser für die Umwelt"></a>
<button class="nav-toggle" type="button" aria-expanded="false" aria-controls="nav"><span class="sr-only">Menü</span>{ico('menu')}</button>
<nav class="nav" id="nav" aria-label="Hauptnavigation">{nav}<a class="btn btn--primary" href="/kundenkarte/">Kundenkarte</a></nav>
</div></header>
<main id="inhalt">
{body}
</main>
<footer class="footer"><div class="wrap">
<div class="footer__grid">
<div><a class="footer__logo" href="/"><img src="/img/logo-344.webp" width="172" height="48" alt="Aquastreet" loading="lazy"></a>
<p>Waschstraße, SB-Waschboxen, Staubsauger und Innenreinigung in Alzenau. Gut für dein Auto, besser für die Umwelt.</p>
<div class="social"><a href="{BIZ['instagram']}" rel="noopener" target="_blank" aria-label="Aquastreet auf Instagram">{ico('instagram')}</a>
<a href="{BIZ['tiktok']}" rel="noopener" target="_blank" aria-label="Aquastreet auf TikTok">{ico('tiktok')}</a></div></div>
<div><h2>Leistungen</h2><ul>
<li><a href="/waschstrasse/">Waschstraße &amp; Preise</a></li><li><a href="/sb-waschen/">SB-Waschen &amp; Saugen</a></li>
<li><a href="/innenreinigung/">Innenreinigung &amp; Aufbereitung</a></li><li><a href="/firmenkunden/">Firmenkunden &amp; Flotten</a></li></ul></div>
<div><h2>Aquastreet</h2><ul>
<li><a href="/kundenkarte/">Kundenkarte</a></li><li><a href="/aktionen/">Aktionen</a></li>
<li><a href="/ueber-uns/">Über uns</a></li><li><a href="/kontakt/">Kontakt &amp; Anfahrt</a></li></ul></div>
<div><h2>Kontakt</h2><address>Aquastreet<br>{BIZ['street']}<br>{BIZ['zip']} {BIZ['city']}</address>
<ul class="mt-1"><li><a href="tel:{BIZ['phone_tel']}">{BIZ['phone_display']}</a></li><li><a href="mailto:{BIZ['email']}">{BIZ['email']}</a></li></ul>
<p class="mt-1">Mo – Sa 8 – 20 Uhr<br>So 10 – 18 Uhr<br>SB 24/7</p></div>
</div>
<div class="footer__bottom"><span>© {dt.date.today().year} {BIZ['legal']} · Aquastreet</span>
<span><a href="/impressum/">Impressum</a> · <a href="/datenschutz/">Datenschutz</a></span></div>
</div></footer>
<div class="actionbar"><a class="btn btn--outline" href="tel:{BIZ['phone_tel']}">{ico('phone')} Anrufen</a>
<a class="btn btn--primary" href="{BIZ['maps']}" rel="noopener" target="_blank">{ico('route')} Route</a></div>
</body>
</html>
"""


# ---------------------------------------------------------------- PAGES ---

def home():
    hero_sizes = "100vw"
    hero = pic("hero-schaumwaesche", "Auto im Aktivschaum in der Aquastreet Waschstraße in Alzenau", hero_sizes, eager=True)
    srcset = hero.split('srcset="')[1].split('"')[0]
    services = [
        ("/waschstrasse/", "waschstrasse-schaumvorhang", "Waschstraße in Alzenau mit Schaumvorhang",
         "Ab 12,90 €", "Waschstraße", "30 Meter moderne Waschtechnik, vier Programme – von der schnellen Wäsche bis zur Osmosespülung."),
        ("/sb-waschen/", "sb-box-hochdruck", "Hochdruckreinigung in der SB-Waschbox",
         "24/7 geöffnet", "SB-Waschen & Saugen", "4 SB-Boxen mit 7 Programmen, 10 Staubsaugerplätze und Mattenreiniger – rund um die Uhr."),
        ("/innenreinigung/", "innenraum-leder", "Gereinigter Innenraum mit Ledersitzen",
         "Express ab 40 €", "Innenreinigung", "Saugen, Ablageflächen, Türfalze, Scheiben, Geruchsbekämpfung – direkt nach der Wäsche, ohne Termin."),
        ("/innenreinigung/#aufbereitung", "aufbereitung-politur", "Politur einer Motorhaube bei der Fahrzeugaufbereitung",
         "Ab 20 €", "Aufbereitung & Detailing", "Leder- und Polsterreinigung, Politur, Wachs-, Keramik- und Graphenversiegelung."),
    ]
    cards = "".join(f"""<article class="card card--link">{pic(img, alt, "(max-width: 600px) 100vw, (max-width: 1100px) 50vw, 25vw")}
<div class="card__body"><p class="card__meta">{meta}</p><h3><a class="stretched" href="{u}">{t}</a></h3><p>{d}</p>
<span class="card__more" aria-hidden="true">Mehr erfahren {ico('arrow')}</span></div></article>""" for u, img, alt, meta, t, d in services)
    plans = "".join(plan_card(p, compact=True) for p in PROGRAMS)
    products = "".join(f'<div class="product">{pic(n, t, "(max-width: 600px) 50vw, 16vw")}<div><span>{t}</span><b>{pr}</b></div></div>' for n, t, pr in PRODUCTS)
    body = f"""
<section class="hero">
<div class="hero__img">{hero}</div>
<div class="wrap">
<span class="eyebrow">Waschpark Alzenau · ohne Termin</span>
<h1>Ihre Waschstraße in Alzenau. <span>Glänzend in wenigen Minuten.</span></h1>
<p>Moderne 30-Meter-Waschstraße, SB-Waschboxen rund um die Uhr und Innenreinigung mit Liebe zum Detail – schonend für Ihr Auto und die Umwelt.</p>
<div class="btn-row"><a class="btn btn--primary" href="/waschstrasse/">Programme &amp; Preise {ico('arrow')}</a>
<a class="btn btn--ghost" href="{BIZ['maps']}" rel="noopener" target="_blank">{ico('route')} Route planen</a></div>
<ul class="chips">
<li>{ico('check')} Ohne Termin</li><li>{ico('check')} Programme ab 12,90 €</li>
<li>{ico('check')} SB-Boxen 24/7</li><li>{ico('check')} 4 Min. gratis saugen</li></ul>
</div></section>

<section class="section"><div class="wrap">
<div class="head"><span class="eyebrow">Unsere Leistungen</span>
<h2>Alles für Ihr Auto – an einem Ort.</h2>
<p class="lead">Ob schnelle Wäsche auf dem Heimweg, gründliche Selbstbedienung am Wochenende oder eine Aufbereitung, nach der Ihr Auto wie neu aussieht.</p></div>
<div class="grid grid--4">{cards}</div>
</div></section>

<section class="section section--tint" aria-labelledby="preise"><div class="wrap">
<div class="head head--center"><span class="eyebrow">Waschstraße</span>
<h2 id="preise">Vier Programme. Ein Anspruch: sauber bis ins Detail.</h2>
<p class="lead">Jede Wäsche startet mit manueller Vorwäsche – auch im günstigsten Programm.</p></div>
<div class="plans">{plans}</div>
<p class="center mt-2"><a class="btn btn--outline" href="/waschstrasse/">Alle Leistungen im Vergleich {ico('arrow')}</a></p>
</div></section>

<section class="section section--dark"><div class="wrap">
<div class="split">
<div><span class="eyebrow">Gut für dein Auto, besser für die Umwelt</span>
<h2>Moderne Technik, die Wasser spart und Lack schont.</h2>
<p class="lead">Wasserrückgewinnung, fachgerechte Abwasserbehandlung und zielgenau dosierte Reinigungsmittel: So wird Ihr Auto gründlich sauber, ohne die Umwelt unnötig zu belasten.</p>
{checks(["Wasserrückgewinnung und Einsparsysteme", "Abwasserbehandlung – keine Chemikalien in die Umwelt", "Lackschonende Sensorfil-Textilbürsten", "Regelmäßige Wartung aller Anlagen"])}
</div>
<div class="split__media">{pic("waschstrasse-buersten", "Textilbürsten der Waschstraße mit beleuchtetem Fahrzeug")}</div>
</div>
<div class="stats mt-3"><div><strong>30 m</strong><span>Waschstraße</span></div><div><strong>4</strong><span>SB-Waschboxen</span></div>
<div><strong>7</strong><span>SB-Programme</span></div><div><strong>10</strong><span>Staubsaugerplätze</span></div></div>
</div></section>

<section class="section"><div class="wrap">
<div class="split">
<div class="split__media">{pic("kundenkarte-cabrio", "Zufriedene Fahrerin im frisch gewaschenen Cabrio")}
<div class="split__badge"><div>{ico('card')}</div><div><strong>bis 20 %</strong><span>sparen mit der Karte</span></div></div></div>
<div><span class="eyebrow">Aquastreet-Kundenkarte</span>
<h2>Bei jeder Wäsche sparen.</h2>
<p class="lead">Aufladen, bargeldlos bezahlen und bei jeder Wäsche sparen – in der Waschstraße und an den SB-Boxen.</p>
{checks(["Privatkarte: bis zu 15 % sparen", "Firmenkarte: bis zu 20 % sparen – mit monatlichem Leistungsbericht", "Geschenk bei der ersten Aufladung ab 100 €", "Einmalige Gebühr: nur 2 €"])}
<div class="btn-row"><a class="btn btn--primary" href="/kundenkarte/">Karte beantragen {ico('arrow')}</a>
<a class="btn btn--outline" href="/firmenkunden/">Für Firmen</a></div>
</div></div>
</div></section>

<section class="section section--tint"><div class="wrap">
<div class="split split--rev">
<div><span class="eyebrow">Jeden Montag</span>
<h2>Seniorentag: bis zu 3 € sparen.</h2>
<p class="lead">Montags, den ganzen Tag: alle vier Waschprogramme günstiger für Seniorinnen und Senioren – einfach den Seniorenausweis an der Kasse zeigen.</p>
<p><a class="btn btn--primary" href="/aktionen/">Zu den Aktionen {ico('arrow')}</a></p></div>
<div class="split__media">{pic("aktion-seniorentag-preise", "Seniorentag bei Aquastreet: alle Programme jeden Montag günstiger")}</div>
</div></div></section>

<section class="section"><div class="wrap">
<div class="head head--center"><span class="eyebrow">Bevor Sie einfahren</span>
<h2>Passt Ihr Fahrzeug in die Waschstraße?</h2></div>
{dims_block()}
</div></section>

<section class="section section--tint"><div class="wrap">
<div class="head"><span class="eyebrow">An der Kasse erhältlich</span>
<h2>Profi-Pflege für zu Hause.</h2>
<p class="lead">Unsere Tücher und Waschhandschuhe – ideal für die SB-Wäsche und die Pflege zwischendurch.</p></div>
<div class="products">{products}</div>
</div></section>

<section class="section"><div class="wrap">
<div class="head"><span class="eyebrow">Standort</span><h2>Zentral in Alzenau.</h2>
<p class="lead">Schnell erreichbar aus Alzenau, Hanau, Aschaffenburg und dem Kahlgrund.</p></div>
{location_block()}
</div></section>

<section class="section section--tint"><div class="wrap">
<div class="head"><span class="eyebrow">Häufige Fragen</span><h2>Gut zu wissen</h2></div>
{faq_block(FAQ_HOME)}
</div></section>
{cta()}"""
    return layout("/", "Waschstraße Alzenau – Aquastreet Waschpark | SB-Boxen 24/7",
                  "Moderne 30-m-Waschstraße, 4 SB-Boxen & 10 Staubsauger in Alzenau. Ohne Termin, Mo–Sa 8–20 Uhr, So 10–18 Uhr. Programme ab 12,90 €.",
                  body, [business_ld(), faq_ld(FAQ_HOME)], preload=(srcset, hero_sizes))


def waschstrasse():
    trail = [("/", "Startseite"), ("/waschstrasse/", "Waschstraße & Preise")]
    plans = "".join(plan_card(p) for p in PROGRAMS)
    head = "".join(f'<th scope="col" class="c">{p["name"]}<br><span class="muted">{p["price"]} €</span></th>' for p in PROGRAMS)

    def cell(v):
        if v == 1:
            return '<td class="c"><span class="yes" aria-label="inklusive">✓</span></td>'
        if v == 0:
            return '<td class="c"><span class="no" aria-label="nicht enthalten">–</span></td>'
        return f'<td class="c">{v}</td>'
    rows = "".join(f'<tr><th scope="row">{l}</th>{"".join(cell(v) for v in vals)}</tr>' for l, vals in MATRIX)
    faq = [
        ("Wie lange dauert eine Wäsche?", "Die Wäsche selbst dauert nur wenige Minuten. Wartezeiten hängen davon ab, wie viel los ist – unter der Woche am Vormittag ist es meist am ruhigsten."),
        FAQ_HOME[3], FAQ_HOME[4], FAQ_HOME[5],
    ]
    service = {
        "@type": "Service", "name": "Autowäsche in der Waschstraße", "serviceType": "Waschstraße",
        "provider": {"@id": SITE + "/#business"}, "areaServed": "Alzenau",
        "offers": [{"@type": "Offer", "name": p["name"], "price": p["num"], "priceCurrency": "EUR",
                    "description": ", ".join(p["items"])} for p in PROGRAMS],
    }
    body = f"""{page_hero(trail, "Waschstraße Alzenau", "Waschprogramme &amp; Preise", "Vier Programme von 12,90 € bis 19,90 € – jede Wäsche mit manueller Vorwäsche, Powertrocknung und Tuchtrocknung. Ohne Termin, Montag bis Sonntag.")}
<section class="section section--tint"><div class="wrap">
<h2 class="sr-only">Die vier Waschprogramme</h2>
<div class="plans">{plans}</div>
<p class="note">Alle Preise in Euro inkl. MwSt. Kunden der Waschstraße saugen bis zu 4 Minuten kostenlos. Mit der <a href="/kundenkarte/">Kundenkarte</a> sparen Sie bei jeder Wäsche.</p>
</div></section>

<section class="section"><div class="wrap">
<div class="head"><span class="eyebrow">Im Detail</span><h2>Alle Leistungen im Vergleich</h2></div>
<div class="table-wrap"><table><caption class="sr-only">Leistungsvergleich der Waschprogramme</caption>
<thead><tr><th scope="col">Leistung</th>{head}</tr></thead><tbody>{rows}</tbody></table></div>
</div></section>

<section class="section section--dark"><div class="wrap"><div class="split">
<div class="split__media">{pic("waschstrasse-schaumvorhang", "Fahrzeug fährt durch den Schaumvorhang der Waschstraße")}</div>
<div><span class="eyebrow">Technik</span><h2>30 Meter Waschstraße. Bis zu 13 Pflegeschritte.</h2>
<p class="lead">Sensorfil-Textilbürsten, Hyperjet-Felgenreinigung, Osmosespülung für kalkfreie Trocknung und zwei Turbogebläse: Im Aquastreet-Programm arbeitet die ganze Anlage für Ihr Auto.</p>
{checks(["Lackschonende Textilbürsten statt harter Borsten", "Osmosewasser gegen Kalkflecken", "Regelmäßig gewartete Anlage", "Bezahlung auch mit DKV- und UTA-Karte"])}
</div></div></div></section>

<section class="section"><div class="wrap">
<div class="head head--center"><span class="eyebrow">Vor der Einfahrt</span><h2>Fahrzeugmaße für die Waschstraße</h2></div>
{dims_block()}
</div></section>

<section class="section section--tint"><div class="wrap">
<div class="head"><span class="eyebrow">Fragen &amp; Antworten</span><h2>Rund um die Waschstraße</h2></div>
{faq_block(faq)}
</div></section>
{cta()}"""
    return layout("/waschstrasse/", "Waschstraße Alzenau: Programme & Preise | Aquastreet",
                  "4 Waschprogramme von 12,90 € bis 19,90 €: Vorwäsche, Aktivschaum, Felgenreinigung, NANO-Wachs, Osmosespülung. Ohne Termin in Alzenau.",
                  body, [service, crumbs_ld(trail), faq_ld(faq)])


def sb():
    trail = [("/", "Startseite"), ("/sb-waschen/", "SB-Waschen & Saugen")]
    products = "".join(f'<div class="product">{pic(n, t, "(max-width: 600px) 50vw, 16vw")}<div><span>{t}</span><b>{pr}</b></div></div>' for n, t, pr in PRODUCTS)
    faq = [
        ("Wann kann ich die SB-Boxen nutzen?", "Rund um die Uhr – 24 Stunden am Tag, 7 Tage die Woche. Das gilt auch für die Staubsaugerplätze."),
        ("Wie bezahle ich an den SB-Boxen?", "Mit Jetons. Jetons erhalten Sie an der Kasse der Waschstraße – auch mit DKV- oder UTA-Karte."),
        ("Ist Staubsaugen kostenlos?", "Für Kunden der Waschstraße sind bis zu 4 Minuten Saugen kostenlos."),
    ]
    body = f"""{page_hero(trail, "Selbstbedienung · 24/7", "SB-Waschbox &amp; Staubsauger in Alzenau", "Selbst waschen, wann es Ihnen passt: 4 SB-Boxen mit 7 Programmen, 10 Staubsaugerplätze und Mattenreiniger – rund um die Uhr geöffnet.")}
<section class="section"><div class="wrap">
<h2 class="sr-only">Ausstattung</h2>
<div class="grid grid--3">
<div class="card"><div class="icon">{ico('drop')}</div><h3>4 SB-Waschboxen</h3><p>Mit 7 Programmen und speziellen Reinigungsmitteln für starken Glanz – in wenigen Minuten.</p></div>
<div class="card"><div class="icon">{ico('wind')}</div><h3>10 Staubsaugerplätze</h3><p>Starke Saugleistung, regelmäßig gewartet. Für Kunden der Waschstraße bis zu 4 Minuten gratis.</p></div>
<div class="card"><div class="icon">{ico('clock')}</div><h3>24 Stunden, 7 Tage</h3><p>SB-Boxen, Staubsauger und Mattenreiniger stehen Ihnen jederzeit zur Verfügung.</p></div>
</div></div></section>

<section class="section section--tint"><div class="wrap"><div class="split">
<div><span class="eyebrow">Selbst ist der Glanz</span><h2>Die richtigen Mittel für Ihre Handwäsche.</h2>
<p class="lead">Wer selbst wäscht, braucht gute Technik und die richtigen Mittel. In unseren SB-Boxen finden Sie beides – durchdachte Programme und Reinigungsmittel, die Schmutz lösen und Lack schonen.</p>
{checks(["7 Waschprogramme pro Box", "Spezielle Reinigungsmittel für extremen Glanz", "Jetons an der Kasse – auch mit DKV/UTA", "Mattenreiniger vor Ort"])}
</div>
<div class="split__media">{pic("sb-hochdruck-felge", "Hochdruckreinigung der Felgen an der SB-Waschbox")}</div>
</div></div></section>

<section class="section"><div class="wrap">
<div class="head"><span class="eyebrow">An der Kasse erhältlich</span><h2>Pflegeprodukte für Ihre SB-Wäsche</h2>
<p class="lead">Mikrofaser- und Trocknungstücher, Ledertuch und Waschhandschuh in Aquastreet-Qualität.</p></div>
<div class="products">{products}</div>
</div></section>

<section class="section section--tint"><div class="wrap">
<div class="head"><span class="eyebrow">Fragen &amp; Antworten</span><h2>SB-Waschen bei Aquastreet</h2></div>
{faq_block(faq)}
</div></section>
{cta("Waschen, wann Sie wollen.", "SB-Boxen und Staubsauger sind rund um die Uhr geöffnet – Emmy-Noether-Straße 5, 63755 Alzenau.")}"""
    service = {"@type": "Service", "name": "SB-Waschboxen und Staubsauger", "serviceType": "Selbstbedienungs-Autowäsche",
               "provider": {"@id": SITE + "/#business"}, "areaServed": "Alzenau",
               "hoursAvailable": {"@type": "OpeningHoursSpecification", "dayOfWeek": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"], "opens": "00:00", "closes": "23:59"}}
    return layout("/sb-waschen/", "SB-Waschbox & Staubsauger Alzenau 24/7 | Aquastreet",
                  "Selbst waschen in Alzenau: 4 SB-Boxen mit 7 Programmen, 10 Staubsaugerplätze und Mattenreiniger – rund um die Uhr. Jetons auch mit DKV/UTA.",
                  body, [service, crumbs_ld(trail), faq_ld(faq)])


def innen():
    trail = [("/", "Startseite"), ("/innenreinigung/", "Innenreinigung & Aufbereitung")]
    prices = "".join(f"<li><span>{n}</span><b>{p}</b></li>" for n, p in DETAILING)
    service = {"@type": "Service", "name": "Innenreinigung und Fahrzeugaufbereitung", "serviceType": "Fahrzeugaufbereitung",
               "provider": {"@id": SITE + "/#business"}, "areaServed": "Alzenau",
               "offers": [{"@type": "Offer", "name": n, "priceSpecification": {"@type": "PriceSpecification", "minPrice": p.replace("ab ", "").split(" ")[0], "priceCurrency": "EUR"}} for n, p in DETAILING]}
    body = f"""{page_hero(trail, "Innenreinigung · Detailing", "Innenreinigung &amp; Fahrzeugaufbereitung in Alzenau", "Das Innere zählt: Express-Innenreinigung direkt nach der Wäsche – ohne Termin. Und für den großen Auftritt: Politur, Leder- und Polsterpflege sowie Lackversiegelung.")}
<section class="section"><div class="wrap"><div class="split">
<div><span class="eyebrow">Mo – Sa · 09 – 19 Uhr · ohne Termin</span>
<h2>Express-Innenreinigung für 40 €</h2>
<p class="lead">Einfach zum Waschprogramm dazubuchen. Mit speziellen Reinigungspistolen und gezielter Säuberung – vom Kofferraum bis zum Armaturenbrett.</p>
{checks(INTERIOR_ITEMS)}
<a class="btn btn--primary" href="{BIZ['maps']}" rel="noopener" target="_blank">{ico('route')} Jetzt vorbeikommen</a>
</div>
<div class="split__media">{pic("innenreinigung-spray", "Innenreinigung der Türverkleidung mit Sprühflasche")}</div>
</div></div></section>

<section class="section section--dark" id="aufbereitung"><div class="wrap"><div class="split split--rev">
<div><span class="eyebrow">Fahrzeugpflege &amp; Detailing</span>
<h2>Mehr als eine Wäsche: Werterhalt mit System.</h2>
<p class="lead">Gründliche Polster- und Lederreinigung, schonende Motorraumreinigung, hochwertige Politur oder professionelle Lackversiegelung – für nachhaltigen Glanz, Schutz und Werterhalt. Auf Wunsch auch individuell auf Ihr Auto abgestimmt.</p>
<ul class="price-list">{prices}</ul>
<p class="note">Preise inkl. MwSt. „ab“-Preise hängen von Fahrzeuggröße und Zustand ab. Größere Aufbereitungen mit oder ohne Termin – sprechen Sie uns an.</p>
<div class="btn-row"><a class="btn btn--light" href="/kontakt/">Angebot anfragen {ico('arrow')}</a>
<a class="btn btn--ghost" href="tel:{BIZ['phone_tel']}">{ico('phone')} Anrufen</a></div>
</div>
<div class="split__media">{pic("aufbereitung-team", "Mitarbeiter bei der Fahrzeugaufbereitung eines Oldtimers")}</div>
</div></div></section>

<section class="section"><div class="wrap">
<div class="grid grid--3">
<article class="card card--link">{pic("innenraum-lenkrad", "Sauberes Lenkrad und Cockpit nach der Innenreinigung", "(max-width: 860px) 100vw, 33vw")}<div class="card__body"><h3>Cockpit &amp; Ablagen</h3><p>Staub, Fingerabdrücke und Krümel entfernen wir aus jeder Ecke – auch aus Türfalzen und Konsole.</p></div></article>
<article class="card card--link">{pic("felgenreinigung", "Felgenreinigung mit Bürste und Schaum", "(max-width: 860px) 100vw, 33vw")}<div class="card__body"><h3>Felgen &amp; Reifen</h3><p>Felgengrundreinigung, Intensivschmutzlöser und Hyperjet-Hochdruck lösen auch Bremsstaub.</p></div></article>
<article class="card card--link">{pic("lack-seite", "Glänzender Lack nach Politur und Versiegelung", "(max-width: 860px) 100vw, 33vw")}<div class="card__body"><h3>Lack &amp; Versiegelung</h3><p>Politur, Wachs-, Keramik- oder Graphenversiegelung für langanhaltenden Schutz und Tiefenglanz.</p></div></article>
</div></div></section>
{cta("Innen wie neu – ohne Termin.", "Express-Innenreinigung Montag bis Samstag von 9 bis 19 Uhr. Für Aufbereitungen beraten wir Sie gern persönlich.")}"""
    return layout("/innenreinigung/", "Innenreinigung & Fahrzeugaufbereitung Alzenau | Aquastreet",
                  "Express-Innenreinigung für 40 € ohne Termin, Leder- & Polsterreinigung, Politur, Keramik- und Graphenversiegelung in Alzenau. Jetzt vorbeikommen.",
                  body, [service, crumbs_ld(trail)])


def firmen():
    trail = [("/", "Startseite"), ("/firmenkunden/", "Firmenkunden & Flotten")]
    body = f"""{page_hero(trail, "Für Unternehmen", "Autowäsche für Firmenfahrzeuge &amp; Flotten", "Ein Dienstwagen oder ein ganzer Fuhrpark: Mit der Aquastreet-Firmenkarte sparen Sie bis zu 20 %, zahlen bargeldlos und behalten alle Fahrzeuge im Blick.")}
<section class="section"><div class="wrap">
<h2 class="sr-only">Vorteile der Firmenkarte</h2>
<div class="grid grid--4">
<div class="card"><div class="icon">{ico('gauge')}</div><h3>Bis zu 20 % sparen</h3><p>Je mehr Sie aufladen, desto mehr sparen Sie – bei jeder Wäsche.</p></div>
<div class="card"><div class="icon">{ico('card')}</div><h3>Bargeldlos</h3><p>Keine Spesenbelege mehr: Ihre Fahrer bezahlen einfach mit der Firmenkarte.</p></div>
<div class="card"><div class="icon">{ico('chart')}</div><h3>Monatlicher Bericht</h3><p>Leistungsbericht mit Zusammenfassung aller Fahrzeuge – ideal für die Buchhaltung.</p></div>
<div class="card"><div class="icon">{ico('building')}</div><h3>DKV &amp; UTA</h3><p>Tankkarten akzeptiert – für Wäschen, Pflegeprodukte und Jetons.</p></div>
</div></div></section>

<section class="section section--tint"><div class="wrap"><div class="split">
<div class="split__media">{pic("dkv-uta", "DKV- und UTA-Karten werden bei Aquastreet akzeptiert", "(max-width: 860px) 100vw, 40vw")}</div>
<div><span class="eyebrow">Fuhrpark-Pflege</span><h2>Ein gepflegter Fuhrpark hinterlässt Eindruck.</h2>
<p class="lead">Saubere Fahrzeuge sind Visitenkarte Ihres Unternehmens. Bei Aquastreet waschen Ihre Fahrer ohne Termin – Waschstraße Mo – Sa 8 – 20 Uhr, So 10 – 18 Uhr, SB-Boxen rund um die Uhr.</p>
{checks(["Ideal für Dienstwagen, Firmenflotten und Transporter bis 2,05 m Höhe", "Firmenkarte online beantragen, am nächsten Tag abholen", "Bezahlung mit DKV-, UTA- oder Firmenkarte", "Fahrzeugaufbereitung auf Anfrage"])}
<div class="btn-row"><a class="btn btn--primary" href="/kundenkarte/#antrag">Firmenkarte beantragen {ico('arrow')}</a>
<a class="btn btn--outline" href="/kontakt/">Persönliches Angebot</a></div>
</div></div></div></section>
<section class="section"><div class="wrap">
<div class="head"><span class="eyebrow">Fragen &amp; Antworten</span><h2>Firmenkarte &amp; Flottenwäsche</h2></div>
{faq_block(FAQ_FIRMEN)}
</div></section>
{cta("Fragen zur Firmenkarte?", "Wir beraten Sie gern – telefonisch unter " + BIZ['phone_display'] + " oder per E-Mail an " + BIZ['email'] + ".")}"""
    return layout("/firmenkunden/", "Firmenkarte & Flottenwäsche Alzenau | Aquastreet",
                  "Autowäsche für Firmenwagen und Fuhrparks: bis zu 20 % sparen mit der Aquastreet-Firmenkarte, monatlicher Leistungsbericht, DKV & UTA akzeptiert.",
                  body, [crumbs_ld(trail), faq_ld(FAQ_FIRMEN)])


def kundenkarte():
    trail = [("/", "Startseite"), ("/kundenkarte/", "Kundenkarte")]
    gifts = "".join(f'<div class="card"><div class="icon">{ico("gift")}</div><h3>Ab {a} Aufladung</h3><p>{g} geschenkt</p></div>' for a, g in GIFTS)
    body = f"""{page_hero(trail, "Kundenkarte", "Kundenkarte beantragen &amp; bei jeder Wäsche sparen", "Laden Sie Ihre Karte auf, bezahlen Sie bargeldlos und sparen Sie bei jeder Nutzung – in der Waschstraße und an den SB-Boxen. Einmalige Gebühr: 2 €.")}
<section class="section"><div class="wrap">
<h2 class="sr-only">Privatkarte und Firmenkarte</h2>
<div class="grid grid--2">
<div class="card"><div class="icon">{ico('card')}</div><h3>Privatkarte</h3><p class="plan__price">bis 15 % <small>sparen</small></p>
{checks(["Rabatt bei jeder Wäsche", "Bargeldlose Bezahlung", "Ideale Geschenkidee", "Je mehr Sie aufladen, desto mehr sparen Sie"])}
<a class="btn btn--primary" href="#antrag">Privatkarte beantragen</a></div>
<div class="card"><div class="icon">{ico('building')}</div><h3>Firmenkarte</h3><p class="plan__price">bis 20 % <small>sparen</small></p>
{checks(["Für einen Wagen oder die ganze Flotte", "Bargeldlose Bezahlung", "Monatlicher Leistungsbericht", "Zusammenfassung aller Fahrzeuge"])}
<a class="btn btn--primary" href="#antrag">Firmenkarte beantragen</a></div>
</div></div></section>

<section class="section section--tint"><div class="wrap">
<div class="head"><span class="eyebrow">So einfach geht's</span><h2>In drei Schritten zur Karte</h2></div>
<ol class="steps">
<li><h3>Beantragen</h3><p>Online über das Formular unten – oder direkt an der Kasse, dann nehmen Sie die Karte sofort mit.</p></li>
<li><h3>Abholen &amp; aufladen</h3><p>Online beantragte Karten liegen am nächsten Tag bereit. Zur Registrierung laden Sie die Karte bei der Abholung auf.</p></li>
<li><h3>Bei jeder Wäsche sparen</h3><p>Regelmäßiges Waschen schützt den Wert Ihres Autos – gerade im Winter. Mit der Karte wird es günstiger.</p></li>
</ol></div></section>

<section class="section"><div class="wrap">
<div class="head"><span class="eyebrow">Willkommensgeschenk</span><h2>Ihr Geschenk zur ersten Aufladung</h2>
<p class="lead">Bei der ersten Aufladung erhalten Sie eines unserer Pflegeprodukte gratis an der Kasse.</p></div>
<div class="grid grid--3">{gifts}</div>
</div></section>

<section class="section section--tint" id="antrag"><div class="wrap"><div class="split">
<div><span class="eyebrow">Online-Antrag</span><h2>Jetzt Kundenkarte beantragen</h2>
<p class="lead">Füllen Sie das Formular aus – wir melden uns, sobald Ihre Karte zur Abholung bereitliegt. Einmalige Gebühr 2 €, zahlbar bei Abholung.</p>
{checks(["Abholung ab dem nächsten Tag", "Kein Abo, keine Grundgebühr", "Daten nur zur Kartenerstellung"])}
</div>
<div class="card">
<form class="form" action="/formular.php" method="post">
<input type="hidden" name="formular" value="kundenkarte">
<div class="hp" aria-hidden="true"><label for="website">Website</label><input type="text" id="website" name="website" tabindex="-1" autocomplete="off"></div>
<fieldset class="choice"><legend class="sr-only">Kartenart</legend>
<label><input type="radio" name="kartenart" value="Privatkarte" checked><span><b>Privatkarte</b><span>bis 15 % sparen</span></span></label>
<label><input type="radio" name="kartenart" value="Firmenkarte"><span><b>Firmenkarte</b><span>bis 20 % sparen</span></span></label>
</fieldset>
<div class="form__row"><div><label for="vorname">Vorname</label><input type="text" id="vorname" name="vorname" autocomplete="given-name" required maxlength="80"></div>
<div><label for="nachname">Nachname</label><input type="text" id="nachname" name="nachname" autocomplete="family-name" required maxlength="80"></div></div>
<div><label for="firma">Firma <span class="opt">(nur bei Firmenkarte)</span></label><input type="text" id="firma" name="firma" autocomplete="organization" maxlength="120"></div>
<div><label for="strasse">Straße und Hausnummer</label><input type="text" id="strasse" name="strasse" autocomplete="street-address" required maxlength="120"></div>
<div class="form__row"><div><label for="plz">PLZ</label><input type="text" id="plz" name="plz" autocomplete="postal-code" inputmode="numeric" pattern="[0-9]{{5}}" required maxlength="5"></div>
<div><label for="ort">Ort</label><input type="text" id="ort" name="ort" autocomplete="address-level2" required maxlength="80"></div></div>
<div class="form__row"><div><label for="email">E-Mail</label><input type="email" id="email" name="email" autocomplete="email" required maxlength="120"></div>
<div><label for="telefon">Telefon <span class="opt">(optional)</span></label><input type="tel" id="telefon" name="telefon" autocomplete="tel" maxlength="40"></div></div>
<div><label for="kennzeichen">Kennzeichen <span class="opt">(optional, bei Flotten mehrere)</span></label><input type="text" id="kennzeichen" name="kennzeichen" maxlength="300"></div>
<small>Mit dem Absenden verarbeiten wir Ihre Angaben zur Erstellung der Kundenkarte. Mehr dazu in der <a href="/datenschutz/">Datenschutzerklärung</a>.</small>
<button class="btn btn--primary" type="submit">Karte verbindlich beantragen {ico('arrow')}</button>
</form></div>
</div></div></section>"""
    return layout("/kundenkarte/", "Kundenkarte: bis 20 % sparen | Aquastreet Alzenau",
                  "Aquastreet-Kundenkarte online beantragen: Privat bis 15 %, Firmen bis 20 % Rabatt, bargeldlos zahlen, Geschenk bei der ersten Aufladung. Nur 2 € Gebühr.",
                  body, [crumbs_ld(trail)])


def aktionen():
    trail = [("/", "Startseite"), ("/aktionen/", "Aktionen")]
    rows = "".join(f'<tr><th scope="row">{n}</th><td class="c"><s>{a} €</s></td><td class="c"><b>{b} €</b></td></tr>' for n, a, b in SENIOR)
    body = f"""{page_hero(trail, "Aktionen &amp; Angebote", "Aktuelle Aktionen bei Aquastreet", "Jede Woche sparen: Am Seniorentag sind alle Waschprogramme günstiger. Weitere Aktionen kündigen wir regelmäßig auf Instagram an.")}
<section class="section"><div class="wrap"><div class="split">
<div><span class="eyebrow">Jeden Montag · ganztägig</span><h2>Seniorentag</h2>
<p class="lead">Ein guter Start in die Woche: Montags waschen Seniorinnen und Senioren in allen Programmen günstiger. Bitte zeigen Sie dazu Ihren Seniorenausweis an der Kasse.</p>
<div class="table-wrap"><table class="table--compact"><caption class="sr-only">Seniorentag-Preise</caption>
<thead><tr><th scope="col">Programm</th><th scope="col" class="c">Regulär</th><th scope="col" class="c">Montag</th></tr></thead><tbody>{rows}</tbody></table></div>
</div>
<div class="split__media">{pic("aktion-seniorentag", "Aquastreet Seniorentag jeden Montag", "(max-width: 860px) 100vw, 45vw")}</div>
</div></div></section>

<section class="section section--tint"><div class="wrap"><div class="split split--rev">
<div><span class="eyebrow">An allen anderen Tagen</span><h2>Mit der Kundenkarte immer sparen</h2>
<p class="lead">Bis zu 15 % als Privatkunde, bis zu 20 % als Firmenkunde – in der Waschstraße und an den SB-Boxen. Online beantragen, vor Ort abholen.</p>
<div class="btn-row"><a class="btn btn--primary" href="/kundenkarte/">Kundenkarte beantragen {ico('arrow')}</a>
<a class="btn btn--outline" href="{BIZ['instagram']}" rel="noopener" target="_blank">{ico('instagram')} Aktionen auf Instagram</a></div></div>
<div class="split__media">{pic("golf-schaum", "Weißes Auto im Schaum in der Waschstraße")}</div>
</div></div></section>
{cta()}"""
    offer = {"@type": "Offer", "name": "Seniorentag – alle Waschprogramme günstiger", "url": SITE + "/aktionen/",
             "eligibleCustomerType": "Senioren mit Seniorenausweis", "priceCurrency": "EUR", "price": "9.90",
             "description": "Jeden Montag ganztägig: Aquastreet 16,90 €, Highwaystreet 13,90 €, Countrystreet 11,90 €, Expressstreet 9,90 €.",
             "offeredBy": {"@id": SITE + "/#business"}}
    return layout("/aktionen/", "Aktionen: Seniorentag jeden Montag | Aquastreet Alzenau",
                  "Jeden Montag Seniorentag bei Aquastreet in Alzenau: alle Waschprogramme bis zu 3 € günstiger. Dazu dauerhaft sparen mit der Kundenkarte.",
                  body, [offer, crumbs_ld(trail)])


def ueber():
    trail = [("/", "Startseite"), ("/ueber-uns/", "Über uns")]
    body = f"""{page_hero(trail, "Über Aquastreet", "Mehr als nur eine Wäsche.", "Aquastreet in Alzenau ist ein Waschpark mit Rundum-Service: von der Außen- bis zur Innenreinigung, von der Waschstraße bis zur SB-Box. Bei Planung und Umsetzung sind wir bis ins Detail gegangen.")}
<section class="section"><div class="wrap"><div class="split">
<div><span class="eyebrow">Unser Anspruch</span><h2>Die Liebe zum Waschen.</h2>
<p class="lead">Viele Waschstraßen setzen auf das Nötigste. Wir nicht: moderne Maschinen, regelmäßige Wartung und ein Team, das jedes Detail im Blick hat.</p>
<div class="compare mt-2">
<div class="compare__them"><h3>Typische Waschstraße</h3><ul><li>Nur die nötigsten Maschinen</li><li>Selten gewartet</li><li>Wenig Leistung zum hohen Preis</li><li>Kein persönlicher Kontakt</li></ul></div>
<div class="compare__us"><h3>Aquastreet</h3>{checks(["Maschinen und Personal für jedes Detail", "Regelmäßige Wartung", "Alle Leistungen in 4 klaren Programmen", "Persönlich vor Ort und auf Social Media"])}</div>
</div></div>
<div class="split__media">{pic("mercedes-halle", "Frisch gewaschenes Auto in der Halle von Aquastreet")}</div>
</div></div></section>

<section class="section section--dark"><div class="wrap">
<div class="head"><span class="eyebrow">Wofür wir stehen</span><h2>Gut für dein Auto, besser für die Umwelt.</h2></div>
<div class="grid grid--3">
<div class="card"><div class="icon">{ico('shield')}</div><h3>Schonen</h3><p>Zu jeder Jahreszeit braucht Ihr Auto Pflege. Wir setzen die richtigen Mittel ein und schützen Lack und Werterhalt.</p></div>
<div class="card"><div class="icon">{ico('leaf')}</div><h3>Umwelt</h3><p>Einsparsysteme, Wasserrückgewinnung, Abwasserbehandlung und genau dosierte Mittel – für weniger Belastung.</p></div>
<div class="card"><div class="icon">{ico('spark')}</div><h3>Zufriedenheit</h3><p>Ihre Meinung ist uns wichtig. Sprechen Sie uns vor Ort an oder schreiben Sie uns – wir antworten auf alles.</p></div>
</div></div></section>

<section class="section section--tint"><div class="wrap">
<div class="head"><span class="eyebrow">Fragen &amp; Antworten</span><h2>Häufig gestellte Fragen</h2></div>
{faq_block(FAQ_ABOUT)}
</div></section>

<section class="section"><div class="wrap"><h2 class="sr-only">Standort und Öffnungszeiten</h2>{location_block()}</div></section>"""
    return layout("/ueber-uns/", "Über uns – Aquastreet Waschpark Alzenau",
                  "Aquastreet ist der Waschpark in Alzenau: moderne Waschstraße, SB-Boxen und Innenreinigung mit Liebe zum Detail – gut für Ihr Auto, besser für die Umwelt.",
                  body, [crumbs_ld(trail), faq_ld(FAQ_ABOUT)])


def kontakt():
    trail = [("/", "Startseite"), ("/kontakt/", "Kontakt & Anfahrt")]
    body = f"""{page_hero(trail, "Kontakt &amp; Anfahrt", "So erreichen Sie Aquastreet", "Emmy-Noether-Straße 5, 63755 Alzenau. Für Waschstraße, SB und Innenreinigung brauchen Sie keinen Termin – für Fragen und Aufbereitungen sind wir gern für Sie da.")}
<section class="section"><div class="wrap"><h2 class="sr-only">Adresse und Öffnungszeiten</h2>{location_block()}</div></section>
<section class="section section--tint"><div class="wrap"><div class="split">
<div><span class="eyebrow">Nachricht schreiben</span><h2>Wir sind für Sie da.</h2>
<p class="lead">Fragen zur Kundenkarte, ein Angebot für die Aufbereitung oder Feedback zu Ihrer Wäsche? Schreiben Sie uns – oder rufen Sie an unter <a href="tel:{BIZ['phone_tel']}">{BIZ['phone_display']}</a>.</p>
{checks(["Antwort in der Regel innerhalb eines Werktags", "Aufbereitungen individuell auf Anfrage", "Persönlich vor Ort zu den Öffnungszeiten"])}
</div>
<div class="card"><form class="form" action="/formular.php" method="post">
<input type="hidden" name="formular" value="kontakt">
<div class="hp" aria-hidden="true"><label for="website">Website</label><input type="text" id="website" name="website" tabindex="-1" autocomplete="off"></div>
<div class="form__row"><div><label for="name">Name</label><input type="text" id="name" name="name" autocomplete="name" required maxlength="120"></div>
<div><label for="email">E-Mail</label><input type="email" id="email" name="email" autocomplete="email" required maxlength="120"></div></div>
<div class="form__row"><div><label for="telefon">Telefon <span class="opt">(optional)</span></label><input type="tel" id="telefon" name="telefon" autocomplete="tel" maxlength="40"></div>
<div><label for="thema">Thema</label><select id="thema" name="thema"><option>Allgemeine Frage</option><option>Fahrzeugaufbereitung / Angebot</option><option>Kundenkarte / Firmenkarte</option><option>Lob &amp; Kritik</option></select></div></div>
<div><label for="nachricht">Nachricht</label><textarea id="nachricht" name="nachricht" required maxlength="4000"></textarea></div>
<small>Ihre Angaben verwenden wir nur zur Bearbeitung Ihrer Anfrage. Mehr in der <a href="/datenschutz/">Datenschutzerklärung</a>.</small>
<button class="btn btn--primary" type="submit">Nachricht senden {ico('arrow')}</button>
</form></div>
</div></div></section>"""
    cp = {"@type": "ContactPage", "url": SITE + "/kontakt/", "name": "Kontakt Aquastreet", "about": {"@id": SITE + "/#business"}}
    return layout("/kontakt/", "Kontakt & Anfahrt – Aquastreet Waschstraße Alzenau",
                  "Aquastreet, Emmy-Noether-Straße 5, 63755 Alzenau. Telefon 0151 72297295, info@aquastreet.de. Öffnungszeiten, Route und Kontaktformular.",
                  body, [cp, business_ld(full=False), crumbs_ld(trail)])


def impressum():
    trail = [("/", "Startseite"), ("/impressum/", "Impressum")]
    body = f"""{page_hero(trail, "Rechtliches", "Impressum", "Angaben gemäß § 5 Digitale-Dienste-Gesetz (DDG).")}
<section class="section"><div class="wrap prose">
<h2>Anbieter</h2>
<p>{BIZ['legal']}<br>{BIZ['street']}<br>{BIZ['zip']} {BIZ['city']}</p>
<p>Vertreten durch: Nurettin Gültekin</p>
<h2>Kontakt</h2>
<p>Telefon: <a href="tel:{BIZ['phone_tel']}">{BIZ['phone_intl']}</a><br>E-Mail: <a href="mailto:{BIZ['email']}">{BIZ['email']}</a></p>
<h2>Registereintrag</h2>
<p>Eintragung im Handelsregister<br>Registergericht: Amtsgericht Aschaffenburg<br>Registernummer: HRB 16269</p>
<h2>Umsatzsteuer-ID</h2>
<p>Umsatzsteuer-Identifikationsnummer gemäß § 27 a Umsatzsteuergesetz: DE347188022</p>
<h2>Haftung für Inhalte</h2>
<p>Als Diensteanbieter sind wir für eigene Inhalte auf diesen Seiten nach den allgemeinen Gesetzen verantwortlich. Wir sind jedoch nicht verpflichtet, übermittelte oder gespeicherte fremde Informationen zu überwachen oder nach Umständen zu forschen, die auf eine rechtswidrige Tätigkeit hinweisen. Verpflichtungen zur Entfernung oder Sperrung der Nutzung von Informationen nach den allgemeinen Gesetzen bleiben hiervon unberührt. Eine diesbezügliche Haftung ist erst ab dem Zeitpunkt der Kenntnis einer konkreten Rechtsverletzung möglich. Bei Bekanntwerden entsprechender Rechtsverletzungen entfernen wir diese Inhalte umgehend.</p>
<h2>Haftung für Links</h2>
<p>Unser Angebot enthält Links zu externen Websites Dritter, auf deren Inhalte wir keinen Einfluss haben. Für diese fremden Inhalte können wir daher keine Gewähr übernehmen. Für die Inhalte der verlinkten Seiten ist stets der jeweilige Anbieter oder Betreiber verantwortlich. Die verlinkten Seiten wurden zum Zeitpunkt der Verlinkung auf mögliche Rechtsverstöße überprüft; rechtswidrige Inhalte waren nicht erkennbar. Bei Bekanntwerden von Rechtsverletzungen entfernen wir derartige Links umgehend.</p>
<h2>Urheberrecht</h2>
<p>Die durch die Seitenbetreiber erstellten Inhalte und Werke auf diesen Seiten unterliegen dem deutschen Urheberrecht. Vervielfältigung, Bearbeitung, Verbreitung und jede Art der Verwertung außerhalb der Grenzen des Urheberrechts bedürfen der schriftlichen Zustimmung des jeweiligen Autors bzw. Erstellers. Soweit Inhalte nicht vom Betreiber erstellt wurden, werden die Urheberrechte Dritter beachtet. Sollten Sie trotzdem auf eine Urheberrechtsverletzung aufmerksam werden, bitten wir um einen entsprechenden Hinweis.</p>
</div></section>"""
    return layout("/impressum/", "Impressum | Aquastreet Alzenau", "Impressum der Aquastreet Waschanlage – GLT Verwaltungs GmbH, Emmy-Noether-Straße 5, 63755 Alzenau.",
                  body, [crumbs_ld(trail)])


def datenschutz():
    trail = [("/", "Startseite"), ("/datenschutz/", "Datenschutz")]
    body = f"""{page_hero(trail, "Rechtliches", "Datenschutzerklärung", "Diese Website kommt ohne Cookies, ohne Tracking und ohne eingebettete Inhalte von Drittanbietern aus.")}
<section class="section"><div class="wrap prose">
<h2>1. Verantwortliche Stelle</h2>
<p>Verantwortlich für die Datenverarbeitung auf dieser Website ist:</p>
<p>{BIZ['legal']}<br>{BIZ['street']}<br>{BIZ['zip']} {BIZ['city']}<br>Telefon: {BIZ['phone_intl']}<br>E-Mail: <a href="mailto:{BIZ['email']}">{BIZ['email']}</a></p>
<p>Verantwortliche Stelle ist die natürliche oder juristische Person, die allein oder gemeinsam mit anderen über die Zwecke und Mittel der Verarbeitung personenbezogener Daten entscheidet.</p>

<h2>2. Hosting</h2>
<p>Wir hosten diese Website bei der STRATO GmbH, Otto-Ostrowski-Straße 7, 10249 Berlin („STRATO“). Beim Besuch unserer Website verarbeitet STRATO technisch notwendige Daten, insbesondere Ihre IP-Adresse, in Server-Logfiles. Weitere Informationen finden Sie in der Datenschutzerklärung von STRATO: <a href="https://www.strato.de/datenschutz/" rel="noopener">www.strato.de/datenschutz</a>.</p>
<p>Die Nutzung von STRATO erfolgt auf Grundlage von Art. 6 Abs. 1 lit. f DSGVO. Wir haben ein berechtigtes Interesse an einer zuverlässigen und sicheren Bereitstellung unserer Website. Mit STRATO besteht ein Vertrag zur Auftragsverarbeitung nach Art. 28 DSGVO.</p>

<h2>3. Server-Logfiles</h2>
<p>Bei jedem Aufruf der Website werden automatisch Informationen erfasst, die Ihr Browser übermittelt: Browsertyp und -version, Betriebssystem, Referrer-URL, Hostname des zugreifenden Rechners, Uhrzeit der Serveranfrage und IP-Adresse. Diese Daten werden nicht mit anderen Datenquellen zusammengeführt. Rechtsgrundlage ist Art. 6 Abs. 1 lit. f DSGVO; unser berechtigtes Interesse liegt in der technisch fehlerfreien und sicheren Darstellung der Website.</p>

<h2>4. Keine Cookies, kein Tracking</h2>
<p>Diese Website setzt keine Cookies, verwendet keine Analyse- oder Marketing-Tools und lädt keine Schriften, Karten, Videos oder Skripte von Drittanbietern. Links zu Google Maps, Instagram und TikTok sind einfache Links: Erst wenn Sie darauf klicken, verlassen Sie unsere Website, und es gelten die Datenschutzbestimmungen des jeweiligen Anbieters.</p>

<h2>5. Kontaktformular, Kundenkartenantrag und Anfragen per E-Mail oder Telefon</h2>
<p>Wenn Sie uns über das Kontaktformular, den Kundenkartenantrag, per E-Mail oder telefonisch kontaktieren, verarbeiten wir Ihre Angaben (z. B. Name, Anschrift, E-Mail-Adresse, Telefonnummer, Kennzeichen, Nachricht) zur Bearbeitung Ihrer Anfrage bzw. zur Erstellung Ihrer Kundenkarte. Die Formulardaten werden per E-Mail an uns übermittelt.</p>
<p>Rechtsgrundlage ist Art. 6 Abs. 1 lit. b DSGVO, soweit Ihre Anfrage mit der Erfüllung eines Vertrags zusammenhängt oder zur Durchführung vorvertraglicher Maßnahmen erforderlich ist, im Übrigen Art. 6 Abs. 1 lit. f DSGVO (berechtigtes Interesse an der effektiven Bearbeitung von Anfragen). Ihre Daten bleiben bei uns, bis der Zweck entfällt, Sie die Löschung verlangen oder gesetzliche Aufbewahrungsfristen ablaufen. Eine Weitergabe an Dritte erfolgt nicht.</p>

<h2>6. Speicherdauer</h2>
<p>Soweit nicht ausdrücklich anders angegeben, verbleiben Ihre personenbezogenen Daten bei uns, bis der Zweck der Verarbeitung entfällt. Gesetzliche Aufbewahrungspflichten (z. B. steuer- oder handelsrechtlich) bleiben unberührt.</p>

<h2>7. SSL-/TLS-Verschlüsselung</h2>
<p>Diese Website nutzt aus Sicherheitsgründen eine SSL-/TLS-Verschlüsselung. Eine verschlüsselte Verbindung erkennen Sie an „https://“ in der Adresszeile und am Schloss-Symbol Ihres Browsers.</p>

<h2>8. Ihre Rechte</h2>
<p>Sie haben jederzeit das Recht auf unentgeltliche Auskunft über Ihre gespeicherten personenbezogenen Daten (Art. 15 DSGVO), auf Berichtigung (Art. 16), Löschung (Art. 17), Einschränkung der Verarbeitung (Art. 18), Datenübertragbarkeit (Art. 20) sowie auf Widerruf einer erteilten Einwilligung mit Wirkung für die Zukunft (Art. 7 Abs. 3).</p>
<p><strong>Widerspruchsrecht (Art. 21 DSGVO):</strong> Erfolgt die Verarbeitung auf Grundlage von Art. 6 Abs. 1 lit. f DSGVO, können Sie aus Gründen, die sich aus Ihrer besonderen Situation ergeben, jederzeit Widerspruch einlegen.</p>
<p>Wenden Sie sich dazu einfach an <a href="mailto:{BIZ['email']}">{BIZ['email']}</a>.</p>

<h2>9. Beschwerderecht bei der Aufsichtsbehörde</h2>
<p>Sie haben das Recht, sich bei einer Datenschutz-Aufsichtsbehörde zu beschweren. Zuständig für uns ist das Bayerische Landesamt für Datenschutzaufsicht (BayLDA), Promenade 18, 91522 Ansbach, <a href="https://www.lda.bayern.de" rel="noopener">www.lda.bayern.de</a>.</p>

<p class="muted">Stand: {dt.date.today().strftime('%m/%Y')}</p>
</div></section>"""
    return layout("/datenschutz/", "Datenschutzerklärung | Aquastreet Alzenau", "Datenschutzerklärung von Aquastreet: keine Cookies, kein Tracking. Informationen zu Hosting, Kontaktformular und Ihren Rechten.",
                  body, [crumbs_ld(trail)])


def danke():
    body = f"""<section class="page-hero"><div class="wrap"><span class="eyebrow">Vielen Dank</span>
<h1>Ihre Nachricht ist bei uns angekommen.</h1>
<p class="lead">Wir melden uns so schnell wie möglich – in der Regel innerhalb eines Werktags. Kundenkarten liegen ab dem nächsten Tag zur Abholung bereit.</p>
<div class="btn-row mt-2"><a class="btn btn--light" href="/">Zur Startseite</a><a class="btn btn--ghost" href="/waschstrasse/">Programme &amp; Preise</a></div>
</div></section>"""
    return layout("/danke/", "Vielen Dank | Aquastreet", "Vielen Dank für Ihre Nachricht an Aquastreet.", body, noindex=True)


def fehler():
    body = f"""<section class="page-hero"><div class="wrap"><span class="eyebrow">Senden fehlgeschlagen</span>
<h1>Das hat leider nicht geklappt.</h1>
<p class="lead">Bitte prüfen Sie Ihre Angaben und versuchen Sie es erneut – oder schreiben Sie uns direkt an <a href="mailto:{BIZ['email']}">{BIZ['email']}</a> bzw. rufen Sie an: <a href="tel:{BIZ['phone_tel']}">{BIZ['phone_display']}</a>.</p>
<div class="btn-row mt-2"><a class="btn btn--light" href="/kontakt/">Zurück zum Kontakt</a><a class="btn btn--ghost" href="/kundenkarte/#antrag">Zum Kartenantrag</a></div>
</div></section>"""
    return layout("/fehler/", "Senden fehlgeschlagen | Aquastreet", "Das Formular konnte nicht gesendet werden.", body, noindex=True)


def notfound():
    links = "".join(f'<li><a href="{u}">{n}</a></li>' for u, n in NAV)
    body = f"""<section class="page-hero"><div class="wrap"><span class="eyebrow">Fehler 404</span>
<h1>Diese Seite gibt es nicht (mehr).</h1>
<p class="lead">Vielleicht finden Sie hier, was Sie suchen:</p>
<div class="btn-row mt-2"><a class="btn btn--light" href="/">Zur Startseite</a><a class="btn btn--ghost" href="/waschstrasse/">Programme &amp; Preise</a></div>
</div></section>
<section class="section"><div class="wrap"><ul class="checks">{links}</ul></div></section>"""
    return layout("/404.html", "Seite nicht gefunden | Aquastreet", "Diese Seite existiert nicht.", body, noindex=True)


# ---------------------------------------------------------------- BUILD ---

PAGES = [("/", home, "1.0"), ("/waschstrasse/", waschstrasse, "0.9"), ("/sb-waschen/", sb, "0.8"),
         ("/innenreinigung/", innen, "0.8"), ("/kundenkarte/", kundenkarte, "0.8"), ("/firmenkunden/", firmen, "0.7"),
         ("/aktionen/", aktionen, "0.7"), ("/ueber-uns/", ueber, "0.6"), ("/kontakt/", kontakt, "0.7"),
         ("/impressum/", impressum, "0.2"), ("/datenschutz/", datenschutz, "0.2")]
HIDDEN = [("/danke/", danke), ("/fehler/", fehler)]


def minify_css(css):
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    css = re.sub(r"\s+", " ", css)
    css = re.sub(r"\s*([{}:;,>])\s*", r"\1", css)
    return css.replace(";}", "}").strip()


def hashed(src, out, sub, ext):
    data = open(src, "rb").read()
    if ext == "css":
        data = minify_css(data.decode("utf-8")).encode("utf-8")
    h = hashlib.sha256(data).hexdigest()[:10]
    name = f"{sub}/{os.path.splitext(os.path.basename(src))[0]}.{h}.{ext}"
    os.makedirs(os.path.join(out, sub), exist_ok=True)
    open(os.path.join(out, name), "wb").write(data)
    return "/" + name


def make_icons(out):
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><defs><linearGradient id="a" x1="0" y1="0" x2="1" y2="1">'
           '<stop offset="0" stop-color="#22b8e8"/><stop offset="1" stop-color="#1673d1"/></linearGradient></defs>'
           '<rect width="64" height="64" rx="14" fill="#0a1324"/>'
           '<path d="M32 10s15 15.5 15 27a15 15 0 0 1-30 0c0-11.5 15-27 15-27z" fill="url(#a)"/>'
           '<path d="M25 40a7 7 0 0 0 7 6" stroke="#fff" stroke-width="3.5" fill="none" stroke-linecap="round"/></svg>')
    open(os.path.join(out, "favicon.svg"), "w").write(svg)
    from PIL import ImageDraw
    for size, name in ((32, "favicon-32.png"), (180, "apple-touch-icon.png"), (192, "icon-192.png"), (512, "icon-512.png")):
        s = size * 4
        im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle((0, 0, s - 1, s - 1), radius=int(s * .22), fill=(10, 19, 36, 255))
        cx, top, r = s / 2, s * .16, s * .235
        d.ellipse((cx - r, s * .58 - r, cx + r, s * .58 + r), fill=(28, 150, 220, 255))
        d.polygon([(cx, top), (cx - r * .97, s * .53), (cx + r * .97, s * .53)], fill=(28, 150, 220, 255))
        im.resize((size, size), Image.LANCZOS).save(os.path.join(out, name), optimize=True)
    with open(os.path.join(out, "favicon.ico"), "wb") as f:
        Image.open(os.path.join(out, "favicon-32.png")).save(f, format="ICO", sizes=[(32, 32)])
    json.dump({"name": "Aquastreet Waschpark Alzenau", "short_name": "Aquastreet", "start_url": "/", "display": "browser",
               "background_color": "#ffffff", "theme_color": "#0a1324", "lang": "de",
               "icons": [{"src": "/icon-192.png", "sizes": "192x192", "type": "image/png"},
                         {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png"}]},
              open(os.path.join(out, "site.webmanifest"), "w"), ensure_ascii=False, indent=1)


def write_page(out, path, content):
    if path != "/":  # first content image is near the fold on sub pages: load it right away
        content = content.replace(' loading="lazy" decoding="async"', ' decoding="async"', 1)
    target = os.path.join(out, path.strip("/"), "index.html") if path.endswith("/") else os.path.join(out, path.strip("/"))
    os.makedirs(os.path.dirname(target), exist_ok=True)
    open(target, "w", encoding="utf-8").write(content)
    return len(content.encode("utf-8"))


def llms_txt():
    progs = "\n".join(f"- {p['name']}: {p['price']} € – " + ", ".join(p["items"]) for p in PROGRAMS)
    det = "\n".join(f"- {n}: {p}" for n, p in DETAILING)
    return f"""# Aquastreet – Waschstraße & Waschpark in Alzenau

> Aquastreet ist ein Waschpark in der Emmy-Noether-Straße 5, 63755 Alzenau (Bayern): 30-Meter-Waschstraße mit vier Programmen (12,90–19,90 €), 4 SB-Waschboxen mit 7 Programmen, 10 Staubsaugerplätze, Mattenreiniger, Express-Innenreinigung und Fahrzeugaufbereitung. Ohne Termin. Betreiber: {BIZ['legal']}.

## Fakten
- Adresse: {BIZ['street']}, {BIZ['zip']} {BIZ['city']}
- Telefon: {BIZ['phone_intl']} · E-Mail: {BIZ['email']}
- Waschstraße: Mo–Sa 08:00–20:00, So 10:00–18:00
- Express-Innenreinigung: Mo–Sa 09:00–19:00
- SB-Boxen & Staubsauger: 24/7
- Fahrzeugmaße Waschstraße: max. Höhe 2,05 m, max. Breite 2,40 m, min. 8 cm Bodenfreiheit
- Bezahlung: u. a. DKV- und UTA-Karte, Aquastreet-Kundenkarte (privat bis 15 %, Firmen bis 20 % Rabatt, 2 € Gebühr)
- Kunden der Waschstraße saugen bis zu 4 Minuten kostenlos
- Seniorentag: jeden Montag alle Programme günstiger (9,90–16,90 €)

## Waschprogramme
{progs}

## Innenreinigung & Aufbereitung
{det}

## Seiten
- [Waschstraße: Programme & Preise]({SITE}/waschstrasse/)
- [SB-Waschen & Staubsauger]({SITE}/sb-waschen/)
- [Innenreinigung & Fahrzeugaufbereitung]({SITE}/innenreinigung/)
- [Kundenkarte]({SITE}/kundenkarte/)
- [Firmenkunden & Flotten]({SITE}/firmenkunden/)
- [Aktionen]({SITE}/aktionen/)
- [Über uns & FAQ]({SITE}/ueber-uns/)
- [Kontakt & Anfahrt]({SITE}/kontakt/)
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", default=os.path.join(HERE, "dist"))
    a = ap.parse_args()
    out = os.path.abspath(a.out)
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(out)
    ASSET["css"] = hashed(os.path.join(HERE, "assets/css/style.css"), out, "css", "css")
    ASSET["js"] = hashed(os.path.join(HERE, "assets/js/main.js"), out, "js", "js")
    shutil.copytree(os.path.join(HERE, "assets/img"), os.path.join(out, "img"))
    for f in os.listdir(os.path.join(HERE, "public")):
        shutil.copy2(os.path.join(HERE, "public", f), os.path.join(out, f))
    make_icons(out)
    total, built = 0, []
    for path, fn, _ in PAGES:
        total += write_page(out, path, fn())
        built.append(path)
    for path, fn in HIDDEN:
        total += write_page(out, path, fn())
        built.append(path)
    total += write_page(out, "/404.html", notfound())
    urls = "".join(f"<url><loc>{SITE}{p}</loc><lastmod>{TODAY}</lastmod><priority>{pr}</priority></url>\n" for p, _, pr in PAGES)
    open(os.path.join(out, "sitemap.xml"), "w").write(
        f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}</urlset>\n')
    open(os.path.join(out, "robots.txt"), "w").write(
        f"User-agent: *\nAllow: /\nDisallow: /formular.php\n\nSitemap: {SITE}/sitemap.xml\n")
    open(os.path.join(out, "llms.txt"), "w", encoding="utf-8").write(llms_txt())
    print(json.dumps({"pages": built + ["/404.html"], "out": out, "bytes": total}))


if __name__ == "__main__":
    main()
