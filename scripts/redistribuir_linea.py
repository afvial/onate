#!/usr/bin/env python3
"""Reparte las cajas de las palabras de una línea del PAGE XML a lo largo de su
anchura, según el ancho aproximado de cada letra. Para líneas mal segmentadas
por Transkribus. Uso:
    python3 scripts/redistribuir_linea.py PAGE.xml tr_1_tl_N [x_ini x_fin]
Sin x_ini/x_fin, toma los extremos del Baseline."""
import sys
from lxml import etree
NS = "http://schema.primaresearch.org/PAGE/gts/pagecontent/2013-07-15"
T = lambda n: f"{{{NS}}}{n}"
path, lid = sys.argv[1], sys.argv[2]
tree = etree.parse(path)
line = tree.find(f".//{T('TextLine')}[@id='{lid}']")
assert line is not None, f"no encuentro {lid}"
words = line.findall(T("Word"))
txt = [w.findtext(f".//{T('Unicode')}") or "" for w in words]
if len(sys.argv) >= 5:
    x0, x1 = int(sys.argv[3]), int(sys.argv[4])
else:
    bl = [tuple(map(int, p.split(","))) for p in line.find(T("Baseline")).get("points").split()]
    x0, x1 = min(p[0] for p in bl), max(p[0] for p in bl)
ys = [int(p.split(",")[1]) for w in words for p in w.find(T("Coords")).get("points").split()]
y0, y1 = min(ys), max(ys)
NARROW, WIDE = set("iljtfſr.,;:'!|¬"), set("mwMWæœÆŒ&")
wlen = lambda t: sum(0.45 if c in NARROW else 1.5 if c in WIDE else 1.0 for c in t)
GAP = 0.9
unit = (x1 - x0) / (sum(wlen(t) for t in txt) + GAP * (len(txt) - 1))
x = x0
for w, t in zip(words, txt):
    a, b = round(x), round(x + wlen(t) * unit)
    w.find(T("Coords")).set("points", f"{a},{y0} {a},{y1} {b},{y1} {b},{y0}")
    print(f"  {w.get('id'):<18} {t:<14} x={a}–{b}")
    x += (wlen(t) + GAP) * unit
tree.write(path, encoding="UTF-8", xml_declaration=True)
