#!/usr/bin/env python3
"""
onate_next_sentence.py — Imprime la primera oración sin traducir de una
columna (texto diplomático + tabla lemma/pos/msd por palabra), lista para
pegar en la conversación de traducción.

Uso:
    python3 onate_next_sentence.py <src_xml> <translations_json> [--n N]

Sin --n, busca la primera oración cuyo número no esté ya en translations_json.
Con --n, muestra esa oración puntual (para revisar/retraducir).

Si existe cache/lwn_index.json (scripts/onate_lwn_index.py), añade al final
los sentidos candidatos del Latin WordNet para cada palabra con contenido,
a partir de su @lemmaRef, marcando los ya anclados en senses/.
"""
import argparse
import re
import json
import os
from lxml import etree

# Reutiliza las mismas funciones de extracción que onate_bilingual_html.py
import importlib.util

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("onate_bilingual_html", os.path.join(_HERE, "onate_bilingual_html.py"))
_bh = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_bh)

NS = _bh.NS


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src_xml")
    ap.add_argument("translations_json")
    ap.add_argument("--n", type=int, default=None, help="Mostrar la oración N en vez de la primera pendiente")
    ap.add_argument("--senses-json", default=None, help="senses/disp63/<stem>.json (para marcar lo ya anclado)")
    ap.add_argument("--index", default="cache/lwn_index.json", help="índice del Latin WordNet")
    ap.add_argument("--sin-sentidos", action="store_true", help="no listar los sentidos candidatos")
    args = ap.parse_args()

    tree = etree.parse(args.src_xml)
    root = tree.getroot()
    sentences = root.findall(".//tei:s", NS)

    translations = {}
    if os.path.exists(args.translations_json):
        with open(args.translations_json, encoding="utf-8") as f:
            translations = {s["n"]: s["es"] for s in json.load(f).get("sentences", [])}

    if args.n is not None:
        target = args.n
    else:
        target = None
        for idx in range(1, len(sentences) + 1):
            if idx not in translations:
                target = idx
                break
        if target is None:
            print(f"Todas las oraciones ({len(sentences)}) ya están traducidas en {args.translations_json}.")
            return

    if target < 1 or target > len(sentences):
        print(f"Oración {target} fuera de rango (la columna tiene {len(sentences)} oraciones).")
        return

    s_el = sentences[target - 1]
    tokens = _bh.tokenize_sentence(s_el, {})
    latin_text = " ".join(t["text"] for t in tokens if not t["punct"] or True)
    # reconstrucción simple sin cuidar espacios de puntuación (solo para lectura humana)
    plain = ""
    for i, t in enumerate(tokens):
        if t["punct"]:
            plain += t["text"]
        else:
            plain += (" " if i else "") + t["text"]

    print(f"=== Oración {target} de {len(sentences)} ({os.path.basename(args.src_xml)}) ===\n")
    print(plain)
    print()
    print(f"{'palabra':<16} {'lemma':<16} {'pos':<8} msd")
    print("-" * 70)
    for t in tokens:
        if t["punct"] or not t.get("meta"):
            continue
        m = t["meta"]
        print(f"{t['text']:<16} {(m.get('lemma') or ''):<16} {(m.get('pos') or ''):<8} {m.get('msd') or ''}")

    if target in translations:
        print(f"\n[ya tiene traducción guardada]\n{translations[target]}")

    if not args.sin_sentidos:
        print_senses(s_el, tokens, target, args)


CONTENT_POS = {"NOUN", "VERB", "ADJ", "ADV"}
TEI_W = "{http://www.tei-c.org/ns/1.0}w"


def print_senses(s_el, tokens, target, args):
    """Sentidos candidatos del Latin WordNet por palabra con contenido."""
    if not os.path.exists(args.index):
        print(f"\n(sin {args.index}: genera el índice con scripts/onate_lwn_index.py para ver sentidos)")
        return
    with open(args.index, encoding="utf-8") as f:
        idx = json.load(f)
    anchored = {}
    if args.senses_json and os.path.exists(args.senses_json):
        with open(args.senses_json, encoding="utf-8") as f:
            for e in json.load(f).get("senses", []):
                if e["sentence"] == target:
                    m = re.search(r"(\d{8}-[nvars])/?$", e.get("synset") or e.get("lila_uri") or "")
                    anchored[(e["text"], e.get("occurrence", 1))] = m.group(1) if m else "?"
    refs = {}
    for w in s_el.iter(TEI_W):
        if w.get("lemma") and w.get("lemmaRef"):
            refs.setdefault((w.get("lemma"), w.get("pos")), w.get("lemmaRef"))

    print("\n── Sentidos (Latin WordNet) " + "─" * 42)
    seen_forms, shown = {}, set()
    for t in tokens:
        if t["punct"] or not t.get("meta"):
            continue
        m = t["meta"]
        occ = seen_forms[t["text"]] = seen_forms.get(t["text"], 0) + 1
        if (m.get("pos") or "") not in CONTENT_POS:
            continue
        ref = refs.get((m.get("lemma"), m.get("pos")))
        syns = idx["lemmas"].get(ref, []) if ref else []
        mark = anchored.get((t["text"], occ))
        head = f"{t['text']}" + (f" ({occ}.ª)" if occ > 1 else "") + f"  ·  {m.get('lemma')} {ref or '(sin lemmaRef)'}"
        if mark:
            print(f"\n✓ {head}  → anclado: {mark}")
            continue
        if not syns:
            print(f"\n· {head}  — sin sentidos en el Latin WordNet")
            continue
        if ref in shown:
            print(f"\n  {head}  — (mismos sentidos que arriba)")
            continue
        shown.add(ref)
        print(f"\n  {head}  — {len(syns)} sentido(s)")
        for syn in syns:
            info = idx["synsets"].get(syn, {})
            lat = ", ".join(x for x in info.get("latin", []) if x != m.get("lemma"))[:40]
            d = info.get("def", "")
            d = d if len(d) <= 78 else d[:77] + "…"
            print(f"    {syn}  {d}" + (f"  [{lat}]" if lat else ""))


if __name__ == "__main__":
    main()
