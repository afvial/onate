#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
onate_search_index.py
─────────────────────
Genera el índice de búsqueda (JSON compacto) a partir del TEI ensamblado.

Uso:
    python3 scripts/onate_search_index.py output/disp63_bibl_completo.xml
    python3 scripts/onate_search_index.py output/disp63_bibl_completo.xml \
            --out html/disp63/search_index.json

Por defecto escribe html/disp63/search_index.js (window.ONATE_INDEX = …),
que concordancia.html carga con <script>: así funciona también abriendo el
HTML directamente desde el disco (file://), donde fetch() está bloqueado.
Con --out *.json escribe JSON puro (para cargarlo a mano o reutilizarlo).

Un token por palabra o signo de puntuación, con:
    f   forma regularizada (reg / expan / corr; ſ→s)
    d   forma diplomática (orig / abbr / sic; conserva ſ, æ…)
    l   lema          p   POS          m   rasgos morfológicos (msd)
    pg  página        c   columna (izq / der / unica)
    ln  número de línea (<lb n>) donde empieza la palabra

Las palabras partidas entre columnas (@wpair) cuentan una sola vez, en la
columna donde empiezan.
"""
import sys
import json
import argparse
import datetime
from pathlib import Path
from lxml import etree

NS = "http://www.tei-c.org/ns/1.0"
T = lambda local: f"{{{NS}}}{local}"

NORM_BRANCH = {T("reg"), T("expan"), T("corr")}
DIPL_BRANCH = {T("orig"), T("abbr"), T("sic")}


def side_text(el, keep):
    """Texto de el eligiendo, en cada <choice>, la rama de `keep`
    (ignora <lb/>, cuyo tail sí se conserva)."""
    if el.tag == T("choice"):
        kids = [b for b in el if isinstance(b.tag, str)]
        branch = next((b for b in kids if b.tag in keep), kids[0] if kids else None)
        return side_text(branch, keep) if branch is not None else ""
    out = [el.text or ""]
    for ch in el:
        if isinstance(ch.tag, str):
            out.append(side_text(ch, keep))
        out.append(ch.tail or "")
    return "".join(out)


def in_branch(el, tags):
    p = el.getparent()
    while p is not None:
        if p.tag in tags:
            return True
        p = p.getparent()
    return False


def token_root(w):
    """El elemento que representa la palabra entera: el <choice> más externo
    que contiene a w (si lo hay), o el propio w."""
    root, p = w, w.getparent()
    while p is not None and p.tag in (T("choice"), T("reg"), T("expan"),
                                       T("corr"), T("orig"), T("abbr"), T("sic")):
        if p.tag == T("choice"):
            root = p
        p = p.getparent()
    return root


def col_names(divs):
    seen, names = {}, []
    for d in divs:
        n = d.get("n", "?")
        k = seen.get(n, 0)
        seen[n] = k + 1
        names.append(k)
    counts = {n: c for n, c in seen.items()}
    out = []
    for d, k in zip(divs, names):
        n = d.get("n", "?")
        out.append("unica" if counts[n] == 1 else ("izq", "der", "c3", "c4")[k])
    return out


def build(xml_path):
    tree = etree.parse(str(xml_path))
    divs = tree.getroot().findall(f".//{T('div')}[@type='page']")
    tokens, seen_pairs = [], {}

    for div, col in zip(divs, col_names(divs)):
        page = div.get("n", "")
        line = ""
        done = set()
        for el in div.iter(T("lb"), T("w"), T("pc")):
            if el.tag == T("lb"):
                # lb dentro de una palabra no cambia la línea de inicio
                if not in_branch(el, {T("w")}) and el.get("n"):
                    line = el.get("n")
                continue
            if in_branch(el, DIPL_BRANCH):
                continue                      # duplicado diplomático
            root = token_root(el)
            if root in done:
                continue
            done.add(root)
            wp = root.get("wpair") if root.tag == T("choice") else None
            if wp and wp in seen_pairs:
                # segunda mitad de una palabra partida entre columnas: se
                # completa la forma diplomática de la primera y no se cuenta
                tokens[seen_pairs[wp]][1] += "".join(side_text(root, DIPL_BRANCH).split())
                continue
            if el.tag == T("pc"):
                txt = (el.text or "").strip()
                if txt:
                    tokens.append([txt, txt, "", "PUNCT", "", page, col, line])
                continue
            norm = side_text(root, NORM_BRANCH).strip().replace("ſ", "s")
            dipl = side_text(root, DIPL_BRANCH).strip()
            norm, dipl = "".join(norm.split()), "".join(dipl.split())
            if not norm:
                continue
            if wp:
                seen_pairs[wp] = len(tokens)
            tokens.append([norm, dipl, el.get("lemma", ""), el.get("pos", ""),
                           el.get("msd", ""), page, col, line])

    return {"fields": ["f", "d", "l", "p", "m", "pg", "c", "ln"],
            "source": Path(xml_path).name,
            "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "tokens": tokens}


def main():
    ap = argparse.ArgumentParser(description="TEI ensamblado → índice de búsqueda JSON")
    ap.add_argument("input")
    ap.add_argument("--out", "-o", default="html/disp63/search_index.js")
    a = ap.parse_args()
    idx = build(a.input)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(idx, ensure_ascii=False, separators=(",", ":"))
    if out.suffix == ".js":
        data = "window.ONATE_INDEX = " + data + ";\n"
    out.write_text(data, encoding="utf-8")
    words = sum(1 for t in idx["tokens"] if t[3] != "PUNCT")
    print(f"✓ {words} palabras, {len(idx['tokens'])} tokens → {out} "
          f"({out.stat().st_size // 1024} KB)", file=sys.stderr)


if __name__ == "__main__":
    main()
