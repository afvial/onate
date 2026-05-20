#!/usr/bin/env python3
"""
onate_coords.py — Extrae coordenadas de líneas y palabras del PAGE XML de Transkribus.

Produce un JSON en coords/disp63/ con la estructura:
{
  "img_w": 1084,
  "img_h": 4017,
  "img_name": "pg_63_39_der.png",
  "lines": {
    "1":  { "bbox": {"x":15,"y":14,"w":1054,"h":58}, "text": "vermis, quam gemma…" },
    "2":  { "bbox": {"x":13,"y":81,"w":1062,"h":57}, "text": "magis necessarios…",
            "words": [                      ← solo si Transkribus exportó word-level
              {"bbox":{"x":13,"y":83,"w":150,"h":53}, "text":"magis"},
              …
            ]
          },
    …
  }
}

Las claves de "lines" son strings del número de línea que corresponde
al atributo n de <lb n="N"/> en el TEI — ese es el vínculo texto↔imagen.

Uso:
    python3 scripts/onate_coords.py transkribus/disp63/pg_63_39_der.xml \\
            --out coords/disp63/pg_63_39_der.json \\
            --img facsimiles/disp63/pg_63_39_der.png

    # O integrado en procesar_pagina.sh:
    python3 scripts/onate_coords.py "$PAGE_XML" --out "$COORDS_JSON" --img "$IMG"
"""

import argparse
import json
import re
import sys
from pathlib import Path

try:
    from lxml import etree
except ImportError:
    sys.exit("ERROR: lxml no encontrado — pip install lxml")

# Namespace del PAGE XML de Transkribus (puede variar según versión)
_NS_CANDIDATES = [
    "http://schema.primaresearch.org/PAGE/gts/pagecontent/2013-07-15",
    "http://schema.primaresearch.org/PAGE/gts/pagecontent/2019-07-15",
    "http://schema.primaresearch.org/PAGE/gts/pagecontent/2010-03-19",
]


def _detect_ns(root):
    """Detecta el namespace correcto mirando el tag del elemento raíz."""
    tag = root.tag
    if tag.startswith("{"):
        ns = tag[1:tag.index("}")]
        return {"p": ns}
    # Sin namespace
    return {}


def points_to_bbox(points_str: str) -> dict:
    """
    Convierte la cadena de puntos del PAGE XML ('x1,y1 x2,y2 …')
    al rectángulo envolvente {x, y, w, h}.
    """
    pts = []
    for tok in points_str.strip().split():
        parts = tok.split(",")
        if len(parts) == 2:
            try:
                pts.append((int(parts[0]), int(parts[1])))
            except ValueError:
                continue
    if not pts:
        return {"x": 0, "y": 0, "w": 0, "h": 0}
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    x0, y0 = min(xs), min(ys)
    return {"x": x0, "y": y0, "w": max(xs) - x0, "h": max(ys) - y0}


def line_num_from_id(tl_id: str) -> int | None:
    """
    Extrae el número de línea del ID de Transkribus.
    Soporta los patrones más comunes:
      tr_1_tl_52  →  52
      line_52     →  52
      tl52        →  52
    """
    m = re.search(r"(?:tl[_]?|line[_]?)(\d+)$", tl_id, re.IGNORECASE)
    return int(m.group(1)) if m else None


def extract_coords(page_xml_path: Path, img_override: str | None = None) -> dict:
    """
    Parsea el PAGE XML y devuelve el diccionario de coordenadas.
    """
    tree = etree.parse(str(page_xml_path))
    root = tree.getroot()
    ns = _detect_ns(root)

    def find(el, xpath):
        if ns:
            return el.find(xpath, ns)
        # Eliminar prefijos de namespace del xpath
        xpath_clean = re.sub(r"p:", "", xpath)
        return el.find(xpath_clean)

    def findall(el, xpath):
        if ns:
            return el.findall(xpath, ns)
        xpath_clean = re.sub(r"p:", "", xpath)
        return el.findall(xpath_clean)

    page = find(root, ".//p:Page")
    img_w = int(page.get("imageWidth", 0)) if page is not None else 0
    img_h = int(page.get("imageHeight", 0)) if page is not None else 0
    img_name = img_override or (page.get("imageFilename", "") if page is not None else "")

    lines = {}
    skipped = 0

    for tl in findall(root, ".//p:TextLine"):
        tl_id = tl.get("id", "")
        line_num = line_num_from_id(tl_id)

        if line_num is None:
            skipped += 1
            continue

        coords_el = find(tl, "p:Coords")
        if coords_el is None:
            skipped += 1
            continue

        bbox = points_to_bbox(coords_el.get("points", ""))

        # Texto de la línea
        text_el = find(tl, ".//p:TextEquiv/p:Unicode")
        text = (text_el.text or "").strip() if text_el is not None else ""

        entry = {"bbox": bbox, "text": text}

        # Palabras individuales (solo si Transkribus las segmentó)
        words = []
        for word in findall(tl, ".//p:Word"):
            w_coords = find(word, "p:Coords")
            w_text = find(word, ".//p:TextEquiv/p:Unicode")
            if w_coords is None:
                continue
            w_bbox = points_to_bbox(w_coords.get("points", ""))
            w_str = (w_text.text or "").strip() if w_text is not None else ""
            words.append({"bbox": w_bbox, "text": w_str})

        if words:
            entry["words"] = words

        lines[str(line_num)] = entry

    if skipped:
        print(f"  Líneas omitidas (ID no reconocido): {skipped}", file=sys.stderr)

    return {
        "img_w": img_w,
        "img_h": img_h,
        "img_name": img_name,
        "lines": lines,
    }


def add_tesseract_words(data: dict, img_path: str) -> int:
    """
    Enriquece data["lines"] con coordenadas de palabras via Tesseract.
    Solo actúa en líneas que no tienen words de Transkribus.
    Devuelve el número de líneas enriquecidas.
    """
    img_file = Path(img_path)
    if not img_file.exists():
        print(f"  Aviso: imagen no encontrada en {img_file}.", file=sys.stderr)
        return 0
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        print("  Aviso: pytesseract/Pillow no disponibles.", file=sys.stderr)
        return 0

    print("  Ejecutando Tesseract para coordenadas de palabras…")
    img   = Image.open(img_file).convert("RGB")
    tdata = pytesseract.image_to_data(img, lang="lat", output_type=pytesseract.Output.DICT)

    enriched = 0
    for lnum, ldata in data["lines"].items():
        if ldata.get("words"):
            continue
        b = ldata["bbox"]
        line_words = []
        for i in range(len(tdata["text"])):
            t = tdata["text"][i].strip()
            if not t or int(tdata["conf"][i]) < 20:
                continue
            wy = tdata["top"][i] + tdata["height"][i] * 0.5
            if b["y"] <= wy <= b["y"] + b["h"]:
                line_words.append({
                    "bbox": {
                        "x": tdata["left"][i],
                        "y": tdata["top"][i],
                        "w": tdata["width"][i],
                        "h": tdata["height"][i],
                    },
                    "text": t,
                })
        line_words.sort(key=lambda w: w["bbox"]["x"])
        if line_words:
            ldata["words"] = line_words
            enriched += 1

    return enriched


def main():
    ap = argparse.ArgumentParser(description="Extrae coordenadas del PAGE XML de Transkribus.")
    ap.add_argument("page_xml", type=Path, help="Ruta al PAGE XML de Transkribus")
    ap.add_argument("--out",    type=Path, default=None,
                    help="Ruta del JSON de salida")
    ap.add_argument("--img",    type=str,  default=None,
                    help="Ruta de la imagen. Si existe, Tesseract añade coords de palabras.")
    ap.add_argument("--no-ocr", action="store_true",
                    help="No ejecutar Tesseract aunque --img esté presente.")
    ap.add_argument("--pretty", action="store_true",
                    help="JSON con indentación (para depuración)")
    args = ap.parse_args()

    if not args.page_xml.exists():
        sys.exit(f"ERROR: no se encuentra {args.page_xml}")

    out_path = args.out
    if out_path is None:
        out_dir = args.page_xml.parent.parent.parent / "coords" / args.page_xml.parent.name
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / (args.page_xml.stem + ".json")

    print(f"Leyendo {args.page_xml} …")
    data = extract_coords(args.page_xml, img_override=args.img)

    tess_lines = 0
    if args.img and not args.no_ocr:
        tess_lines = add_tesseract_words(data, args.img)

    n_lines = len(data["lines"])
    n_words = sum(len(v.get("words", [])) for v in data["lines"].values())

    indent = 2 if args.pretty else None
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=indent))

    print(f"  Imagen:  {data['img_name']}  ({data['img_w']}×{data['img_h']} px)")
    print(f"  Líneas:  {n_lines}")
    if tess_lines:
        print(f"  Palabras (Tesseract): {n_words} en {tess_lines} líneas  ✓")
    else:
        print(f"  Palabras: {n_words}  {'✓' if n_words else '— (solo líneas)'}")
    print(f"  → {out_path}")


if __name__ == "__main__":
    main()
