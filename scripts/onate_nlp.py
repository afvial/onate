#!/usr/bin/env python3
"""
onate_nlp.py — Anotación morfológica y sintáctica NLP del TEI diplomático (src/)

Anota cada <w> con @lemma, @pos y @msd usando latincy (spaCy) y, para las
palabras que están dentro de una oración <s>, también las dependencias:
  @n       posición de la palabra en su oración (1, 2, 3…)
  @head    @n de la palabra de la que depende (0 = raíz de la oración)
  @deprel  relación de dependencia (Universal Dependencies: nsubj, obj, amod…)

El modelo analiza cada <s> como una oración completa, con las palabras ya
tokenizadas por el pipeline (no vuelve a tokenizar), así que usa el contexto
para la morfología y puede calcular la sintaxis. Las palabras fuera de toda
<s> (encabezados, cabeceras) se analizan sueltas, como antes.
Con --por-palabra se recupera el comportamiento anterior (cada palabra sola,
sin dependencias), útil para comparar.

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

from onate_tokens import AUTHOR_FULL_NAMES

# Nombres propios (autores) que LatinCy suele lematizar/etiquetar mal por
# falta de vocabulario. Se aplica DESPUES de spaCy, sobreescribiendo su
# resultado, en vez de antes (a diferencia de NLP_QUERY_OVERRIDES, que
# cambia el texto que se le consulta al modelo).
# Sembrado automaticamente desde AUTHOR_FULL_NAMES (lemma=el propio nombre,
# pos=PROPN). Añadir aqui manualmente variantes declinadas que necesiten
# un lemma distinto al texto tal cual aparece, p.ej.:
#   MANUAL_LEMMA["Salae"] = ("Salas", "PROPN", "Case=Gen|Gender=Masc|Number=Sing")
MANUAL_LEMMA = {name: (name, "PROPN", "Case=Nom|Gender=Masc|Number=Sing") for name in AUTHOR_FULL_NAMES}
MANUAL_LEMMA["republica"] = ("respublica", "NOUN", "Case=Abl|Gender=Fem|Number=Sing")
MANUAL_LEMMA["sanctissimum"] = ("sanctus", "ADJ", "Case=Acc|Degree=Sup|Gender=Masc|Number=Sing")
MANUAL_LEMMA["Patriarcham"] = ("patriarcha", "NOUN", "Case=Acc|Gender=Masc|Number=Sing")

# "n" suelta (p. ej. «Petrus Nau. n... lib.», signo dudoso del impreso):
# sin análisis latino; "n." con punto sigue siendo la abreviatura de numero.
MANUAL_LEMMA["n"] = ("n", "X", "")

# expensa (gasto): LatinCy lo toma por participio de expendo.
for _f in ("expensa", "expensae", "expensam", "expensas", "expensis", "expensarum"):
    MANUAL_LEMMA[_f] = ("expensa", "NOUN", None)

# Effroenata: LatinCy lo toma por nombre propio por la mayúscula.
for _f in ("Effroenata", "effroenata", "Effroenatam", "effroenatam"):
    MANUAL_LEMMA[_f] = ("effroenatus", "ADJ", None)

# LatinCy lematiza mal circumstantia (circumsto, circumstantius…).
# msd=None: se conserva la morfología que da el modelo.
for _f in ("circumstantia", "circumstantiae", "circumstantiam", "circumstantiis",
           "circumstantijs", "circumstantias", "circumstantiarum"):
    MANUAL_LEMMA[_f] = ("circumstantia", "NOUN", None)
# conuentionalis (adj. escolástico, LatinCy lo toma por sustantivo)
for _f in ("conuentionalis", "conuentionale", "conuentionali", "conuentionalem",
           "conuentionales", "conuentionalia", "conuentionalium", "conuentionalibus"):
    MANUAL_LEMMA[_f] = ("conuentionalis", "ADJ", None)
TEI_NS  = "http://www.tei-c.org/ns/1.0"
TEI     = f"{{{TEI_NS}}}"

# Ancestros que excluyen la anotación
EXCLUDE_ANCESTORS = {"corr", "supplied"}  # "bibl" habilitado: se anota igual que el resto del texto

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
        # Castellano u otra lengua (<foreign>): no se analiza como latín
        if any(a.tag.endswith("}foreign") for a in w.iterancestors()):
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


def sentence_of(w_elem):
    """La <s> que contiene a w_elem, o None."""
    for anc in w_elem.iterancestors():
        if anc.tag == f"{TEI}s":
            return anc
    return None


def analyse_in_context(nlp, items, group=sentence_of):
    """
    Analiza las palabras agrupadas por oración <s>. Devuelve una lista
    paralela a items con (token_spacy | None, n, head, deprel).
    Las palabras fuera de toda <s> se devuelven con token None.
    `group(w)` da la unidad de análisis de cada palabra (por defecto su <s>;
    onate_sentences.py agrupa las partes de una oración partida entre
    columnas para analizarla entera).
    """
    from spacy.tokens import Doc
    groups, order = {}, []
    for k, (w_elem, norm, _) in enumerate(items):
        key = group(w_elem)   # el propio elemento (no id(): lxml reutiliza ids)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(k)

    out = [None] * len(items)
    for key in order:
        idx = groups[key]
        if key is None:
            continue
        words = ["".join(_nlp_query_text(items[k][1]).split()) or "_" for k in idx]
        # Cada palabra pasa por el tokenizador de LatinCy (que normaliza u/v,
        # i/j, acentos… igual que cuando se analizaba suelta) y luego se unen
        # en un solo Doc para que el modelo vea la oración entera.
        tdocs = [nlp.tokenizer(w) for w in words]
        doc = Doc.from_docs([td for td in tdocs if len(td)], ensure_whitespace=True)
        # from_docs marca el inicio de oración en cada palabra unida; se fija
        # explícitamente que la <s> es UNA sola oración (el analizador respeta
        # los límites ya establecidos)
        for t in doc[1:]:
            t.is_sent_start = False
        # Posición de cada palabra en el texto del Doc. La correspondencia
        # token → palabra se hace por posición en el texto (no por índice),
        # porque algún componente de LatinCy puede volver a dividir tokens
        # (enclíticos -que, -ne…) y desplazar los índices.
        starts, pos = [], 0
        for td in tdocs:
            if len(td):
                at = doc.text.find(td.text, pos)
                at = pos if at < 0 else at
                starts.append(at); pos = at + len(td.text)
            else:
                starts.append(None)
        valid = [(st, wi) for wi, st in enumerate(starts) if st is not None]
        import bisect
        keys = [st for st, _ in valid]

        for _, proc in nlp.pipeline:
            doc = proc(doc)

        def word_of(tok):
            j = bisect.bisect_right(keys, tok.idx) - 1
            return valid[j][1] if j >= 0 else None

        by_word = {}
        for tok in doc:
            wi = word_of(tok)
            if wi is not None:
                by_word.setdefault(wi, []).append(tok)
        for wi, k in enumerate(idx):
            toks = by_word.get(wi)
            if not toks:
                continue
            # rasgos: el primer token de la palabra (como cuando se analizaba
            # suelta); sintaxis: el token cuyo núcleo está fuera de la palabra
            main = next((t for t in toks if t.head.i == t.i or word_of(t.head) != wi), toks[0])
            hw = None if main.head.i == main.i else word_of(main.head)
            head = 0 if hw is None or hw == wi else hw + 1
            out[k] = (toks[0], wi + 1, head, main.dep_ or "")
    return out


def annotate(input_path: Path, output_path: Path, model_name: str, dry_run: bool,
             per_word: bool = False, cambios: str = None):
    parser = etree.XMLParser(remove_blank_text=False)
    tree   = etree.parse(str(input_path), parser)

    items = collect_w_elements(tree)
    if not items:
        print("No se encontraron <w> para anotar.", file=sys.stderr)
        return

    mode = "palabra a palabra" if per_word else "por oración"
    print(f"→ {len(items)} tokens a anotar con {model_name} ({mode})", file=sys.stderr)

    import spacy
    nlp = spacy.load(model_name)

    texts  = [_nlp_query_text(norm) for _, norm, _ in items]
    norms  = [norm for _, norm, _ in items]
    elems  = [(w, reg) for w, _, reg in items]

    # Análisis en contexto (por oración); lo que quede fuera de <s>, suelto
    ctx = [None] * len(items) if per_word else analyse_in_context(nlp, items)
    loose = [k for k, c in enumerate(ctx) if c is None]
    loose_docs = dict(zip(loose, nlp.pipe([texts[k] for k in loose], batch_size=256)))

    changed = {"lemma": 0, "pos": 0, "msd": 0}
    examples, all_changes = [], []
    annotated = with_deps = 0
    for k, ((w_elem, reg_w), norm) in enumerate(zip(elems, norms)):
        tok = ctx[k][0] if ctx[k] is not None else None
        doc = None if tok is not None else loose_docs.get(k)
        # Override manual (nombres propios que LatinCy lematiza mal)
        is_digit = norm.isdigit()
        is_manual = norm in MANUAL_LEMMA
        if is_digit:
            lemma, pos, msd = norm, "NUM", ""
        elif is_manual:
            lemma, pos, msd = MANUAL_LEMMA[norm]
            if msd is None:   # conservar la morfología de LatinCy
                _t = tok if tok is not None else (doc[0] if doc else None)
                msd = morph_to_msd(_t) if _t is not None else ""
                if pos in ("NOUN", "ADJ", "PROPN") and msd:
                    # rasgos verbales de un análisis previo como participio
                    _verb = ("Aspect=", "VerbForm=", "Voice=", "Tense=", "Mood=", "Person=")
                    msd = "|".join(f for f in msd.split("|") if not f.startswith(_verb))
        else:
            if tok is None:
                if not doc:
                    continue
                tok = doc[0]  # palabra suelta (fuera de <s>)
            lemma = tok.lemma_ or ""
            pos   = tok.pos_  or ""
            msd   = morph_to_msd(tok)

        # cuánto cambia respecto de la anotación anterior (si la había)
        for att, new in (("lemma", lemma), ("pos", pos), ("msd", msd)):
            old = w_elem.get(att)
            if old is not None and old != new:
                changed[att] += 1
                all_changes.append((norm, att, old, new))
                if len(examples) < 12 and att != "msd":
                    examples.append(f"{norm}: {att} {old} → {new}")

        deps = ctx[k][1:] if ctx[k] is not None else None
        if not dry_run:
            for target in (w_elem, reg_w):
                if target is None:
                    continue
                target.set("lemma", lemma)
                target.set("pos",   pos)
                if msd:
                    target.set("msd", msd)
                elif "msd" in target.attrib:
                    del target.attrib["msd"]
                if is_manual:
                    target.set("manual", "1")
                if deps is not None:
                    n, head, deprel = deps
                    target.set("n", str(n))
                    target.set("head", str(head))
                    if deprel:
                        target.set("deprel", deprel)
                else:
                    for att in ("n", "head", "deprel"):
                        target.attrib.pop(att, None)
        else:
            print(f"  {w_elem.text or ''!r:20} → lemma={lemma} pos={pos} msd={msd}")

        annotated += 1
        if deps is not None:
            with_deps += 1

    print(f"✓ {annotated} tokens anotados, {with_deps} con dependencias", file=sys.stderr)
    if any(changed.values()):
        print(f"  Cambios respecto de la anotación anterior: lema {changed['lemma']}, "
              f"categoría {changed['pos']}, morfología {changed['msd']}", file=sys.stderr)
        for e in examples:
            print(f"    {e}", file=sys.stderr)
    if cambios:
        Path(cambios).parent.mkdir(parents=True, exist_ok=True)
        with open(cambios, "w", encoding="utf-8") as fh:
            fh.write("palabra\tcampo\tantes\tahora\n")
            for r in all_changes:
                fh.write("\t".join(r) + "\n")
        print(f"  Todos los cambios → {cambios}", file=sys.stderr)

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
    ap.add_argument("--cambios", metavar="TSV",
                    help="Escribir en un TSV todos los cambios respecto de la anotación anterior")
    ap.add_argument("--por-palabra", action="store_true",
                    help="Analizar cada palabra suelta, sin contexto ni dependencias (comportamiento anterior)")
    args = ap.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: no existe {input_path}", file=sys.stderr)
        sys.exit(1)

    output_path = Path(args.out) if args.out else input_path
    annotate(input_path, output_path, args.model, args.dry_run, per_word=args.por_palabra,
             cambios=args.cambios)


if __name__ == "__main__":
    main()
