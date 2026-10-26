#!/usr/bin/env python3
"""Lista los <bibl> sin @corresp (citas aún no identificadas) de bibl/disp63."""
from lxml import etree
from pathlib import Path
NS = {"t": "http://www.tei-c.org/ns/1.0"}
for f in sorted(Path("bibl/disp63").glob("*_bibl.xml")):
    for b in etree.parse(str(f)).xpath("//t:bibl[not(@corresp)]", namespaces=NS):
        ws = [w.text.strip() for w in b.xpath(".//t:w[not(ancestor::t:expan or ancestor::t:reg or ancestor::t:corr)]",
                                              namespaces=NS) if w.text]
        print(f"{f.stem.replace('_bibl',''):14} {' '.join(ws)[:60]}")
