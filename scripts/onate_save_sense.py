#!/usr/bin/env python3
"""
onate_save_sense.py — Ancla el sentido de una palabra (en una oración
concreta) a un synset del Latin WordNet de LiLa, en senses/disp63/<stem>.json.

Rellena automáticamente, a partir del TEI y de cache/lwn_index.json:
  lemma, lemmaRef, lila_uri (forma canónica http://…), lila_def
y comprueba que el synset elegido pertenece de verdad a ese lema.

Subcomandos:

  anclar   <senses_json> <src_xml> <n> <forma> <synset> --match TEXTO
           [--match-occ N] [--occ N] [--gloss EN] [--nota TXT] [--force]

      <forma>  la palabra tal como sale en `siguiente` (también vale sin
               ſ/æ/acentos: 'aestimatio' encuentra 'æſtimatio')
      <synset> id del synset, p. ej. 05171334-n (el que lista `siguiente`)
      --match  palabra o frase de la TRADUCCIÓN que se resalta
      --occ    si la forma latina aparece varias veces en la oración (def. 1)
      --force  anclar aunque el synset no esté entre los del lema

  validar  <senses_json> <src_xml>
      Revisa todas las entradas: añade lemmaRef si falta, normaliza la URI
      (http, sin barra final) y avisa si un synset no pertenece al lema.

Uso habitual, a través de traducir_pagina.sh:
    ./traducir_pagina.sh 34 der sentido 1 pretium 05171334-n --match precio --match-occ 2
"""

import argparse
import importlib.util
import json
import os
import re
import sys
import unicodedata

from lxml import etree

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("onate_bilingual_html", os.path.join(_HERE, "onate_bilingual_html.py"))
_bh = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_bh)
NS = _bh.NS
TEI = "{http://www.tei-c.org/ns/1.0}"

CONCEPT_BASE = "http://lila-erc.eu/data/lexicalResources/LatinWordNet/id/LexicalConcept/"
SYNSET_RE = re.compile(r"(\d{8}-[nvars])/?$")

README = (
    "Ancla el sentido de una palabra latina puntual (en su ocurrencia dentro de una "
    "oración concreta) al Latin WordNet de LiLa. 'occurrence' desambigua cuándo la misma "
    "forma latina aparece más de una vez en la oración. 'match_text' es la palabra/frase "
    "a resaltar en la TRADUCCIÓN y 'match_occurrence' desambigua si aparece varias veces. "
    "'lemmaRef' es el lema de LiLa (como en el TEI); 'synset' el id del LexicalConcept; "
    "'lila_uri' y 'lila_def' se rellenan desde cache/lwn_index.json con "
    "scripts/onate_save_sense.py. 'note' es el comentario editorial."
)


def fold(s: str) -> str:
    """Comparación tolerante: ſ→s, æ→ae, œ→oe, sin diacríticos, minúsculas, u/v, i/j."""
    s = s.replace("ſ", "s").replace("æ", "ae").replace("Æ", "Ae").replace("œ", "oe").replace("Œ", "Oe")
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.lower().replace("v", "u").replace("j", "i")


def synset_of(uri_or_id: str):
    m = SYNSET_RE.search((uri_or_id or "").strip())
    return m.group(1) if m else None


def canonical_uri(synset: str) -> str:
    return CONCEPT_BASE + synset


def load_index(path):
    if not os.path.exists(path):
        sys.exit(f"No existe {path}. Genéralo con scripts/onate_lwn_index.py")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def sentence_tokens(src_xml, n):
    root = etree.parse(src_xml).getroot()
    sentences = root.findall(".//tei:s", NS)
    if not 1 <= n <= len(sentences):
        sys.exit(f"Oración {n} fuera de rango (la columna tiene {len(sentences)}).")
    s_el = sentences[n - 1]
    tokens = [t for t in _bh.tokenize_sentence(s_el, {}) if not t["punct"]]
    # (lema, pos) → lemmaRef, leído de los <w> de la propia oración
    refs = {}
    for w in s_el.iter(TEI + "w"):
        if w.get("lemma") and w.get("lemmaRef"):
            refs.setdefault((w.get("lemma"), w.get("pos")), w.get("lemmaRef"))
    return tokens, refs


def lemma_ref_for(token, refs):
    m = token.get("meta") or {}
    return m.get("lemma"), refs.get((m.get("lemma"), m.get("pos")))


def load_senses(path, src_xml):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    else:
        stem = os.path.splitext(os.path.basename(src_xml))[0]
        data = {"page": stem.replace("pg_63_", ""), "source_xml": os.path.basename(src_xml), "senses": []}
    data["_readme"] = README
    data.setdefault("senses", [])
    return data


def save_senses(path, data):
    order = ["_readme", "page", "source_xml", "senses"]
    out = {k: data[k] for k in order if k in data}
    out.update({k: v for k, v in data.items() if k not in out})
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


# ── anclar ────────────────────────────────────────────────────────────────────
def cmd_anclar(a):
    idx = load_index(a.index)
    synset = synset_of(a.synset)
    if not synset:
        sys.exit(f"'{a.synset}' no parece un synset (formato 05171334-n).")
    if synset not in idx["synsets"]:
        sys.exit(f"El synset {synset} no existe en el Latin WordNet.")

    tokens, refs = sentence_tokens(a.src_xml, a.n)
    hits = [t for t in tokens if t["text"] == a.forma] or \
           [t for t in tokens if fold(t["text"]) == fold(a.forma)]
    if len(hits) < a.occ:
        forms = ", ".join(sorted({t["text"] for t in tokens}))
        sys.exit(f"'{a.forma}' (aparición {a.occ}) no está en la oración {a.n}.\nFormas: {forms}")
    tok = hits[a.occ - 1]
    lemma, lemma_ref = lemma_ref_for(tok, refs)

    candidates = idx["lemmas"].get(lemma_ref, []) if lemma_ref else []
    if synset not in candidates and not a.force:
        msg = (f"El synset {synset} no está entre los sentidos de '{lemma}' ({lemma_ref or 'sin lemmaRef'})."
               if candidates else f"'{lemma}' ({lemma_ref or 'sin lemmaRef'}) no tiene sentidos en el Latin WordNet.")
        sys.exit(msg + "\nComprueba el id en la lista de `siguiente`, o usa --force si es intencionado.")

    entry = {
        "sentence": a.n,
        "text": tok["text"],
        "occurrence": a.occ,
        "lemma": lemma,
        "lemmaRef": lemma_ref,
        "synset": synset,
        "match_text": a.match,
        "match_occurrence": a.match_occ,
        "lila_uri": canonical_uri(synset),
        "lila_def": idx["synsets"][synset]["def"],
    }
    if a.gloss:
        entry["gloss_en"] = a.gloss
    if a.nota:
        entry["note"] = a.nota

    data = load_senses(a.senses_json, a.src_xml)
    key = (entry["sentence"], entry["text"], entry["occurrence"])
    old = next((e for e in data["senses"] if (e["sentence"], e["text"], e.get("occurrence", 1)) == key), None)
    if old:
        # conservar campos editoriales que no se pasaron ahora
        for k in ("gloss_en", "note"):
            if k in old and k not in entry:
                entry[k] = old[k]
        data["senses"][data["senses"].index(old)] = entry
        verb = "Actualizado"
    else:
        data["senses"].append(entry)
        verb = "Anclado"
    data["senses"].sort(key=lambda e: (e["sentence"], e.get("occurrence", 1)))
    save_senses(a.senses_json, data)
    print(f"{verb}: §{a.n} {tok['text']} ({lemma}, {lemma_ref}) → {synset}")
    print(f"  {entry['lila_def']}")
    if synset not in candidates:
        print("  ⚠ anclado con --force: el synset no pertenece al lema en el Latin WordNet")


# ── validar ───────────────────────────────────────────────────────────────────
def cmd_validar(a):
    idx = load_index(a.index)
    data = load_senses(a.senses_json, a.src_xml)
    cache, changed, problems = {}, 0, 0
    for e in data["senses"]:
        n = e["sentence"]
        if n not in cache:
            cache[n] = sentence_tokens(a.src_xml, n)
        tokens, refs = cache[n]
        hits = [t for t in tokens if t["text"] == e["text"]]
        occ = e.get("occurrence", 1)
        label = f"§{n} {e['text']}"
        if len(hits) < occ:
            print(f"✗ {label}: la forma ya no está en la oración (¿cambió la segmentación?)")
            problems += 1
            continue
        lemma, lemma_ref = lemma_ref_for(hits[occ - 1], refs)
        syn = e.get("synset") or synset_of(e.get("lila_uri"))
        if lemma_ref and e.get("lemmaRef") != lemma_ref:
            e["lemmaRef"] = lemma_ref
            changed += 1
        if syn:
            if e.get("synset") != syn:
                e["synset"] = syn
                changed += 1
            if e.get("lila_uri") != canonical_uri(syn):
                e["lila_uri"] = canonical_uri(syn)
                changed += 1
            if not e.get("lila_def") and syn in idx["synsets"]:
                e["lila_def"] = idx["synsets"][syn]["def"]
                changed += 1
            ok = syn in idx["lemmas"].get(lemma_ref, [])
            print(f"{'✓' if ok else '⚠'} {label} ({lemma}, {lemma_ref}) → {syn}"
                  + ("" if ok else "  — el synset NO pertenece a este lema"))
            problems += 0 if ok else 1
        else:
            print(f"· {label} ({lemma}, {lemma_ref}): sin synset (pendiente)")
    save_senses(a.senses_json, data)
    print(f"\n{len(data['senses'])} entradas; {changed} campos actualizados; {problems} aviso(s).")


def main():
    ap = argparse.ArgumentParser(description="Anclar/validar sentidos (Latin WordNet).")
    ap.add_argument("--index", default="cache/lwn_index.json")
    sub = ap.add_subparsers(dest="cmd", required=True)

    an = sub.add_parser("anclar")
    an.add_argument("senses_json")
    an.add_argument("src_xml")
    an.add_argument("n", type=int)
    an.add_argument("forma")
    an.add_argument("synset")
    an.add_argument("--match", required=True, help="texto a resaltar en la traducción")
    an.add_argument("--match-occ", type=int, default=1)
    an.add_argument("--occ", type=int, default=1)
    an.add_argument("--gloss", help="glosa inglesa opcional (título en la concordancia)")
    an.add_argument("--nota", help="comentario editorial")
    an.add_argument("--force", action="store_true")

    va = sub.add_parser("validar")
    va.add_argument("senses_json")
    va.add_argument("src_xml")

    a = ap.parse_args()
    {"anclar": cmd_anclar, "validar": cmd_validar}[a.cmd](a)


if __name__ == "__main__":
    main()
