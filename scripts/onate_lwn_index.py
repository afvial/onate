#!/usr/bin/env python3
"""
onate_lwn_index.py — Índice local del Latin WordNet (LiLa) por lemmaRef.

Se ejecuta UNA vez (o al actualizar el Latin WordNet). Lee el Turtle
revisado del Latin WordNet y genera un JSON que responde a:
    "¿qué sentidos (LexicalConcept / synset) tiene el lema lila:119455?"

Así el flujo de traducción puede proponer los sentidos de cada palabra
a partir del @lemmaRef que ya tiene en el TEI, sin buscar en la web.

Fuente (CIRCSE, Università Cattolica):
    https://github.com/CIRCSE/latinWordnet-revision  →  lwn31.ttl

Uso:
    curl -L -o cache/lwn31.ttl \
        https://raw.githubusercontent.com/CIRCSE/latinWordnet-revision/master/lwn31.ttl
    python3 scripts/onate_lwn_index.py cache/lwn31.ttl cache/lwn_index.json

Salida:
    {"meta": {...},
     "lemmas":  {"lila:119455": ["05171334-n", ...], "lilah:111474": [...]},
     "synsets": {"05171334-n": {"def": "...", "latin": ["pretium", ...]}}}

Los ids de synset son los mismos que cierran las URIs que ya usas en
senses/:  http://lila-erc.eu/data/lexicalResources/LatinWordNet/id/LexicalConcept/<id>
"""

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from datetime import date

CONCEPT_BASE = "http://lila-erc.eu/data/lexicalResources/LatinWordNet/id/LexicalConcept/"

SUBJ_RE = re.compile(r"^(wordnetLexicalEntry|wordnetSynset):(\S+)\s")
CANON_RE = re.compile(r"ontolex:canonicalForm\s+(lilaLemma|lilaIpoLemma):(\d+)")
SYN_RE = re.compile(r"wordnetSynset:([\w-]+)")
LABEL_RE = re.compile(r'rdfs:label\s+"((?:[^"\\]|\\.)*)"')
DEF_RE = re.compile(r'skos:definition\s+"((?:[^"\\]|\\.)*)"')


def parse(path):
    """Lector por bloques. Un mismo sujeto puede aparecer en varios bloques
    del Turtle (p. ej. más ontolex:evokes declarados aparte), así que las
    entradas se acumulan por id en vez de leerse de un solo bloque."""
    entries = defaultdict(lambda: {"lemma": None, "label": "", "synsets": []})
    concepts = {}
    text = open(path, encoding="utf-8").read()
    for block in text.split("\n\n"):
        block = block.strip()
        m = SUBJ_RE.match(block)
        if not m:
            continue
        kind, ident = m.group(1), m.group(2)
        if kind == "wordnetLexicalEntry":
            e = entries[ident]
            if (c := CANON_RE.search(block)):
                e["lemma"] = ("lila:" if c.group(1) == "lilaLemma" else "lilah:") + c.group(2)
            if (lb := LABEL_RE.search(block)):
                e["label"] = lb.group(1)
            for ev in re.findall(r"ontolex:evokes\s+(.*?)(?:;\s*\n|\s\.\s*$)", block, re.S):
                for x in SYN_RE.findall(ev):
                    if x not in e["synsets"]:
                        e["synsets"].append(x)
        elif "a ontolex:LexicalConcept" in block.split("\n", 1)[0]:
            d = DEF_RE.search(block)
            concepts[ident] = d.group(1).replace('\\"', '"') if d else ""
    return list(entries.values()), concepts


def main():
    ap = argparse.ArgumentParser(description="Índice local del Latin WordNet por lemmaRef.")
    ap.add_argument("ttl", help="cache/lwn31.ttl")
    ap.add_argument("out", help="cache/lwn_index.json")
    args = ap.parse_args()

    entries, concepts = parse(args.ttl)
    if len(entries) < 10_000 or len(concepts) < 10_000:
        sys.exit(f"Error: solo {len(entries)} entradas y {len(concepts)} synsets; ¿cambió el formato?")

    lemmas = defaultdict(list)
    latin = defaultdict(set)
    for e in entries:
        if not e["lemma"]:
            continue
        for s in e["synsets"]:
            if s not in lemmas[e["lemma"]]:
                lemmas[e["lemma"]].append(s)
            if e["label"]:
                latin[s].add(e["label"])

    synsets = {s: {"def": d, "latin": sorted(latin.get(s, []))} for s, d in concepts.items()}
    data = {
        "meta": {
            "source": "https://github.com/CIRCSE/latinWordnet-revision (lwn31.ttl)",
            "concept_base": CONCEPT_BASE,
            "sha256_16": hashlib.sha256(open(args.ttl, "rb").read()).hexdigest()[:16],
            "built": date.today().isoformat(),
            "lemmas": len(lemmas),
            "synsets": len(synsets),
        },
        "lemmas": lemmas,
        "synsets": synsets,
    }
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, separators=(",", ":"))
    print(f"OK: {len(lemmas)} lemas con sentido, {len(synsets)} synsets → {args.out}")


if __name__ == "__main__":
    main()
