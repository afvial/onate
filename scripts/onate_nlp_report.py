#!/usr/bin/env python3
"""
onate_nlp_report.py — Genera un reporte legible por oración del análisis
morfológico actual (lemma/pos/msd) de cada palabra en un TEI ya anotado
(src/*.xml), para revisión manual.

No modifica nada. Solo lee y muestra. Pensado para pegar el resultado en
una conversación y revisar caso por caso qué palabras están mal anotadas
por LatinCy, antes de agregarlas a nlp_corrections/disp63/pg_63_XX_YY.json.

Uso:
  python3 onate_nlp_report.py src/disp63/pg_63_41_izq.xml
  python3 onate_nlp_report.py src/disp63/pg_63_41_izq.xml --min-sent 1 --max-sent 5
"""
import sys
import argparse
from pathlib import Path
from lxml import etree

TEI_NS = "http://www.tei-c.org/ns/1.0"
TEI    = f"{{{TEI_NS}}}"


def get_norm_text(w_elem) -> str:
    parts = []
    for node in w_elem.iter():
        if node.text:
            parts.append(node.text)
        if node.tail and node is not w_elem:
            parts.append(node.tail)
    text = "".join(parts).strip()
    if text.endswith("-"):
        text = text[:-1]
    return text


def local(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def token_info(elem):
    """
    Dado un hijo directo de <s> (<w>, <choice>, <pc>, <lb>...), devuelve
    (display_text, lemma, pos, msd) o None si no aporta texto visible.
    Para <choice>, usa la forma legible (reg/expan) para mostrar, y el
    lemma/pos/msd de cualquiera de sus <w> internos que lo tenga (deberían
    coincidir, ya que se copian entre sí).
    """
    tag = local(elem.tag)
    if tag == "w":
        text = get_norm_text(elem)
        return (text, elem.get("lemma", ""), elem.get("pos", ""), elem.get("msd", ""))
    if tag == "pc":
        return ((elem.text or "").strip(), None, None, None)
    if tag == "choice":
        # Texto legible: preferir reg/expan; si no existe, orig/abbr
        display = None
        lemma = pos = msd = ""
        for pref_tag in ("reg", "expan"):
            sub = elem.find(f"{TEI}{pref_tag}")
            if sub is not None:
                w = sub.find(f".//{TEI}w")
                if w is not None:
                    display = get_norm_text(w)
                    break
        if display is None:
            for pref_tag in ("orig", "abbr"):
                sub = elem.find(f"{TEI}{pref_tag}")
                if sub is not None:
                    w = sub.find(f".//{TEI}w")
                    if w is not None:
                        display = get_norm_text(w)
                        break
        # lemma/pos/msd: cualquier <w> descendiente que tenga lemma no vacío
        for w in elem.iter(f"{TEI}w"):
            if w.get("lemma"):
                lemma = w.get("lemma", "")
                pos   = w.get("pos", "")
                msd   = w.get("msd", "")
                break
        return (display or "", lemma, pos, msd)
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("xml_path", help="Archivo TEI a reportar")
    parser.add_argument("--min-sent", type=int, default=1,
        help="Primera oración a mostrar (1-indexed)")
    parser.add_argument("--max-sent", type=int, default=None,
        help="Última oración a mostrar (1-indexed, inclusive)")
    args = parser.parse_args()

    tree = etree.parse(args.xml_path)
    root = tree.getroot()

    sentences = list(root.iter(f"{TEI}s"))
    total = len(sentences)
    lo = max(1, args.min_sent)
    hi = min(total, args.max_sent) if args.max_sent else total

    print(f"# {args.xml_path} — {total} oración(es) total, mostrando {lo}-{hi}\n")

    for i, s in enumerate(sentences[lo-1:hi], start=lo):
        tokens = []
        for child in s.iter():
            if child is s:
                continue
            if child.getparent() is not s:
                continue  # solo hijos directos de <s> (evita duplicar dentro de choice)
            info = token_info(child)
            if info:
                tokens.append(info)

        sent_text = " ".join(t[0] for t in tokens if t[0]).replace(" ,", ",").replace(" .", ".")
        print(f"── Oración {i} ──")
        print(sent_text)
        print()
        for text, lemma, pos, msd in tokens:
            if lemma is None:  # <pc>, no es palabra
                continue
            if not text:
                continue
            print(f"  {text:20s} lemma={lemma or '—':20s} pos={pos or '—':8s} msd={msd or ''}")
        print()


if __name__ == "__main__":
    main()
