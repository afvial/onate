#!/usr/bin/env python3
"""
onate_export_catalog.py — Exporta listBibl + listPerson de tei_header.xml
                           a un JSON plano para el tooltip de citas del HTML.

El HTML de salida referencia cada cita con data-corresp="#bib_XXX". Este
script produce un JSON {bib_XXX: {author, title}} para que el JS del
visor pueble el tooltip sin depender de la estructura interna (frágil)
de cada <bibl> individual dentro de los archivos de página.

Uso:
    python3 onate_export_catalog.py tei_header.xml --out bibl_catalog.json
"""

import argparse
import json
import sys
from pathlib import Path
from lxml import etree

TEI_NS = "http://www.tei-c.org/ns/1.0"
XML_NS = "http://www.w3.org/XML/1998/namespace"
TEI = f"{{{TEI_NS}}}"
XML = f"{{{XML_NS}}}"


def xml_id(el):
    return el.get(f"{XML}id", "")


def text_of(el):
    """Texto completo de un elemento (concatenando descendientes)."""
    if el is None:
        return ""
    return " ".join(el.itertext()).strip()


def pick_title(bibl_el):
    """
    Elige el título más adecuado para el tooltip:
    1. <title xml:lang="la"> con @type="translated"
    2. cualquier <title xml:lang="la">
    3. el primer <title> que haya, sea cual sea su idioma
    """
    titles = bibl_el.findall(f"{TEI}title")
    if not titles:
        return ""

    for t in titles:
        if t.get(f"{XML}lang") == "la" and t.get("type") == "translated":
            return text_of(t)
    for t in titles:
        if t.get(f"{XML}lang") == "la":
            return text_of(t)
    return text_of(titles[0])


def build_person_names(root):
    """{xml:id del <person>: nombre en latín (o el primero disponible)}."""
    names = {}
    for person in root.iter(f"{TEI}person"):
        pid = xml_id(person)
        if not pid:
            continue
        names_el = person.findall(f"{TEI}persName")
        if not names_el:
            continue
        chosen = None
        for n in names_el:
            if n.get(f"{XML}lang") == "la":
                chosen = n
                break
        if chosen is None:
            chosen = names_el[0]
        names[pid] = text_of(chosen)
    return names


def build_catalog(tei_header_path: Path) -> dict:
    tree = etree.parse(str(tei_header_path))
    root = tree.getroot()

    person_names = build_person_names(root)

    catalog = {}
    for bibl in root.iter(f"{TEI}bibl"):
        bib_id = xml_id(bibl)
        if not bib_id:
            continue

        author_el = bibl.find(f"{TEI}author")
        author_name = ""
        if author_el is not None:
            ref = author_el.get("ref", "").lstrip("#")
            if ref and ref in person_names:
                author_name = person_names[ref]
            else:
                # sin @ref resoluble: usar el texto inline del <author>
                author_name = text_of(author_el)

        title = pick_title(bibl)

        catalog[bib_id] = {
            "author": author_name,
            "title": title,
        }

    return catalog


def main():
    ap = argparse.ArgumentParser(
        description="Exporta listBibl/listPerson de tei_header.xml a JSON")
    ap.add_argument("input", type=Path, help="Ruta a tei_header.xml")
    ap.add_argument("--out", type=Path, required=True,
                     help="Ruta del JSON de salida")
    args = ap.parse_args()

    if not args.input.exists():
        sys.exit(f"ERROR: no se encuentra {args.input}")

    catalog = build_catalog(args.input)

    if not catalog:
        print("⚠ No se encontró ningún <bibl xml:id=...> en listBibl. "
              "¿Es el archivo correcto?", file=sys.stderr)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2, sort_keys=True)

    print(f"✓ {len(catalog)} entradas → {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
