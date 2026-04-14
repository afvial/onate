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
    lines = extract_lines(path)

    # ── Detección y eliminación del reclamo (catchword) ──────────────────────
    # El reclamo es la última línea de la columna: una sola palabra corta,
    # sin guión de corte (soft_hyphen=False). Se emite en stdout para que
    # el script de shell lo pase como --join-left a la columna siguiente.
    if args.strip_catchword and lines:
        last = lines[-1]
        last_text = last["text"].strip()
        words = last_text.split()
        is_catchword = (
            len(words) <= 2          # máximo dos palabras (sílaba o palabra entera)
            and len(last_text) <= 20 # longitud razonable para un reclamo
            and not last["soft_hyphen"]  # los reclamos no llevan guión de corte
        )
        if is_catchword:
            lines = lines[:-1]
            # Imprimir el texto del reclamo en stdout para captura en shell
            print(last_text)
            print(f"  Reclamo detectado y eliminado: «{last_text}»",
                  file=sys.stderr)
        else:
            print(f"  --strip-catchword: última línea no parece reclamo «{last_text}», "
                  "se conserva.", file=sys.stderr)
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
        div  = lines_to_tei(lines, args.page, join_left=args.join_left)
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

