#!/usr/bin/env python3
"""
Genera notas/autores_ids.tsv con los autores del header sin Wikidata ni VIAF:
id, nombres, fechas, obras y un enlace de búsqueda en Wikidata. Se rellenan
las columnas wikidata y viaf, y se aplican con onate_autores_aplicar_ids.py.
Conserva lo ya rellenado si la tabla existe.
"""
import csv, re, urllib.parse
from pathlib import Path
from lxml import etree
TEI = "{http://www.tei-c.org/ns/1.0}"
h = etree.parse("tei_header.xml")
obras = {}
for b in h.iter(f"{TEI}bibl"):
    a = b.find(f"{TEI}author")
    t = b.find(f"{TEI}title")
    if a is not None and a.get("ref") and t is not None:
        obras.setdefault(a.get("ref").lstrip("#"), []).append(" ".join(t.itertext()).strip())
salida = Path("notas/autores_ids.tsv")
previo = {}
if salida.exists():
    for r in csv.DictReader(salida.open(encoding="utf-8"), delimiter="\t"):
        previo[r["pers_id"]] = r
PRE = {  # identificadores buscados el 16-11 (pendientes de comprobar)
    "Sa": ("Q4403328", "32014889"), "Hieronymus": ("Q44248", "95147024"), "Pennaforte": ("Q318980", "79081365"),
    "Gandavo": ("Q707637", "37045656"), "Mediavilla": ("Q446656", "64802885"),
}
filas = []
for p in h.iter(f"{TEI}person"):
    pid = p.get("{http://www.w3.org/XML/1998/namespace}id")
    tipos = {i.get("type", "").lower() for i in p.findall(f"{TEI}idno")}
    if "wikidata" in tipos and "viaf" in tipos:
        continue
    nombres = [" ".join(n.itertext()).strip() for n in p.findall(f"{TEI}persName")]
    fechas = " – ".join(filter(None, [(e.text or e.get("when") or "") for e in (p.find(f"{TEI}birth"), p.find(f"{TEI}death")) if e is not None]))
    q, v = previo.get(pid, {}).get("wikidata", ""), previo.get(pid, {}).get("viaf", "")
    nota = previo.get(pid, {}).get("nota", "")
    for clave, (pq, pv) in PRE.items():
        if clave.lower() in pid.lower() and not q:
            q, v, nota = pq, pv, "comprobar (búsqueda del 16-11)"
    busca = "https://www.wikidata.org/w/index.php?search=" + urllib.parse.quote(nombres[-1] if nombres else pid)
    filas.append({"pers_id": pid, "nombres": " | ".join(nombres), "fechas": fechas,
                  "obras": " | ".join(obras.get(pid, [])), "wikidata": q, "viaf": v, "nota": nota, "buscar": busca})
salida.parent.mkdir(parents=True, exist_ok=True)
with salida.open("w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["pers_id", "nombres", "fechas", "obras", "wikidata", "viaf", "nota", "buscar"], delimiter="\t")
    w.writeheader(); w.writerows(filas)
print(f"{len(filas)} autores sin identificadores completos → {salida}")
