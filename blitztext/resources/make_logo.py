#!/usr/bin/env python3
"""Erzeugt das Logo in den Marken-Farben — identisch zur Windows-Version
(blablatext_2.0/resources/make_logo.py), damit beide Plattformen dasselbe
Bild zeigen.

Motiv: abgerundetes Quadrat mit vier nach unten schmaler werdenden Balken.

Wird nur bei Bedarf ausgeführt (braucht Pillow); die erzeugten PNGs liegen
fertig im Repo, damit die App selbst ohne Pillow läuft:

    python blitztext/resources/make_logo.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

# Marken-Palette (identisch zu blablatext.py und popover.py)
ULTRAMARIN = (0, 13, 112, 255)          # #000D70
GEBROCHEN_WEISS = (245, 245, 245, 255)  # #F5F5F5

BALKEN_BREITEN = (1.0, 0.82, 0.64, 0.46)
UEBERABTASTUNG = 16


def zeichne_logo(kantenlaenge: int) -> Image.Image:
    gross = kantenlaenge * UEBERABTASTUNG
    bild = Image.new("RGBA", (gross, gross), (0, 0, 0, 0))
    d = ImageDraw.Draw(bild)

    d.rounded_rectangle([0, 0, gross - 1, gross - 1],
                        radius=int(gross * 0.22), fill=ULTRAMARIN)

    rand = gross * 0.17
    nutz = gross - 2 * rand
    balken_h = nutz * 0.155
    luecke = (nutz - len(BALKEN_BREITEN) * balken_h) / (len(BALKEN_BREITEN) - 1)

    for i, faktor in enumerate(BALKEN_BREITEN):
        breite = nutz * faktor
        x0 = rand
        y0 = rand + i * (balken_h + luecke)
        d.rounded_rectangle([x0, y0, x0 + breite, y0 + balken_h],
                            radius=balken_h / 2, fill=GEBROCHEN_WEISS)

    return bild.resize((kantenlaenge, kantenlaenge), Image.LANCZOS)


def main() -> None:
    ziel = Path(__file__).parent
    # 28px: Kopfzeile im Popover, 256px: App-/Fenstersymbol (ersetzt icon.png)
    for groesse, name in ((28, "logo-header.png"), (256, "icon.png")):
        pfad = ziel / name
        zeichne_logo(groesse).save(pfad)
        print(f"geschrieben: {pfad}")


if __name__ == "__main__":
    main()
