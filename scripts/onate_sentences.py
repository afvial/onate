#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
onate_sentences.py
──────────────────
Detecta si una <s> que termina al final de una columna continúa en la
columna siguiente, y codifica el span con @part / @next / @prev.

Uso:
    python3 scripts/onate_sentences.py output/disp63_bibl_completo.xml
    python3 scripts/onate_sentences.py output/disp63_bibl_completo.xml \
            --output output/disp63_bibl_sentences.xml
    python3 scripts/onate_sentences.py output/disp63_bibl_completo.xml --report

Resultado TEI para <s> que continúa entre columnas:
    <!-- final de col. A -->
    <s xml:id="s_1_I" part="I" next="#s_1_F">…con<lb break="no"/></s>

    <!-- inicio de col. B -->
    <s xml:id="s_1_F" part="F" prev="#s_1_I">sistit…</s>

Para casos dudosos (sin punto pero mayúscula inicial) añade @cert="low"
sin modificar @part, para revisión manual del editor.

Heurística
──────────
    1. Palabra partida (<lb break="no"/> en último <w>)  → CONTINÚA siempre
    2. Sin punct. final + primera palabra en minúscula    → CONTINÚA
    3. Punct. final (. ? !) + primera palabra en mayúsc.  → NUEVA oración
    4. Sin punct. final + primera palabra en mayúscula    → DUDOSA (cert="low")
    5. Punct. final + primera palabra en minúscula        → DUDOSA (anomalía)
"""

import sys
import argparse
from pathlib import Path
from lxml import etree

# Importar función de reconstrucción con s larga
try:
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "."))
    from onate_tokens import apply_long_s_to_split
    _HAS_LONG_S = True
except ImportError:
    _HAS_LONG_S = False
    def apply_long_s_to_split(left, right): return None, None

# ─── Namespaces ───────────────────────────────────────────────────────────────

NS     = "http://www.tei-c.org/ns/1.0"
XML_NS = "http://www.w3.org/XML/1998/namespace"

def T(local):
    """Nombre de elemento TEI con namespace."""
    return f"{{{NS}}}{local}"

def xml_id_attr():
    return f"{{{XML_NS}}}id"

# ─── Helpers de análisis ──────────────────────────────────────────────────────

CLOSING_PUNCT = {".", "?", "!"}


def all_sentences(div):
    """Todas las <s> dentro de un <div>, en orden de documento."""
    return div.findall(f".//{T('s')}")


def last_sentence(div):
    ss = all_sentences(div)
    return ss[-1] if ss else None


def first_sentence(div):
    ss = all_sentences(div)
    return ss[0] if ss else None


def ends_with_closing_punct(s_elem):
    """
    True si el último <pc> o <w> significativo del <s> es puntuación de cierre.
    Recorre los descendientes en orden inverso ignorando <lb/> y similares.
    """
    for elem in reversed(list(s_elem.iter())):
        if elem is s_elem:
            continue
        if elem.tag == T('pc'):
            return (elem.text or '').strip() in CLOSING_PUNCT
        if elem.tag == T('w'):
            return False   # último elemento léxico es una palabra, no punto
    return False


def has_word_split(s_elem):
    """
    True si el último <w> contiene un <lb break='no'/>,
    indicando que la palabra continúa en la siguiente línea/columna.
    """
    ws = list(s_elem.iter(T('w')))
    if not ws:
        return False
    last_w = ws[-1]
    for lb in last_w.findall(T('lb')):
        if lb.get('break') == 'no':
            return True
    return False


def first_word_text(s_elem):
    """
    Texto del primer <w> del <s> en orden de documento,
    ignorando los <w> que estén dentro de <orig> (variante diplomática).
    """
    for w in s_elem.iter(T('w')):
        # Subir por los ancestros hasta s_elem buscando <orig>
        parent = w.getparent()
        inside_orig = False
        while parent is not None and parent is not s_elem:
            if parent.tag == T('orig'):
                inside_orig = True
                break
            parent = parent.getparent()
        if not inside_orig:
            t = (w.text or '').strip()
            if t:
                return t
    return ''


# ─── Diagnóstico de boundary ──────────────────────────────────────────────────

def diagnose(div_a, div_b):
    """
    Analiza el boundary entre div_a (fin) y div_b (inicio).

    Retorna: ('continues' | 'new' | 'uncertain', info_dict)
    """
    s_end   = last_sentence(div_a)
    s_start = first_sentence(div_b)

    if s_end is None or s_start is None:
        return 'uncertain', {'reason': 'no <s> en una de las columnas'}

    word_split   = has_word_split(s_end)
    closes       = ends_with_closing_punct(s_end)
    first_word   = first_word_text(s_start)
    starts_lower = bool(first_word) and first_word[0].islower()

    info = {
        'word_split':   word_split,
        'closes':       closes,
        'first_word':   first_word,
        'starts_lower': starts_lower,
    }

    if word_split:
        info['reason'] = 'palabra partida (lb break=no)'
        return 'continues', info

    if not closes and starts_lower:
        info['reason'] = 'sin punct. final + minúscula inicial'
        return 'continues', info

    if closes and not starts_lower:
        info['reason'] = 'punct. final + mayúscula inicial'
        return 'new', info

    if not closes and not starts_lower:
        info['reason'] = 'sin punct. final pero mayúscula inicial'
        return 'uncertain', info

    # closes and starts_lower — anomalía
    info['reason'] = 'punct. final pero minúscula inicial (anomalía)'
    return 'uncertain', info


# ─── Aplicación de marcas TEI ────────────────────────────────────────────────

def set_xid(elem, val):
    elem.set(xml_id_attr(), val)


def orig_text_of_w(w_elem):
    """
    Devuelve el texto diplomático de un <w>, prefiriendo la lectura
    dentro de <orig> si el padre es un <choice>.
    Maneja también el caso en que <w> está dentro de <reg>/<choice>.
    Solo extrae el texto del nodo, no de hijos como <lb>.
    """
    parent = w_elem.getparent()
    # Caso directo: <choice>/<orig>/<w>  — padre es <choice>
    if parent is not None and parent.tag == T('choice'):
        orig = parent.find(T('orig'))
        if orig is not None:
            orig_w = orig.find(T('w'))
            if orig_w is not None:
                return (orig_w.text or '').strip()
    # Caso inverso: <w> está en <reg>; abuelo puede ser <choice>
    if parent is not None and parent.tag == T('reg'):
        grandparent = parent.getparent()
        if grandparent is not None and grandparent.tag == T('choice'):
            orig = grandparent.find(T('orig'))
            if orig is not None:
                orig_w = orig.find(T('w'))
                if orig_w is not None:
                    return (orig_w.text or '').strip()
    return (w_elem.text or '').strip()


def _w_f_in_choice(w_f):
    """True si w_f está dentro de <reg>/<choice> — el <choice> ya
    muestra la forma orig visualmente; no hay que añadir @orig."""
    parent = w_f.getparent()
    if parent is not None and parent.tag == T('reg'):
        gp = parent.getparent()
        if gp is not None and gp.tag == T('choice'):
            return True
    return False


def _make_choice(parent_elem, w_elem, orig_text, reg_text, keep_lb=False):
    """
    Reemplaza w_elem en su padre por un <choice>:
      <choice>
        <orig><w>orig_text[<lb break="no"/>]</w></orig>
        <reg><w>reg_text</w></reg>
      </choice>
    Si keep_lb=True conserva el <lb break="no"/> dentro del <orig>/<w>.
    """
    idx = list(parent_elem).index(w_elem)
    parent_elem.remove(w_elem)

    choice = etree.Element(T('choice'))
    orig_el = etree.SubElement(choice, T('orig'))
    w_orig  = etree.SubElement(orig_el, T('w'))
    w_orig.text = orig_text
    if keep_lb:
        lb = etree.SubElement(w_orig, T('lb'))
        lb.set('break', 'no')

    reg_el = etree.SubElement(choice, T('reg'))
    w_reg  = etree.SubElement(reg_el, T('w'))
    w_reg.text = reg_text

    parent_elem.insert(idx, choice)
    return choice


def add_orig_to_split_words(s_end, s_start):
    """
    Cuando hay palabra partida entre columnas, reconstruye la forma
    completa (reg) y la forma diplomática con ſ (orig), y genera
    <choice><orig>/<reg></choice> en ambos extremos — análogo al
    tratamiento de palabras partidas por cambio de línea.
    """
    all_w_end = list(s_end.iter(T('w')))
    if not all_w_end:
        return
    w_i = all_w_end[-1]
    has_split = any(lb.get('break') == 'no' for lb in w_i.findall(T('lb')))
    if not has_split:
        return

    # Primer <w> de s_start que no esté dentro de <orig>
    w_f = None
    for w in s_start.iter(T('w')):
        p = w.getparent()
        in_orig = False
        while p is not None:
            if p.tag == T('orig'):
                in_orig = True
                break
            p = p.getparent()
        if not in_orig:
            w_f = w
            break

    if w_f is None:
        return

    part_i = orig_text_of_w(w_i)   # "con"
    part_f = orig_text_of_w(w_f)   # "suetudine" / "sistit"
    reg    = part_i + part_f        # "consuetudine" / "consistit"

    # Forma diplomática con ſ
    if _HAS_LONG_S:
        orig_left, orig_right = apply_long_s_to_split(part_i, part_f)
    else:
        orig_left, orig_right = None, None

    diplo_i = orig_left  if orig_left  else part_i   # "con"  / "conſ"
    diplo_f = orig_right if orig_right else part_f   # "ſuetudine" / "ſiſtit"

    # Padre directo de w_i (puede ser <s> u otro elemento)
    parent_i = w_i.getparent()
    if parent_i is not None:
        _make_choice(parent_i, w_i, diplo_i, reg, keep_lb=True)

    # Padre directo de w_f (puede ser <s>, <reg>, etc.)
    # Si ya está en <choice>/<reg>, reemplazar ese <choice> entero
    parent_f = w_f.getparent()
    if parent_f is not None and parent_f.tag == T('reg'):
        gp = parent_f.getparent()
        if gp is not None and gp.tag == T('choice'):
            ggp = gp.getparent()
            if ggp is not None:
                _make_choice(ggp, gp, diplo_f, reg, keep_lb=False)
            return
    if parent_f is not None:
        _make_choice(parent_f, w_f, diplo_f, reg, keep_lb=False)


def apply_continues(s_end, s_start, counter):
    """Añade @part / @next / @prev al par de <s> que abarca una columna.
    Si hay palabra partida, añade también @orig con la forma completa."""
    id_i = f"s_{counter}_I"
    id_f = f"s_{counter}_F"

    set_xid(s_end, id_i)
    s_end.set('part', 'I')
    s_end.set('next', f'#{id_f}')

    set_xid(s_start, id_f)
    s_start.set('part', 'F')
    s_start.set('prev', f'#{id_i}')

    add_orig_to_split_words(s_end, s_start)

    return id_i, id_f


def apply_uncertain(s_end, s_start):
    """Marca los dos extremos con @cert='low' para revisión manual."""
    s_end.set('cert',  'low')
    s_start.set('cert', 'low')


# ─── Pipeline principal ───────────────────────────────────────────────────────

def col_label(div, idx):
    """Etiqueta legible para el informe: p35_izq, p35_der, etc."""
    n   = div.get('n', '?')
    col = 'izq' if idx % 2 == 0 else 'der'
    return f"p{n}_{col}"


def process(xml_path: Path, output_path: Path, report_only: bool = False):
    parser = etree.XMLParser(remove_blank_text=False)
    tree   = etree.parse(str(xml_path), parser)
    root   = tree.getroot()

    divs = root.findall(f".//{T('div')}[@type='page']")

    stats   = {'continues': 0, 'new': 0, 'uncertain': 0}
    counter = 1
    rows    = []

    for i in range(len(divs) - 1):
        div_a = divs[i]
        div_b = divs[i + 1]

        label_a = col_label(div_a, i)
        label_b = col_label(div_b, i + 1)

        result, info = diagnose(div_a, div_b)
        stats[result] += 1

        s_end   = last_sentence(div_a)
        s_start = first_sentence(div_b)

        rows.append({
            'from':   label_a,
            'to':     label_b,
            'result': result,
            'info':   info,
        })

        if not report_only:
            if result == 'continues':
                apply_continues(s_end, s_start, counter)
                counter += 1
            elif result == 'uncertain':
                apply_uncertain(s_end, s_start)

    # ── Informe ────────────────────────────────────────────────────────────────
    print()
    print("  Pares de columnas analizados :", len(rows))
    print(f"  <s> continúan entre columnas : {stats['continues']}")
    print(f"  Nueva oración (sin cambio)   : {stats['new']}")
    print(f"  Dudosas (cert=\"low\")          : {stats['uncertain']}")
    print()
    print(f"  {'Transición':<20}  {'Diagnóstico':<12}  Razón")
    print(f"  {'-'*20}  {'-'*12}  {'-'*40}")
    for r in rows:
        print(f"  {r['from']+' → '+r['to']:<20}  {r['result']:<12}  {r['info']['reason']}")
    print()

    if report_only:
        print("  (modo --report: no se ha modificado ningún archivo)")
        return

    tree.write(str(output_path), encoding='UTF-8',
               xml_declaration=True, pretty_print=True)
    print(f"  ✓ Escrito en: {output_path}")


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Detecta y codifica límites de <s> entre columnas TEI.'
    )
    parser.add_argument('input',
        help='XML ensamblado (output/disp63_bibl_completo.xml)')
    parser.add_argument('--output', '-o',
        help='Archivo de salida (por defecto: in-place)')
    parser.add_argument('--report', action='store_true',
        help='Solo mostrar diagnóstico sin modificar el XML')
    args = parser.parse_args()

    xml_path = Path(args.input)
    if not xml_path.exists():
        print(f"Error: no existe {xml_path}", file=sys.stderr)
        sys.exit(1)

    out_path = Path(args.output) if args.output else xml_path

    process(xml_path, out_path, report_only=args.report)


if __name__ == '__main__':
    main()
