#!/usr/bin/env python3
"""
onate_sense_candidates.py — Un archivo por oración (página · columna ·
oración) con los sentidos posibles del Latin WordNet (LiLa) para las
palabras relevantes, a partir de su @lemmaRef.

Uso:
    python3 scripts/onate_sense_candidates.py src/disp63/pg_63_34_der.xml
    python3 scripts/onate_sense_candidates.py src/disp63/pg_63_*_*.xml

Salida (Markdown, legible y fácil de pasar a la conversación):
    candidatos/disp63/pg_63_34_der/s01.md
    candidatos/disp63/pg_63_34_der/s02.md
    ...

Cada archivo contiene: el texto latino, la traducción si ya existe, y para
cada sustantivo, verbo, adjetivo o adverbio (una vez por lema) sus synsets
con definición y otros lemas latinos del synset. Las palabras ya ancladas
en senses/ aparecen marcadas con su synset. Se regenera por completo cada
vez: es material de trabajo, derivado del TEI, de senses/ y del índice.
"""

import argparse
import importlib.util
import json
import os
import re
import shutil
from collections import OrderedDict

from lxml import etree

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("onate_bilingual_html", os.path.join(_HERE, "onate_bilingual_html.py"))
_bh = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_bh)
NS = _bh.NS
TEI_W = "{http://www.tei-c.org/ns/1.0}w"

CONTENT_POS = {"NOUN", "VERB", "ADJ", "ADV"}
SYN_RE = re.compile(r"(\d{8}-[nvars])/?$")


def load_json(path, default):
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    return default


def plain_text(tokens):
    out = ""
    for i, t in enumerate(tokens):
        out += t["text"] if t["punct"] else (" " if i else "") + t["text"]
    return out


def sentence_md(stem, n, total, s_el, translation, anchored, idx):
    tokens = _bh.tokenize_sentence(s_el, {})
    refs = {}
    for w in s_el.iter(TEI_W):
        if w.get("lemma") and w.get("lemmaRef"):
            refs.setdefault((w.get("lemma"), w.get("pos")), w.get("lemmaRef"))

    # agrupar por lema (una sección por lemmaRef), conservando el orden del texto
    groups = OrderedDict()
    no_ref, no_senses = [], []
    seen = {}
    for t in tokens:
        if t["punct"] or not t.get("meta"):
            continue
        occ = seen[t["text"]] = seen.get(t["text"], 0) + 1
        m = t["meta"]
        if (m.get("pos") or "") not in CONTENT_POS:
            continue
        ref = refs.get((m.get("lemma"), m.get("pos")))
        form = t["text"] + (f" ({occ}.ª)" if occ > 1 else "")
        mark = anchored.get((t["text"], occ))
        if not ref:
            no_ref.append((form, m.get("lemma"), m.get("pos")))
            continue
        if not idx["lemmas"].get(ref):
            no_senses.append((form, m.get("lemma"), ref, mark))
            continue
        g = groups.setdefault(ref, {"lemma": m.get("lemma"), "forms": []})
        g["forms"].append((form, mark))

    L = [f"# {stem} · oración {n} de {total}", "", f"> {plain_text(tokens)}", ""]
    L += [f"**Traducción:** {translation}" if translation else "*Sin traducción guardada.*", ""]

    done = sum(1 for g in groups.values() for _, mk in g["forms"] if mk)
    todo = sum(1 for g in groups.values() for _, mk in g["forms"] if not mk)
    L += [f"Palabras con sentidos posibles: {done + todo} · ancladas: {done} · pendientes: {todo}", ""]

    for ref, g in groups.items():
        syns = idx["lemmas"][ref]
        forms = ", ".join(f"{f} ✓ {mk}" if mk else f for f, mk in g["forms"])
        L += [f"## {g['lemma']} · `{ref}` · {len(syns)} sentido(s)", f"Formas: {forms}", ""]
        chosen = {mk for _, mk in g["forms"] if mk}
        for syn in syns:
            info = idx["synsets"].get(syn, {})
            lat = ", ".join(x for x in info.get("latin", []) if x != g["lemma"])
            mark = "**✓** " if syn in chosen else ""
            L.append(f"- {mark}`{syn}` {info.get('def', '')}" + (f" *[{lat}]*" if lat else ""))
        L.append("")

    if no_senses:
        L += ["## Sin sentidos en el Latin WordNet", ""]
        L += [f"- {f} · {lem} `{ref}`" + (f" ✓ {mk}" if mk else "") for f, lem, ref, mk in no_senses]
        L.append("")
    if no_ref:
        L += ["## Sin lemmaRef (revisar el lema en nlp_corrections/ o lila/excepciones.tsv)", ""]
        L += [f"- {f} · {lem} ({pos})" for f, lem, pos in no_ref]
        L.append("")
    return "\n".join(L), done, todo


def main():
    ap = argparse.ArgumentParser(description="Sentidos posibles (LiLa) por oración.")
    ap.add_argument("src", nargs="+")
    ap.add_argument("--index", default="cache/lwn_index.json")
    ap.add_argument("--senses-dir", default="senses/disp63")
    ap.add_argument("--trans-dir", default="translations/disp63")
    ap.add_argument("--out-dir", default="candidatos/disp63")
    a = ap.parse_args()

    if not os.path.exists(a.index):
        raise SystemExit(f"No existe {a.index}. Genéralo con scripts/onate_lwn_index.py")
    idx = load_json(a.index, {})

    for src in a.src:
        stem = os.path.splitext(os.path.basename(src))[0]
        sentences = etree.parse(src).getroot().findall(".//tei:s", NS)
        trans = {s["n"]: s["es"] for s in load_json(os.path.join(a.trans_dir, f"{stem}.json"), {}).get("sentences", [])}
        anchored = {}
        for e in load_json(os.path.join(a.senses_dir, f"{stem}.json"), {}).get("senses", []):
            m = SYN_RE.search(e.get("synset") or e.get("lila_uri") or "")
            anchored.setdefault(e["sentence"], {})[(e["text"], e.get("occurrence", 1))] = m.group(1) if m else "?"

        folder = os.path.join(a.out_dir, stem)
        shutil.rmtree(folder, ignore_errors=True)      # regenerar limpio
        os.makedirs(folder)
        tot_done = tot_todo = 0
        width = max(2, len(str(len(sentences))))
        for n, s_el in enumerate(sentences, 1):
            md, done, todo = sentence_md(stem, n, len(sentences), s_el, trans.get(n),
                                         anchored.get(n, {}), idx)
            with open(os.path.join(folder, f"s{n:0{width}d}.md"), "w", encoding="utf-8") as fh:
                fh.write(md + "\n")
            tot_done += done
            tot_todo += todo
        print(f"{stem}: {len(sentences)} oraciones → {folder}/  "
              f"(palabras ancladas {tot_done}, pendientes {tot_todo})")


if __name__ == "__main__":
    main()
