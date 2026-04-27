#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
onate_page2tei.py
─────────────────
Convierte PAGE XML de Transkribus en TEI XML diplomático.

Uso:
    python3 onate_page2tei.py PAGE.xml --out-xml src/disp63/pg35.xml --page 35
    python3 onate_page2tei.py PAGE.xml --out-txt transcriptions/disp63/pg35.txt
    python3 onate_page2tei.py PAGE.xml --out-xml pg35.xml --page 35 --verbose

Requiere: pip install lxml
Módulos propios (mismo directorio): onate_tokens, onate_bibl, onate_tei
"""

import sys
import argparse
from pathlib import Path
from lxml import etree

from onate_tokens import TEI_NS, extract_lines, apply_abbrev_tags
from onate_tei    import lines_to_tei, build_clean_txt

def main():
    parser = argparse.ArgumentParser(
        description="PAGE XML Transkribus → TXT diplomático y/o TEI XML"
    )
    parser.add_argument("page_xml", help="Archivo PAGE XML de Transkribus")
    parser.add_argument("--out-xml", "-x", help="TEI XML de salida")
    parser.add_argument("--out-txt", "-t", help="TXT diplomático de salida")
    parser.add_argument("--page",    "-p", type=int, default=0,
                        help="Número de página")
    parser.add_argument("--join-left", "-j",
                        help="Fragmento final de la columna anterior para fusionar "
                             "con la primera palabra (p.ej. 'con' si la col. izq. "
                             "terminaba en 'con¬' y esta empieza por 'sistit')")
    parser.add_argument("--strip-catchword", "-c", action="store_true",
                        help="Eliminar la última línea si es un reclamo tipográfico "
                             "(catchword). El texto detectado se imprime en stdout "
                             "para usarlo como --join-left de la columna siguiente.")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Mostrar líneas y abbrev tags detectados")
    args = parser.parse_args()

    path = Path(args.page_xml)
    if not path.exists():
        print(f"Error: {path} no encontrado", file=sys.stderr)
        sys.exit(1)
    if not args.out_xml and not args.out_txt:
        print("Error: especifica --out-xml y/o --out-txt", file=sys.stderr)
        sys.exit(1)

    print(f"Leyendo {path.name}...", file=sys.stderr)
    is_staging = etree.parse(str(path)).getroot().tag == "lines"
    lines = extract_lines(path)

    # ── Detección del reclamo tipográfico (catchword) ───────────────────────
    # El reclamo aparece al final de la columna como guía tipográfica al
    # encuadernador. Puede ser:
    #   - una sílaba muy corta (con, rem, vnde — típicamente ≤5 chars)
    #   - o una sílaba corta tras una línea con ¬ (reclamo en línea propia)
    #
    # CASO A — última línea tiene ¬:
    #   Palabra cortada normal. No se elimina; _emit_para_block añade
    #   <lb break="no"/> directamente al árbol TEI.
    #
    # CASO B — última línea sin ¬, corta, cumple al menos uno de:
    #   (B1) ≤5 caracteres (sílaba típica de reclamo: con, rem, vnde…)
    #   (B2) penúltima línea tiene ¬ (el reclamo completa la palabra cortada)
    #   Se elimina y se emite en stdout como --join-left para la col. siguiente.
    #
    # Palabras largas sin ¬ previo (ej. «pretium») se conservan siempre.
    if args.strip_catchword and lines:
        last = lines[-1]
        last_text = last["text"].strip()
        words = last_text.split()
        penultimate_hyphen = len(lines) >= 2 and lines[-2]["soft_hyphen"]

        if last["soft_hyphen"]:
            pass  # CASO A: onate_tei.py lo maneja

        elif (len(words) <= 2 and not last["soft_hyphen"] and not last.get("sic_spans")
              and (len(last_text) <= 5 or penultimate_hyphen)):
            # CASO B: reclamo tipográfico — eliminar y emitir como join_left
            lines = lines[:-1]
            catchword = last_text.rstrip(".-").rstrip("-").strip()
            print(catchword)
            print(f"  Reclamo detectado y eliminado: «{last_text}»", file=sys.stderr)

        else:
            print(f"  --strip-catchword: «{last_text}» se conserva.", file=sys.stderr)
    total_abbrevs = sum(len(l["abbrevs"]) for l in lines)
    total_hyphen  = sum(1 for l in lines if l["soft_hyphen"])
    print(f"  Líneas: {len(lines)}  |  Abreviaturas: {total_abbrevs}"
          f"  |  Guiones ¬: {total_hyphen}", file=sys.stderr)


    if args.verbose:
        for l in lines:
            segs = apply_abbrev_tags(l["text"], l["abbrevs"])
            abbr_str = "  " + " | ".join(
                f"«{s['text']}»→{s['expansion']}"
                for s in segs if s["is_abbrev"]
            ) if any(s["is_abbrev"] for s in segs) else ""
            print(f"  {'¬' if l['soft_hyphen'] else ' '} "
                  f"{l['text'][:55]:55s}{abbr_str}", file=sys.stderr)

    if args.out_txt:
        out = Path(args.out_txt)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(build_clean_txt(lines), encoding="utf-8")
        print(f"  TXT → {out}", file=sys.stderr)

    if args.out_xml:
        out = Path(args.out_xml)
        out.parent.mkdir(parents=True, exist_ok=True)
        div  = lines_to_tei(lines, args.page, join_left=args.join_left, staging=is_staging)
        tree = etree.ElementTree(div)
        tree.write(str(out), encoding="UTF-8",
                   xml_declaration=True, pretty_print=True)
        w  = len(div.findall(f".//{{{TEI_NS}}}w"))
        lb = len(div.findall(f".//{{{TEI_NS}}}lb"))
        ch = len(div.findall(f".//{{{TEI_NS}}}choice"))
        p  = len(div.findall(f".//{{{TEI_NS}}}p"))
        s  = len(div.findall(f".//{{{TEI_NS}}}s"))
        print(f"  XML → {out}", file=sys.stderr)
        print(f"    <p>:{p}  <s>:{s}  <w>:{w}  <lb/>:{lb}  <choice>:{ch}",
              file=sys.stderr)

    print("OK", file=sys.stderr)

if __name__ == "__main__":
    main()

