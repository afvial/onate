#!/usr/bin/env python3
"""
Envuelve en <placeName ref="#id"> (o <rs type="place" ref="#id">) las palabras
cuyo lema figura en lugares.tsv. Se ejecuta después del NLP, sobre src/.
Uso: python3 scripts/onate_lugares.py src/disp63/pg_63_46_der.xml [...]
"""
import csv, sys
from pathlib import Path
from lxml import etree

TEI = "http://www.tei-c.org/ns/1.0"
T = lambda n: f"{{{TEI}}}{n}"
WRAP = {T(x) for x in ("choice", "orig", "reg", "abbr", "expan", "sic", "corr")}

def load(path):
    m = {}
    with open(path, encoding="utf-8") as f:
        for row in csv.reader(f, delimiter="\t"):
            if not row or row[0].startswith("#") or row[0] == "lema":
                continue
            m[row[0]] = (row[1], row[2] if len(row) > 2 and row[2] else "placeName")
    return m

def main():
    lug = load(Path("lugares.tsv"))
    for path in sys.argv[1:]:
        tree = etree.parse(path); n = 0
        for w in list(tree.iter(T("w"))):
            if w.get("lemma") not in lug:
                continue
            top = w
            while top.getparent() is not None and top.getparent().tag in WRAP:
                top = top.getparent()
            par = top.getparent()
            if par is None or par.tag in (T("placeName"), T("rs")):
                continue
            ref, el = lug[w.get("lemma")]
            wrap = etree.Element(T(el))
            if el == "rs":
                wrap.set("type", "place")
            wrap.set("ref", "#" + ref)
            wrap.tail, top.tail = top.tail, None
            par.replace(top, wrap)
            wrap.append(top)
            n += 1
        tree.write(path, encoding="UTF-8", xml_declaration=True)
        print(f"  ✓ {n} lugar(es) en {path}", file=sys.stderr)

if __name__ == "__main__":
    main()
