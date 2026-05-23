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


def _norm(text: str) -> str:
    """Normalizar texto para matching: minúsculas, ſ→s, æ→ae, sin puntuación."""
    import unicodedata
    text = text.lower()
    for a, b in [('ſ','s'),('æ','ae'),('œ','oe'),('¬',''),('-','')]:
        text = text.replace(a, b)
    return ''.join(
        c for c in text if not unicodedata.category(c).startswith('P')
    ).strip()


def _align(tran_words: list, tess_words: list) -> list:
    """
    Alinea palabras de Transkribus (texto fiable) con bboxes de Tesseract.
    Devuelve lista de {"text": str, "bbox": dict}.
    """
    if not tess_words:
        return []
    if not tran_words:
        return tess_words

    n_t, n_s = len(tran_words), len(tess_words)

    # Caso simple: mismo número → 1:1 directo
    if n_t == n_s:
        return [{"text": tw, "bbox": tv["bbox"]}
                for tw, tv in zip(tran_words, tess_words)]

    result   = [None] * n_t
    used     = set()

    # Fase 1: match por texto normalizado
    for i, tw in enumerate(tran_words):
        tn = _norm(tw)
        if len(tn) < 2:
            continue
        best_j, best_sc = -1, 3.1
        for j, tv in enumerate(tess_words):
            if j in used:
                continue
            tn2 = _norm(tv["text"])
            if tn2 == tn:
                sc = 0
            elif tn2.startswith(tn) or tn.startswith(tn2):
                sc = abs(len(tn2) - len(tn)) * 0.5
            else:
                continue
            if sc < best_sc:
                best_sc, best_j = sc, j
        if best_j >= 0:
            result[i] = {"text": tw, "bbox": tess_words[best_j]["bbox"]}
            used.add(best_j)

    # Fase 2: rellenar huecos por posición X proporcional
    x_min     = min(tv["bbox"]["x"] for tv in tess_words)
    x_max     = max(tv["bbox"]["x"] + tv["bbox"]["w"] for tv in tess_words)
    line_w    = max(x_max - x_min, 1)
    total_ch  = sum(len(w) + 1 for w in tran_words) or 1
    chars_acc = 0

    for i, tw in enumerate(tran_words):
        if result[i] is None:
            cx = x_min + (chars_acc + len(tw) / 2) / total_ch * line_w
            best_j, best_d = -1, float('inf')
            for j, tv in enumerate(tess_words):
                if j in used:
                    continue
                d = abs(tv["bbox"]["x"] + tv["bbox"]["w"] / 2 - cx)
                if d < best_d:
                    best_d, best_j = d, j
            if best_j >= 0:
                result[i] = {"text": tw, "bbox": tess_words[best_j]["bbox"]}
                used.add(best_j)
            else:
                # Bbox sintético entre vecinos
                prev = next((r["bbox"] for r in reversed(result[:i]) if r), tess_words[0]["bbox"])
                nxt  = next((r["bbox"] for r in result[i+1:] if r), tess_words[-1]["bbox"])
                est_x = (prev["x"] + prev["w"] + nxt["x"]) // 2
                est_w = max(8, (nxt["x"] - prev["x"] - prev["w"]) // 2)
                result[i] = {"text": tw, "bbox": {
                    "x": est_x, "y": prev["y"], "w": est_w, "h": prev["h"]
                }}
        chars_acc += len(tw) + 1

    return [r for r in result if r is not None]


def add_tesseract_words(data: dict, img_path: str) -> int:
    """
    Enriquece data["lines"] con coordenadas de palabras.
    Estrategia:
      1. Divide el texto Transkribus de cada línea en palabras.
      2. Corre Tesseract (--psm 7) en el recorte de cada línea.
      3. Alinea texto Transkribus ↔ bboxes Tesseract.
      4. Marca "broken_end" / "broken_start" para palabras cortadas (¬).
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

    print("  Ejecutando Tesseract por línea (psm 7) + alineación Transkribus…")
    img = Image.open(img_file).convert("RGB")
    W, H = img.size

    sorted_lnums = sorted(data["lines"].keys(), key=int)
    enriched = 0

    for k, lnum in enumerate(sorted_lnums):
        ldata = data["lines"][lnum]
        if ldata.get("words"):
            continue

        b = ldata["bbox"]
        tran_text = ldata.get("text", "").strip()

        # Palabras de Transkribus (sin el ¬ final)
        tran_words = [w.rstrip("¬") for w in tran_text.split() if w.strip("¬")]

        # Recorte de la línea con padding
        pad = 5
        x0, y0 = max(0, b["x"] - pad), max(0, b["y"] - pad)
        x1, y1 = min(W, b["x"] + b["w"] + pad), min(H, b["y"] + b["h"] + pad)
        line_crop = img.crop((x0, y0, x1, y1))

        try:
            td = pytesseract.image_to_data(
                line_crop, lang="lat",
                config="--psm 7 --oem 1",
                output_type=pytesseract.Output.DICT,
            )
        except Exception as e:
            print(f"  Aviso línea {lnum}: {e}", file=sys.stderr)
            continue

        tess_words = []
        for i in range(len(td["text"])):
            t = td["text"][i].strip()
            if not t or int(td["conf"][i]) < 15:
                continue
            tess_words.append({
                "bbox": {
                    "x": td["left"][i] + x0,
                    "y": td["top"][i] + y0,
                    "w": td["width"][i],
                    "h": td["height"][i],
                },
                "text": t,
            })
        tess_words.sort(key=lambda w: w["bbox"]["x"])

        if not tess_words:
            continue

        aligned = _align(tran_words, tess_words)
        if aligned:
            ldata["words"] = aligned
            # Marcar si la línea termina con palabra cortada (¬)
            if tran_text.endswith("¬"):
                ldata["broken_end"] = True
            enriched += 1

    # Marcar líneas que empiezan con continuación de palabra cortada
    for k, lnum in enumerate(sorted_lnums):
        if k == 0:
            continue
        prev_lnum = sorted_lnums[k - 1]
        if data["lines"][prev_lnum].get("broken_end"):
            data["lines"][lnum]["broken_start"] = True

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
