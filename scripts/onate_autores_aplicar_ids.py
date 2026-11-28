#!/usr/bin/env python3
"""
Añade al header los <idno> de notas/autores_ids.tsv (columnas wikidata y viaf).
No toca los identificadores que ya existan. Uso: python3 scripts/onate_autores_aplicar_ids.py [--dry-run]
"""
import csv, re, sys
from pathlib import Path
seco = "--dry-run" in sys.argv
p = Path("tei_header.xml"); h = p.read_text(encoding="utf-8"); n = 0
for r in csv.DictReader(Path("notas/autores_ids.tsv").open(encoding="utf-8"), delimiter="\t"):
    q, v = (r.get("wikidata") or "").strip(), (r.get("viaf") or "").strip()
    if not (q or v): continue
    if q and not re.fullmatch(r"Q\d+", q): print(f"⚠ {r['pers_id']}: wikidata no válido «{q}»"); continue
    if v and not re.fullmatch(r"\d+", v): print(f"⚠ {r['pers_id']}: viaf no válido «{v}»"); continue
    m = re.search(rf'(<person xml:id="{re.escape(r["pers_id"])}">.*?)(\n(\s*)</person>)', h, flags=re.S)
    if not m: print(f"⚠ no encuentro {r['pers_id']}"); continue
    cuerpo, ind = m.group(1), m.group(3) + "  "
    extra = ""
    if q and 'type="wikidata"' not in cuerpo: extra += f'\n{ind}<idno type="wikidata">{q}</idno>'
    if v and not re.search(r'type="(VIAF|viaf)"', cuerpo): extra += f'\n{ind}<idno type="VIAF">{v}</idno>'
    if extra:
        h = h[:m.end(1)] + extra + h[m.end(1):]; n += 1
        print(f"✓ {r['pers_id']}: {q or '—'} / {v or '—'}")
if seco: print(f"(dry-run) {n} autores se actualizarían"); sys.exit()
p.write_text(h, encoding="utf-8"); print(f"{n} autores actualizados en {p}")
