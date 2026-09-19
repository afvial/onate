#!/usr/bin/env python3
"""
onate_next_sentence.py — Imprime la primera oración sin traducir de una
columna (texto diplomático + tabla lemma/pos/msd por palabra), lista para
pegar en la conversación de traducción.

Uso:
    python3 onate_next_sentence.py <src_xml> <translations_json> [--n N]

Sin --n, busca la primera oración cuyo número no esté ya en translations_json.
Con --n, muestra esa oración puntual (para revisar/retraducir).
"""
import argparse
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
    args = ap.parse_args()

    tree = etree.parse(args.src_xml)
    root = tree.getroot()
    sentences = root.findall(".//tei:s", NS)

    translations = {}
    if os.path.exists(args.translations_json):
        with open(args.translations_json, encoding="utf-8") as f:
            translations = {s["n"]: s["en"] for s in json.load(f).get("sentences", [])}

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


if __name__ == "__main__":
    main()
