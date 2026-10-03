#!/usr/bin/env python3
"""
onate_lila_index.py — Construye un índice local del LiLa Lemma Bank.

Se ejecuta UNA vez (o al actualizar la versión de LiLa). Lee el Turtle
del Lemma Bank y genera un JSON  forma_normalizada → [candidatos], que la
etapa `lila` del pipeline (onate_lila.py) consulta sin conexión.

Fuente del Turtle (CC BY-SA 4.0, CIRCSE / Università Cattolica):
    https://github.com/CIRCSE/LiLa_Lemma-Bank  →  rdf/lemmaBank.ttl

Uso:
    mkdir -p cache
    curl -L -o cache/lemmaBank.ttl \
        https://raw.githubusercontent.com/CIRCSE/LiLa_Lemma-Bank/master/rdf/lemmaBank.ttl
    python3 scripts/onate_lila_index.py cache/lemmaBank.ttl cache/lila_index.json

El parser es un lector por bloques adaptado al formato en que LiLa
publica el Turtle (un sujeto por bloque, propiedades indentadas). Es
mucho más rápido y ligero que rdflib (que necesita ~2 GB de RAM para
este archivo). Si LiLa cambiara el formato, usa --rdflib.
"""

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from collections import defaultdict
from datetime import date

SUBJ_RE = re.compile(r"^(lilaLemma|lilaIpoLemma):(\d+)\s+a\s+lila:(Lemma|Hypolemma)\b")
POS_RE = re.compile(r"lila:hasPOS\s+lila:(\w+)")
LIT_RE = re.compile(r'"((?:[^"\\]|\\.)*)"@la')
LABEL_RE = re.compile(r'rdfs:label\s+"((?:[^"\\]|\\.)*)"')
HYPO_OF_RE = re.compile(r"lila:isHypolemma\s+lilaLemma:(\d+)")


def norm(s: str) -> str:
    """Clave de búsqueda: minúsculas, sin diacríticos, u/v e i/j unificadas."""
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.lower().replace("v", "u").replace("j", "i")
    s = s.replace("æ", "ae").replace("œ", "oe")
    return s.strip()


def parse_blocks(path):
    """Lector por bloques del Turtle de LiLa. Devuelve dicts por (hipo)lema."""
    current = None
    in_wr = False
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                if current:
                    yield current
                current = None
                continue
            m = SUBJ_RE.match(line)
            if m:
                if current:
                    yield current
                current = {
                    "id": m.group(2),
                    "type": "lemma" if m.group(3) == "Lemma" else "hypolemma",
                    "pos": None, "wr": [], "of": None, "label": None,
                }
                in_wr = False
            if current is None:
                continue
            if (p := POS_RE.search(line)):
                current["pos"] = p.group(1)
            if (lb := LABEL_RE.search(line)):
                current["label"] = lb.group(1)
            # writtenRep puede tener varios valores ("a"@la , "b"@la) y,
            # en teoría, continuar en líneas siguientes.
            if "ontolex:writtenRep" in line:
                in_wr = True
            if in_wr:
                current["wr"].extend(LIT_RE.findall(line))
                if line.rstrip().endswith((";", ".")):
                    in_wr = False
            if (h := HYPO_OF_RE.search(line)):
                current["of"] = h.group(1)
    if current:
        yield current


def parse_rdflib(path):
    """Alternativa robusta (lenta, ~2 GB de RAM)."""
    import rdflib
    from rdflib.namespace import RDF, RDFS
    LILA = rdflib.Namespace("http://lila-erc.eu/ontologies/lila/")
    ONTOLEX = rdflib.Namespace("http://www.w3.org/ns/lemon/ontolex#")
    g = rdflib.Graph()
    g.parse(path, format="turtle")
    for cls, typ in ((LILA.Lemma, "lemma"), (LILA.Hypolemma, "hypolemma")):
        for s in g.subjects(RDF.type, cls):
            pos = g.value(s, LILA.hasPOS)
            of = g.value(s, LILA.isHypolemma)
            lb = g.value(s, RDFS.label)
            yield {
                "label": str(lb) if lb else None,
                "id": str(s).rsplit("/", 1)[1],
                "type": typ,
                "pos": str(pos).rsplit("/", 1)[1] if pos else None,
                "wr": [str(o) for o in g.objects(s, ONTOLEX.writtenRep)],
                "of": str(of).rsplit("/", 1)[1] if of else None,
            }


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("ttl", help="cache/lemmaBank.ttl")
    ap.add_argument("out", help="cache/lila_index.json")
    ap.add_argument("--rdflib", action="store_true", help="usar rdflib en vez del lector por bloques")
    args = ap.parse_args()

    entries = defaultdict(list)
    counts = defaultdict(int)
    parser = parse_rdflib if args.rdflib else parse_blocks
    for rec in parser(args.ttl):
        counts[rec["type"]] += 1
        for wr in set(rec["wr"]):
            # canon=True: la forma es la de cita (rdfs:label); False: variante gráfica
            canon = rec["label"] is None or norm(wr) == norm(rec["label"])
            cand = {"id": rec["id"], "type": rec["type"], "pos": rec["pos"],
                    "wr": wr, "canon": canon}
            if rec["of"]:
                cand["of"] = rec["of"]
            entries[norm(wr)].append(cand)

    if counts["lemma"] < 100_000:
        sys.exit(f"Error: solo {counts['lemma']} lemas leídos; ¿cambió el formato? Prueba con --rdflib")

    sha = hashlib.sha256(open(args.ttl, "rb").read()).hexdigest()[:16]
    data = {
        "meta": {
            "source": "https://github.com/CIRCSE/LiLa_Lemma-Bank (rdf/lemmaBank.ttl)",
            "license": "CC BY-SA 4.0",
            "sha256_16": sha,
            "built": date.today().isoformat(),
            "lemmas": counts["lemma"],
            "hypolemmas": counts["hypolemma"],
            "keys": len(entries),
        },
        "entries": entries,
    }
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, separators=(",", ":"))
    print(f"OK: {counts['lemma']} lemas, {counts['hypolemma']} hipolemas, "
          f"{len(entries)} claves → {args.out}")


if __name__ == "__main__":
    main()
