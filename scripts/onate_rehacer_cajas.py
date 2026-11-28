#!/usr/bin/env python3
"""
Rehace las cajas de las palabras de una línea del PAGE XML cuando Transkribus
las segmentó mal (anchura cero, amontonadas, desplazadas). Reparte el ancho
total de la línea entre sus palabras según el ancho aproximado de sus letras.
Uso: python3 scripts/onate_rehacer_cajas.py 51 der tr_1_tl_60 [--dry-run]
"""
import argparse
from pathlib import Path
from lxml import etree

NS = "http://schema.primaresearch.org/PAGE/gts/pagecontent/2013-07-15"
T = lambda n: f"{{{NS}}}{n}"
U = lambda el: el.find(f"{T('TextEquiv')}/{T('Unicode')}")

def caja(w):
    pts = [tuple(map(int, q.split(","))) for q in w.find(T("Coords")).get("points").split()]
    return min(p[0] for p in pts), max(p[0] for p in pts), min(p[1] for p in pts), max(p[1] for p in pts)

def peso(t):
    return sum(0.5 if c in "iltfſrj.,;:1" else 1.5 if c in "mwMW" else 1.0 for c in t) + 1.0

ap = argparse.ArgumentParser(); ap.add_argument("pagina"); ap.add_argument("columna"); ap.add_argument("linea")
ap.add_argument("--dry-run", action="store_true")
a = ap.parse_args()
path = Path(f"transkribus/disp63/pg_63_{a.pagina}_{a.columna}.xml")
tree = etree.parse(str(path))
line = tree.find(f".//{T('TextLine')}[@id='{a.linea}']")
if line is None: raise SystemExit(f"No existe la línea {a.linea} en {path}")
ws = line.findall(T("Word"))
cs = [caja(w) for w in ws]
print("antes:  ", " | ".join(f"{U(w).text} {c[0]}–{c[1]}" for w, c in zip(ws, cs)))
x1, x2 = min(c[0] for c in cs), max(c[1] for c in cs)
y1, y2 = min(c[2] for c in cs), max(c[3] for c in cs)
total = sum(peso(U(w).text or "") for w in ws); x = x1; hueco = (x2 - x1) / total * 0.8
for w in ws:
    ancho = (x2 - x1) * peso(U(w).text or "") / total
    i, f = round(x), round(x + ancho - hueco)
    w.find(T("Coords")).set("points", f"{i},{y1} {i},{y2} {f},{y2} {f},{y1}"); x += ancho
print("después:", " | ".join(f"{U(w).text} {caja(w)[0]}–{caja(w)[1]}" for w in ws))
if a.dry_run:
    print("(dry-run: no se ha escrito nada)")
else:
    tree.write(str(path), encoding="UTF-8", xml_declaration=True)
    print(f"Escrito {path}. Procesa la página: ./procesar_pagina.sh {a.pagina} {a.columna} --skip search,rdf")
