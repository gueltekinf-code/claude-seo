#!/usr/bin/env python3
"""
Convert the original Aquastreet photos into web-ready, responsive WebP files.

The originals (up to 8 MB JPEGs from the old site builder) are not committed.
This script reads them from a folder, crops/resizes them and writes small WebP
variants to ../assets/img/ plus a 1200x630 Open Graph JPEG.

Usage:
    python3 prepare_images.py --src /path/to/originals --map /path/to/imgs.tsv

``imgs.tsv`` lists one image id per line (first tab-separated column); the
selection below refers to images by their line index in that file.

Output (JSON on stdout): {"written": [...], "bytes": <total>}
"""
import argparse
import json
import os

from PIL import Image, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "assets", "img")

# name: (line index in imgs.tsv, widths, aspect ratio w/h or None, focus y 0..1)
SELECTION = {
    "hero-schaumwaesche": (39, [640, 828, 1080, 1440, 1920], 16 / 9, 0.55),
    "waschstrasse-buersten": (2, [480, 720, 960, 1440], 4 / 3, 0.5),
    "waschstrasse-schaumvorhang": (4, [480, 720, 960, 1440], 4 / 3, 0.5),
    "waschstrasse-ausfahrt": (17, [480, 720, 960], 3 / 4, 0.5),
    "waschstrasse-tunnel": (26, [480, 720, 960], 3 / 4, 0.5),
    "sb-box-hochdruck": (1, [480, 720, 960, 1440], 4 / 3, 0.5),
    "sb-hochdruck-felge": (27, [480, 720, 960, 1440], 4 / 3, 0.5),
    "innenraum-leder": (15, [480, 720, 960, 1440], 4 / 3, 0.5),
    "innenreinigung-spray": (19, [480, 720, 960, 1440], 4 / 3, 0.5),
    "innenraum-lenkrad": (14, [480, 720, 960], 4 / 3, 0.5),
    "aufbereitung-politur": (29, [480, 720, 960], 3 / 4, 0.5),
    "aufbereitung-team": (28, [480, 720, 960], 3 / 4, 0.4),
    "felgenreinigung": (37, [480, 720, 960], 3 / 4, 0.5),
    "reifen-buerste": (38, [480, 720, 960], 3 / 4, 0.5),
    "mercedes-halle": (3, [480, 720, 960, 1440], 4 / 3, 0.5),
    "lack-seite": (55, [480, 720, 960], 4 / 3, 0.5),
    "kundenkarte-cabrio": (63, [480, 720, 960, 1440], 4 / 3, 0.5),
    "golf-schaum": (44, [480, 720, 960], 4 / 3, 0.5),
    "aktion-seniorentag": (69, [540, 1080], 1, 0.5),
    "aktion-seniorentag-preise": (70, [540, 1080], 1, 0.5),
    "dkv-uta": (12, [432, 864], 4 / 5, 0.5),
    "produkt-powertuch": (5, [400, 800], 4 / 5, 0.5),
    "produkt-mikrofaser": (6, [400, 800], 4 / 5, 0.5),
    "produkt-baklava": (7, [400, 800], 4 / 5, 0.5),
    "produkt-aquapremium": (8, [400, 800], 4 / 5, 0.5),
    "produkt-handschuh": (9, [400, 800], 4 / 5, 0.5),
    "produkt-leder": (10, [400, 800], 4 / 5, 0.5),
}


def crop_to(im, ratio, focus_y):
    w, h = im.size
    if ratio is None:
        return im
    if w / h > ratio:  # too wide -> crop sides
        nw = int(h * ratio)
        x = (w - nw) // 2
        return im.crop((x, 0, x + nw, h))
    nh = int(w / ratio)  # too tall -> crop top/bottom around focus
    y = int((h - nh) * focus_y)
    return im.crop((0, y, w, y + nh))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--src", required=True)
    ap.add_argument("--map", required=True)
    a = ap.parse_args()
    ids = [line.split("\t")[0].strip() for line in open(a.map, encoding="utf-8")]
    os.makedirs(OUT, exist_ok=True)
    written, total = [], 0
    for name, (idx, widths, ratio, fy) in SELECTION.items():
        im = ImageOps.exif_transpose(Image.open(os.path.join(a.src, ids[idx]))).convert("RGB")
        im = crop_to(im, ratio, fy)
        for w in widths:
            if w > im.size[0]:
                continue
            h = round(w / (im.size[0] / im.size[1]))
            path = os.path.join(OUT, f"{name}-{w}.webp")
            q = 60 if name.startswith("hero") else 68  # hero sits under a dark overlay
            im.resize((w, h), Image.LANCZOS).save(path, "WEBP", quality=q, method=6)
            total += os.path.getsize(path)
            written.append(os.path.basename(path))
        if name == "hero-schaumwaesche":
            og = crop_to(im, 1200 / 630, 0.55).resize((1200, 630), Image.LANCZOS)
            path = os.path.join(OUT, "og-aquastreet.jpg")
            og.save(path, "JPEG", quality=82, optimize=True, progressive=True)
            written.append(os.path.basename(path))
            total += os.path.getsize(path)
    # Logo: keep transparency, two sizes
    logo = Image.open(os.path.join(a.src, ids[0])).convert("RGBA")
    for w in (172, 344, 600):
        h = round(w * logo.size[1] / logo.size[0])
        path = os.path.join(OUT, f"logo-{w}.webp")
        logo.resize((w, h), Image.LANCZOS).save(path, "WEBP", quality=82, method=6)
        written.append(os.path.basename(path))
        total += os.path.getsize(path)
    png = os.path.join(OUT, "logo.png")
    logo.resize((600, round(600 * logo.size[1] / logo.size[0])), Image.LANCZOS).save(png, optimize=True)
    written.append("logo.png")
    print(json.dumps({"written": written, "bytes": total}))


if __name__ == "__main__":
    main()
