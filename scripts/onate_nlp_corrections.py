#!/usr/bin/env python3
"""
onate_nlp_corrections.py — Aplica correcciones manuales de lemma/pos/msd
sobre un TEI ya anotado (src/*.xml), leyendo un archivo JSON de
correcciones por palabra, con alcance limitado a esa página/columna.

Notación del JSON: {"palabra": "Feature=Val,Feature2=Val2,..."}
  - Claves reservadas "lemma"/"pos" sobreescriben esos campos directamente.
  - El resto se trata como rasgo morfológico y se fusiona en @msd -- salvo
    que "pos" también se haya corregido, en cuyo caso el @msd calculado
    por spaCy para el POS incorrecto se descarta por completo (sus rasgos
    no tienen sentido para el nuevo POS).
  - Todas las palabras corregidas quedan marcadas con @manual="1".

No modifica lemma/pos/msd de palabras que no están en el JSON.
Alcance: por palabra dentro de ESTE archivo (página/columna), no todo el
corpus (ver MANUAL_LEMMA en onate_nlp.py para overrides globales).

Uso:
  python3 onate_nlp_corrections.py src/disp63/pg_63_41_izq.xml \
      nlp_corrections/disp63/pg_63_41_izq.json
"""
import sys
import json
import argparse
from pathlib import Path
from lxml import etree

TEI_NS = "http://www.tei-c.org/ns/1.0"
TEI    = f"{{{TEI_NS}}}"


def local(tag: str) -> str:
    """Devuelve el nombre local del tag sin namespace."""
    return tag.split("}")[-1] if "}" in tag else tag

def get_norm_text(w_elem) -> str:
    """Extrae el texto normalizado de un <w>, igual que onate_nlp.py."""
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


def apply_correction(w_elem, correction: str) -> None:
    """Aplica una corrección puntual a un <w>, con la misma lógica de
    fusión de lemma/pos/msd usada en onate_nlp.py."""
    override_pairs = dict(
        pair.split("=", 1) for pair in correction.split(",") if "=" in pair
    )
    lemma = w_elem.get("lemma", "")
    pos   = w_elem.get("pos", "")
    msd   = w_elem.get("msd", "")

    pos_changed = "pos" in override_pairs
    override_feats = {}
    for k, v in override_pairs.items():
        if k == "lemma":
            lemma = v
        elif k == "pos":
            pos = v
        elif k == "text":
            # Sobreescribe el texto visible del <w> (normalmente dentro de
            # <expan>/<reg>). Uso: cuando la expansion generada por el
            # diccionario global de abreviaturas es incorrecta para ESTA
            # ocurrencia puntual (ambiguedad dependiente de contexto que
            # no se puede resolver globalmente).
            w_elem.text = v
        else:
            override_feats[k] = v

    if override_feats:
        if pos_changed:
            existing_feats = {}
        else:
            existing_feats = dict(
                pair.split("=", 1) for pair in msd.split("|") if "=" in pair
            ) if msd else {}
        existing_feats.update(override_feats)
        msd = "|".join(f"{k}={v}" for k, v in sorted(existing_feats.items()))
    elif pos_changed:
        msd = ""

    w_elem.set("lemma", lemma)
    w_elem.set("pos", pos)
    if msd:
        w_elem.set("msd", msd)
    else:
        w_elem.attrib.pop("msd", None)
    w_elem.set("manual", "1")


def main():
    parser = argparse.ArgumentParser(description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("xml_path", help="Archivo TEI a corregir (in-place)")
    parser.add_argument("corrections_json",
        help="JSON de correcciones {palabra: 'Feature=Val,...'}")
    args = parser.parse_args()

    xml_path  = Path(args.xml_path)
    json_path = Path(args.corrections_json)

    if not json_path.exists():
        print(f"  (sin correcciones: {json_path} no existe)", file=sys.stderr)
        return

    with open(json_path, encoding="utf-8") as f:
        corrections = json.load(f)
    if not corrections:
        return

    corrections_lower = {k.lower(): v for k, v in corrections.items()}

    xml_parser = etree.XMLParser(remove_blank_text=False)
    tree = etree.parse(str(xml_path), xml_parser)
    root = tree.getroot()

    applied = 0
    processed = set()

    # Primero: <choice> (orig/reg, abbr/expan, y variantes anidadas de
    # s larga). La clave de busqueda es SIEMPRE el texto normalizado
    # (reg/expan), nunca la forma diplomatica (que puede llevar ſ y no
    # coincidir con la clave del JSON). La correccion se aplica a TODOS
    # los <w> dentro del choice (ambas copias), para que orig y reg
    # queden consistentes -- de lo contrario solo se corrige la copia
    # que coincide por texto, dejando la otra (normalmente la visible
    # en el tooltip) con el analisis viejo de spaCy.
    for choice in root.iter(f"{TEI}choice"):
        reg_el = choice.find(f"{TEI}reg")
        if reg_el is None:
            reg_el = choice.find(f"{TEI}expan")
        if reg_el is None:
            continue
        reg_w = reg_el.find(f".//{TEI}w")
        if reg_w is None:
            continue
        key = get_norm_text(reg_w).lower()
        if key not in corrections_lower:
            continue
        correction = corrections_lower[key]
        # "text" solo debe aplicarse a la copia normalizada (reg_w),
        # nunca a la copia diplomatica (orig/abbr), que debe seguir
        # mostrando fielmente lo impreso. Se separa antes de aplicar
        # el resto de la correccion (lemma/pos/msd) uniformemente.
        pairs = dict(p.split("=", 1) for p in correction.split(",") if "=" in p)
        text_override = pairs.pop("text", None)
        rest_correction = ",".join(f"{k}={v}" for k, v in pairs.items())
        for w in choice.iter(f"{TEI}w"):
            if w in processed:
                continue
            if rest_correction:
                apply_correction(w, rest_correction)
            if text_override and w is reg_w:
                w.text = text_override
                w.set("manual", "1")
            processed.add(w)
        applied += 1

    # Luego: <w> planos que no pertenecen a ningun choice ya procesado.
    for w in root.iter(f"{TEI}w"):
        if w in processed:
            continue
        parent = w.getparent()
        if parent is not None and local(parent.tag) in ("orig", "reg", "abbr", "expan"):
            # Pertenece a un choice que ya se evaluo arriba (coincidiera
            # o no); no reprocesar individualmente con su propio texto,
            # que podria ser la forma diplomatica y no calzar con la clave.
            continue
        text = get_norm_text(w)
        key = text.lower()
        if key in corrections_lower:
            apply_correction(w, corrections_lower[key])
            processed.add(w)
            applied += 1

    if applied:
        tree.write(str(xml_path), encoding="UTF-8",
                   xml_declaration=True, pretty_print=True)
        print(f"  ✓ {applied} corrección(es) NLP aplicada(s) desde {json_path}",
              file=sys.stderr)
    else:
        print(f"  (0 coincidencias de {len(corrections)} corrección(es) en {json_path})",
              file=sys.stderr)


if __name__ == "__main__":
    main()
