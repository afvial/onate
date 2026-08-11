#!/usr/bin/env python3
"""
onate_nlp.py — Anotación morfológica NLP del TEI diplomático (src/)

Anota cada <w> con @lemma, @pos y @msd usando latincy (spaCy).

Excluye <w> que sean descendientes de:
  - bibl   → nombres de autores, títulos, números de referencia
  - corr   → correcciones editoriales
  - supplied → texto suplido por el editor

Incluye <w> dentro de <sic> (forma impresa) y <orig> (grafía original).

Para cada <choice><sic><w>/<corr><w>:
  - Anota usando el texto de <corr><w> (forma correcta para el NLP)
  - Copia los mismos atributos al <corr><w>

Para cada <choice><orig><w>/<reg><w>:
  - Anota el <w> de <reg> (forma normalizada) → el modelo la procesa mejor
  - Copia los mismos atributos al <w> de <orig>

Para cada <choice><abbr><w>/<expan><w>:
  - Anota el <w> de <expan> (forma expandida)
  - No anota el <w> de <abbr> (abreviatura)

Uso:
  python3 onate_nlp.py src/disp63/pg_63_35_der.xml
  python3 onate_nlp.py src/disp63/pg_63_35_der.xml --model la_core_web_lg
  python3 onate_nlp.py src/disp63/pg_63_35_der.xml --dry-run
"""

import argparse
import sys
from pathlib import Path
from lxml import etree

TEI_NS  = "http://www.tei-c.org/ns/1.0"
TEI     = f"{{{TEI_NS}}}"

# Ancestros que excluyen la anotación
EXCLUDE_ANCESTORS = {"bibl", "corr", "supplied"}

# Ancestros que excluyen solo la anotación directa
# (el <w> de <abbr> no se anota; el de <expan> sí)
ABBR_TAG   = f"{TEI}abbr"
EXPAN_TAG  = f"{TEI}expan"
ORIG_TAG   = f"{TEI}orig"
REG_TAG    = f"{TEI}reg"

# Palabras cuya ortografía diplomáticamente correcta (según la regla
# posicional del macrón: medial -> n) LatinCy lematiza mal, porque su
# vocabulario de entrenamiento solo reconoce bien la variante asimilada
# con m (más común en ediciones modernas). Se consulta al modelo con la
# forma de esta lista en vez de la real; el texto guardado en el XML
# (el que ve el lector) no se toca — igual que se hace con ſ->s para la
# consulta al modelo, sin cambiar lo que se muestra.
NLP_QUERY_OVERRIDES = {
    'quocunque': 'quocumque',
    'Quocunque': 'Quocumque',
}


def _nlp_query_text(norm: str) -> str:
    """Texto a enviar al modelo para lematizar: usa la forma que el
    modelo reconoce mejor cuando difiere de la forma diplomática real."""
    return NLP_QUERY_OVERRIDES.get(norm, norm)


def local(tag: str) -> str:
    """Devuelve el nombre local del tag sin namespace."""
    return tag.split("}")[-1] if "}" in tag else tag


def is_excluded(elem) -> bool:
    """True si el <w> tiene un ancestro que excluye la anotación."""
    for anc in elem.iterancestors():
        if local(anc.tag) in EXCLUDE_ANCESTORS:
            return True
    return False


def is_in_abbr(elem) -> bool:
    """True si el <w> está dentro de <abbr> (no se anota)."""
    for anc in elem.iterancestors():
        if anc.tag == ABBR_TAG:
            return True
    return False


def get_norm_text(w_elem) -> str:
    """
    Extrae el texto normalizado de un <w>:
    - Concatena todo el texto del elemento (incluye texto de hijos como <lb>)
    - Elimina el guion de partición al final si hay <lb break='no'>
    """
    parts = []
    for node in w_elem.iter():
        if node.text:
            parts.append(node.text)
        if node.tail and node is not w_elem:
            parts.append(node.tail)
    text = "".join(parts).strip()
    # Quitar guion final de partición
    if text.endswith("-"):
        text = text[:-1]
    return text


def morph_to_msd(token) -> str:
    """Convierte el objeto Morphology de spaCy a string pipe-separated."""
    m = token.morph
    if not m:
        return ""
    return str(m).replace("|", "|")  # ya viene en formato Feature=Val|...


def collect_w_elements(tree):
    """
    Devuelve lista de (w_elem, norm_text, reg_pair_w) donde:
    - w_elem: el elemento <w> a anotar
    - norm_text: texto normalizado para pasar al NLP
    - reg_pair_w: si w_elem es <orig><w>, el <reg><w> correspondiente
                  para copiarle los atributos; None si no aplica
    """
    results = []
    root = tree.getroot()

    for w in root.iter(f"{TEI}w"):
        # Excluir por ancestros bloqueantes
        if is_excluded(w):
            continue

        # Excluir si está en <abbr>
        if is_in_abbr(w):
            continue

        parent = w.getparent()
        if parent is None:
            continue

        parent_tag = local(parent.tag)
        grandparent = parent.getparent()
        grandparent_tag = local(grandparent.tag) if grandparent is not None else ""

        # <choice><abbr><w> / <expan><w>
        if parent_tag == "expan" and grandparent_tag == "choice":
            norm = get_norm_text(w)
            if norm:
                results.append((w, norm, None))
            continue

        # <choice><sic><w> / <corr><w>
        # Usamos el texto de <corr><w> para el NLP (forma correcta);
        if parent_tag == "sic" and grandparent_tag == "choice":
            corr_w = None
            for sibling in grandparent:
                if local(sibling.tag) == "corr":
                    corr_children = list(sibling)
                    if corr_children and local(corr_children[0].tag) == "w":
                        corr_w = corr_children[0]
                    elif corr_children and local(corr_children[0].tag) == "choice":
                        # corr contiene un choice anidado (orig=diplomatico con
                        # s larga / reg=forma plana). Usar reg/w para el NLP y
                        # como destino de copia de atributos.
                        for ch in corr_children[0]:
                            if local(ch.tag) == "reg":
                                reg_children = list(ch)
                                if reg_children and local(reg_children[0].tag) == "w":
                                    corr_w = reg_children[0]
                                break
                    break
            if corr_w is not None:
                norm = get_norm_text(corr_w)
                if norm:
                    # w_elem = sic/w, reg_w = corr/w (destino de copia)
                    results.append((w, norm, corr_w))
            else:
                # No hay corr: anotar con el texto del sic directamente
                norm = get_norm_text(w)
                if norm:
                    results.append((w, norm, None))
            continue

        # <choice><orig><w> / <reg><w>
        if parent_tag == "orig" and grandparent_tag == "choice":
            # Buscar el <reg><w> hermano
            reg_w = None
            for sibling in grandparent:
                if local(sibling.tag) == "reg":
                    reg_children = list(sibling)
                    if reg_children and local(reg_children[0].tag) == "w":
                        reg_w = reg_children[0]
                    break
            if reg_w is not None:
                norm = get_norm_text(reg_w)
                if norm:
                    # Anota el orig/w, con reg_w como destino de copia
                    results.append((w, norm, reg_w))
            else:
                # No hay reg, anotar directamente
                norm = get_norm_text(w)
                if norm:
                    results.append((w, norm, None))
            continue

        if parent_tag == "reg" and grandparent_tag == "choice":
            # Ya fue manejado arriba (vía orig); si hay un orig no lo procesamos de nuevo
            has_orig = any(local(s.tag) == "orig" for s in grandparent)
            if has_orig:
                continue
            # No hay orig → anotar directamente
            norm = get_norm_text(w)
            if norm:
                results.append((w, norm, None))
            continue

        # <w> suelto (sin choice especial)
        norm = get_norm_text(w)
        if norm:
            results.append((w, norm, None))

    return results


def annotate(input_path: Path, output_path: Path, model_name: str, dry_run: bool):
    parser = etree.XMLParser(remove_blank_text=False)
    tree   = etree.parse(str(input_path), parser)

    items = collect_w_elements(tree)
    if not items:
        print("No se encontraron <w> para anotar.", file=sys.stderr)
        return

    print(f"→ {len(items)} tokens a anotar con {model_name}", file=sys.stderr)

    import spacy
    nlp = spacy.load(model_name)

    # Procesar en lotes para eficiencia
    texts  = [_nlp_query_text(norm) for _, norm, _ in items]
    elems  = [(w, reg) for w, _, reg in items]

    docs = list(nlp.pipe(texts, batch_size=256))

    annotated = 0
    for (w_elem, reg_w), doc in zip(elems, docs):
        if not doc:
            continue
        tok = doc[0]  # cada texto es una sola palabra

        lemma = tok.lemma_ or ""
        pos   = tok.pos_  or ""
        msd   = morph_to_msd(tok)

        if not dry_run:
            w_elem.set("lemma", lemma)
            w_elem.set("pos",   pos)
            if msd:
                w_elem.set("msd", msd)
            # Copiar al <reg><w> si existe
            if reg_w is not None:
                reg_w.set("lemma", lemma)
                reg_w.set("pos",   pos)
                if msd:
                    reg_w.set("msd", msd)
        else:
            print(f"  {w_elem.text or ''!r:20} → lemma={lemma} pos={pos} msd={msd}")

        annotated += 1

    print(f"✓ {annotated} tokens anotados", file=sys.stderr)

    if not dry_run:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        tree.write(str(output_path), encoding="UTF-8", xml_declaration=True,
                   pretty_print=True)
        print(f"✓ Guardado: {output_path}", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser(description="Anota morfológicamente el TEI src/ con latincy")
    ap.add_argument("input", help="Archivo src/ TEI a anotar")
    ap.add_argument("--out", default=None,
                    help="Archivo de salida (default: sobreescribe el input)")
    ap.add_argument("--model", default="la_core_web_lg",
                    help="Modelo spaCy a usar (default: la_core_web_lg)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Mostrar anotaciones sin modificar el archivo")
    args = ap.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: no existe {input_path}", file=sys.stderr)
        sys.exit(1)

    output_path = Path(args.out) if args.out else input_path
    annotate(input_path, output_path, args.model, args.dry_run)


if __name__ == "__main__":
    main()
