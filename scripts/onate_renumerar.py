#!/usr/bin/env python3
"""
Renumera las líneas de una columna (tr_1_tl_1, tr_1_tl_2…, sin huecos) en el
PAGE XML y en el staging a la vez, con los id de las palabras y el orden de
lectura. Sin huecos, el TEI y las coordenadas usan la misma numeración.
Uso: python3 scripts/onate_renumerar.py 48 izq [--comprobar]
"""
import argparse, re, sys
from pathlib import Path
from lxml import etree

NS = "http://schema.primaresearch.org/PAGE/gts/pagecontent/2013-07-15"
T = lambda n: f"{{{NS}}}{n}"

ap = argparse.ArgumentParser(); ap.add_argument("pagina"); ap.add_argument("columna")
ap.add_argument("--comprobar", action="store_true", help="solo comprobar, sin cambiar nada")
a = ap.parse_args()
pg = Path(f"transkribus/disp63/pg_63_{a.pagina}_{a.columna}.xml")
st = Path(f"staging/disp63/pg_63_{a.pagina}_{a.columna}.xml")
s = st.read_text(encoding="utf-8")
ids = re.findall(r'<line id="([^"]+)">', s)
malos = [(k + 1, i) for k, i in enumerate(ids) if i != f"tr_1_tl_{k+1}"]
if not malos:
    print(f"{len(ids)} líneas; numeración correcta"); sys.exit(0)
print(f"{len(ids)} líneas; {len(malos)} fuera de posición; primera: posición {malos[0][0]} = {malos[0][1]}")
if a.comprobar:
    sys.exit(1)
tree = etree.parse(str(pg)); lines = list(tree.iter(T("TextLine")))
if [l.get("id") for l in lines] != ids:
    sys.exit("El orden de las líneas no coincide entre el PAGE XML y el staging: no se cambia nada.")
mapa = {}
for k, line in enumerate(lines, 1):
    old, new = line.get("id"), f"tr_1_tl_{k}"; mapa[old] = new; line.set("id", new)
    cu = line.get("custom", "")
    if cu:
        line.set("custom", re.sub(r"readingOrder \{index:\d+;\}", f"readingOrder {{index:{k-1};}}", cu))
    for j, w in enumerate(line.findall(T("Word")), 1):
        w.set("id", f"{new}_w{j}")
tree.write(str(pg), encoding="UTF-8", xml_declaration=True)
st.write_text(re.sub(r'<line id="([^"]+)">', lambda m: f'<line id="{mapa[m.group(1)]}">', s), encoding="utf-8")
print(f"Renumeradas {sum(x != y for x, y in mapa.items())} líneas en {pg} y {st}")
print("Atención: los id de un archivo de correcciones ya preparado pueden haber cambiado.")
