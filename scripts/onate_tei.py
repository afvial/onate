#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
onate_tei.py
────────────
Construcción del árbol TEI XML a partir de tokens normalizados.
Importa de onate_tokens y onate_bibl.
"""

from lxml import etree
from onate_tokens import (
    TEI_NS, XI_NS, PC_TYPES,
    ABBREV_EXPAN, ORIG_REG, MACRON_MAP, LONG_S, ORIG_CHARS,
    _apply_long_s_roots, apply_abbrev_tags, tokenize, classify_tag,
)
from onate_bibl import join_split_words, group_bibl_tokens, group_legal_tokens

# Mapa de macrones por posición
# Final → sustituye vocal+m; medial → sustituye vocal+n
_MACRON_FINAL = {"ā": "am", "ē": "em", "ī": "im", "ō": "om", "ū": "um",
                 "Ā": "Am", "Ē": "Em", "Ī": "Im", "Ō": "Om", "Ū": "Um"}
_MACRON_MEDIAL = {"ā": "an", "ē": "en", "ī": "in", "ō": "on", "ū": "un",
                  "Ā": "An", "Ē": "En", "Ī": "In", "Ō": "On", "Ū": "Un"}
_MACRON_CHARS  = set(_MACRON_FINAL)


def _expand_macrons(text: str) -> str | None:
    """
    Expande macrones en una palabra según su posición:
      medial (no último carácter significativo) → vocal + n
      final  (último carácter significativo)     → vocal + m
    Devuelve la forma expandida o None si no hay macrones.
    """
    if not any(c in text for c in _MACRON_CHARS):
        return None
    result = []
    stripped = text.rstrip(".")
    for idx, ch in enumerate(text):
        if ch not in _MACRON_CHARS:
            result.append(ch); continue
        # ¿Es el último carácter significativo (antes del punto final)?
        is_final = (idx == len(stripped) - 1)
        expansion = _MACRON_FINAL[ch] if is_final else _MACRON_MEDIAL[ch]
        result.append(expansion)
    return "".join(result)


def add_w(parent, text: str, expansion: str = None, is_abbrev: bool = False):
    """
    Añade <w> al parent con el encoding correcto:
      - <choice><abbr><w/><expan> si es abreviatura
      - <choice><orig><w/><reg>  si es grafía original (ORIG_REG o ae→æ)
      - <w> simple si no hay choice
    """
    # ORIG_REG manual tiene prioridad absoluta
    reg = ORIG_REG.get(text) or ORIG_REG.get(text.replace("ſ", "s"))

    # s larga: lookup en LONG_S (case-insensitive, preserva mayúscula inicial)
    # Se calcula siempre, incluso para abreviaturas, para poder generar
    # <choice> anidado cuando hay abbr + variante gráfica.
    # Para abreviaturas se strip el punto final antes de buscar.
    long_s_orig = None
    if not reg:
        # Strip punto final para abreviaturas (p.ej. "disput." → "disput")
        text_base   = text.rstrip(".") if is_abbrev else text
        suffix      = text[len(text_base):] if is_abbrev else ""
        key = text_base.lower()
        if key in LONG_S:
            orig_form = LONG_S[key] + suffix
            # Preservar mayúscula inicial si la tiene
            if text and text[0].isupper():
                orig_form = orig_form[0].upper() + orig_form[1:]
            if orig_form != text:
                long_s_orig = orig_form
        else:
            base_result = _apply_long_s_roots(text_base)
            if base_result:
                long_s_orig = base_result + suffix

    # Detección automática ae→æ (solo si no hay ya un choice)
    ae_orig = None
    if not reg and not long_s_orig and not is_abbrev and "ae" in text:
        ae_orig = text.replace("ae", "æ")

    if is_abbrev and expansion:
        tag_type = classify_tag(text, expansion)

        choice = etree.SubElement(parent, f"{{{TEI_NS}}}choice")
        if tag_type == "abbr":
            abbr_el = etree.SubElement(choice, f"{{{TEI_NS}}}abbr")
            if long_s_orig:
                # <abbr><choice><orig><w>diſput.</w></orig>
                #               <reg><w>disp.</w></reg></choice></abbr>
                inner_choice = etree.SubElement(abbr_el, f"{{{TEI_NS}}}choice")
                orig_el = etree.SubElement(inner_choice, f"{{{TEI_NS}}}orig")
                w       = etree.SubElement(orig_el, f"{{{TEI_NS}}}w")
                w.text  = long_s_orig
                reg_el  = etree.SubElement(inner_choice, f"{{{TEI_NS}}}reg")
                w_reg   = etree.SubElement(reg_el, f"{{{TEI_NS}}}w")
                w_reg.text = text
            else:
                w      = etree.SubElement(abbr_el, f"{{{TEI_NS}}}w")
                w.text = text
            expan  = etree.SubElement(choice, f"{{{TEI_NS}}}expan")
            w_exp  = etree.SubElement(expan,  f"{{{TEI_NS}}}w")
            w_exp.text = expansion
        else:  # orig
            inner  = etree.SubElement(choice, f"{{{TEI_NS}}}orig")
            w      = etree.SubElement(inner,  f"{{{TEI_NS}}}w")
            w.text = text
            reg_el = etree.SubElement(choice, f"{{{TEI_NS}}}reg")
            w_reg  = etree.SubElement(reg_el, f"{{{TEI_NS}}}w")
            w_reg.text = expansion
    elif reg:
        choice = etree.SubElement(parent, f"{{{TEI_NS}}}choice")
        orig   = etree.SubElement(choice, f"{{{TEI_NS}}}orig")
        w      = etree.SubElement(orig,   f"{{{TEI_NS}}}w")
        w.text = text
        reg_el = etree.SubElement(choice, f"{{{TEI_NS}}}reg")
        w_reg  = etree.SubElement(reg_el, f"{{{TEI_NS}}}w")
        w_reg.text = reg
    elif long_s_orig and not is_abbrev:
        choice = etree.SubElement(parent, f"{{{TEI_NS}}}choice")
        orig   = etree.SubElement(choice, f"{{{TEI_NS}}}orig")
        w      = etree.SubElement(orig,   f"{{{TEI_NS}}}w")
        w.text = long_s_orig
        reg_el = etree.SubElement(choice, f"{{{TEI_NS}}}reg")
        w_reg  = etree.SubElement(reg_el, f"{{{TEI_NS}}}w")
        w_reg.text = text
    elif ae_orig:
        choice = etree.SubElement(parent, f"{{{TEI_NS}}}choice")
        orig   = etree.SubElement(choice, f"{{{TEI_NS}}}orig")
        w      = etree.SubElement(orig,   f"{{{TEI_NS}}}w")
        w.text = ae_orig
        reg_el = etree.SubElement(choice, f"{{{TEI_NS}}}reg")
        w_reg  = etree.SubElement(reg_el, f"{{{TEI_NS}}}w")
        w_reg.text = text
    else:
        # Macrones en texto plano (no marcado como abbrev por Transkribus)
        macron_exp = _expand_macrons(text) if not is_abbrev else None
        if macron_exp and macron_exp != text:
            choice = etree.SubElement(parent, f"{{{TEI_NS}}}choice")
            abbr   = etree.SubElement(choice, f"{{{TEI_NS}}}abbr")
            w      = etree.SubElement(abbr,   f"{{{TEI_NS}}}w")
            w.text = text
            expan  = etree.SubElement(choice, f"{{{TEI_NS}}}expan")
            w_exp  = etree.SubElement(expan,  f"{{{TEI_NS}}}w")
            w_exp.text = macron_exp
        else:
            w = etree.SubElement(parent, f"{{{TEI_NS}}}w")
            w.text = text


def apply_long_s_to_split(left: str, right: str):
    """
    Aplica LONG_S (y como fallback LONG_S_ROOTS) a una palabra partida por lb.
    Reconstruye la palabra completa, busca la forma diplomática y distribuye
    las grafías entre left y right según la longitud original.
    Devuelve (orig_left, orig_right) o (None, None) si no aplica.
    """
    full = left + right
    key = full.lower()
    if key in LONG_S:
        orig_full = LONG_S[key]
    else:
        orig_full = _apply_long_s_roots(full)
        if orig_full is None:
            return None, None
    # Preservar mayúscula inicial
    if full and full[0].isupper():
        orig_full = orig_full[0].upper() + orig_full[1:]
    if orig_full == full:
        return None, None
    orig_left  = orig_full[:len(left)]
    orig_right = orig_full[len(left):]
    return orig_left, orig_right


def add_w_lb(parent, left: str, right: str, expansion: str = None, lb_n: int = None):
    """
    Añade una palabra partida por salto de línea:
      <w>left<lb break="no"/>right</w>
    Con <choice><orig> o <choice><abbr> si hay expansion.
    """
    # Texto completo reconstruido para classify_tag
    full_text = left + right
    reg_full = ORIG_REG.get(full_text) or ORIG_REG.get(full_text.replace("ſ","s"))

    # LONG_S para palabras partidas
    long_s_left, long_s_right = apply_long_s_to_split(left, right)

    # ae→æ para palabras partidas
    ae_full = None
    if not reg_full and not long_s_left and "ae" in full_text:
        ae_full = full_text.replace("ae", "æ")
        if ae_full == full_text:
            ae_full = None

    def _make_w_lb(parent_el, w_left, w_right):
        w = etree.SubElement(parent_el, f"{{{TEI_NS}}}w")
        w.text = w_left
        lb = etree.SubElement(w, f"{{{TEI_NS}}}lb")
        lb.set("break", "no")
        if lb_n: lb.set("n", str(lb_n))
        lb.tail = w_right
        return w

    if expansion:
        tag_type = classify_tag(full_text, expansion)
        choice = etree.SubElement(parent, f"{{{TEI_NS}}}choice")
        inner  = etree.SubElement(choice,
                     f"{{{TEI_NS}}}abbr" if tag_type == "abbr"
                     else f"{{{TEI_NS}}}orig")
        _make_w_lb(inner, left, right)
        outer_tag = f"{{{TEI_NS}}}expan" if tag_type == "abbr" else f"{{{TEI_NS}}}reg"
        outer  = etree.SubElement(choice, outer_tag)
        w_out  = etree.SubElement(outer, f"{{{TEI_NS}}}w")
        w_out.text = expansion
    elif reg_full:
        choice = etree.SubElement(parent, f"{{{TEI_NS}}}choice")
        orig   = etree.SubElement(choice, f"{{{TEI_NS}}}orig")
        _make_w_lb(orig, left, right)
        reg_el = etree.SubElement(choice, f"{{{TEI_NS}}}reg")
        w_reg  = etree.SubElement(reg_el, f"{{{TEI_NS}}}w")
        w_reg.text = reg_full
    elif long_s_left:
        choice = etree.SubElement(parent, f"{{{TEI_NS}}}choice")
        orig   = etree.SubElement(choice, f"{{{TEI_NS}}}orig")
        _make_w_lb(orig, long_s_left, long_s_right)
        reg_el = etree.SubElement(choice, f"{{{TEI_NS}}}reg")
        w_reg  = etree.SubElement(reg_el, f"{{{TEI_NS}}}w")
        w_reg.text = full_text
    elif ae_full:
        ae_left  = ae_full[:len(left)]
        ae_right = ae_full[len(left):]
        choice = etree.SubElement(parent, f"{{{TEI_NS}}}choice")
        orig   = etree.SubElement(choice, f"{{{TEI_NS}}}orig")
        _make_w_lb(orig, ae_left, ae_right)
        reg_el = etree.SubElement(choice, f"{{{TEI_NS}}}reg")
        w_reg  = etree.SubElement(reg_el, f"{{{TEI_NS}}}w")
        w_reg.text = full_text
    else:
        _make_w_lb(parent, left, right)


def add_pc(parent, text: str):
    pc = etree.SubElement(parent, f"{{{TEI_NS}}}pc")
    pc.set("type", PC_TYPES.get(text, "other"))
    if text in ("[", "("): pc.set("subtype", "open")
    elif text in ("]", ")"): pc.set("subtype", "close")
    pc.text = text


def emit_legal_bibl(parent, legal_tok: dict):
    """Emite <hi rend="italic"><bibl type="legal"> para una cita jurídica.
    En el impreso toda referencia bibliográfica va en cursiva, incluyendo
    las jurídicas aunque Transkribus no las marque como tal.
    """
    hi   = etree.SubElement(parent, f"{{{TEI_NS}}}hi")
    hi.set("rend", "italic")
    bibl = etree.SubElement(hi, f"{{{TEI_NS}}}bibl")
    bibl.set("type", "legal")
    for tok in legal_tok["toks"]:
        emit_token(bibl, tok)


def emit_hi_bibl(parent, hi_tok: dict):
    """Emite un único <hi rend="italic"> por bloque bibliográfico.
    Dentro van todos los <bibl> y los conectores inter (ibi, ex parte, &)
    en el orden en que aparecen, separados por el & que los precede.

    Estructura resultante:
      <hi rend="italic">
        <bibl>...</bibl>          ← primer bibl
        & et                      ← conector (&) + inter (ibi / ex parte)
        <bibl>...</bibl>          ← segundo bibl
      </hi>
    """
    groups = hi_tok["groups"]
    if not groups:
        return

    # Un único <hi> para todo el bloque
    hi = etree.SubElement(parent, f"{{{TEI_NS}}}hi")
    hi.set("rend", "italic")

    for group in groups:
        if group["kind"] == "bibl":
            bibl = etree.SubElement(hi, f"{{{TEI_NS}}}bibl")
            for tok in group["toks"]:
                emit_token(bibl, tok)
        else:  # inter — ibi, ex parte, etc. van dentro del <hi>
            for tok in group["toks"]:
                emit_token(hi, tok)



def emit_token(parent, tok: dict):
    """Emite un token normalizado como elemento TEI."""
    kind = tok["kind"]
    if kind == "sol":
        lb = etree.SubElement(parent, f"{{{TEI_NS}}}lb")
        lb.set("n", tok["text"])
    elif kind == "word_lb":
        add_w_lb(parent, tok["left"], tok["right"],
                 expansion=tok["expansion"], lb_n=tok.get("lb_n"))
    elif kind == "word":
        add_w(parent, tok["text"], expansion=tok["expansion"],
              is_abbrev=(tok["expansion"] is not None))
    elif kind == "abbrev_dot":
        _abbr_text = tok["text"]
        _expan_text = ABBREV_EXPAN.get(_abbr_text, ABBREV_EXPAN.get(_abbr_text.lower(), ""))
        # Reutilizar add_w para generar <choice> anidado si hay long_s
        add_w(parent, _abbr_text, expansion=_expan_text, is_abbrev=True)
    elif kind == "amp":
        choice = etree.SubElement(parent, f"{{{TEI_NS}}}choice")
        abbr   = etree.SubElement(choice, f"{{{TEI_NS}}}abbr")
        w      = etree.SubElement(abbr,   f"{{{TEI_NS}}}w")
        w.text = "&"
        expan  = etree.SubElement(choice, f"{{{TEI_NS}}}expan")
        w_exp  = etree.SubElement(expan,  f"{{{TEI_NS}}}w")
        w_exp.text = "et"
    elif kind in ("pc", "dot"):
        add_pc(parent, tok["text"])
    if tok.get("eol"):
        lb = etree.SubElement(parent, f"{{{TEI_NS}}}lb")
        lb.set("n", str(tok["eol"]))


def _flatten_lines_to_raw_tokens(lines: list, first_lb_ref: list) -> list:
    """
    Aplana una lista de líneas en raw_tokens (5-tuplas).
    first_lb_ref es una lista de un elemento usada como referencia mutable
    para saber si ya se emitió el primer 'sol'.
    """
    raw_tokens = []
    for li, line in enumerate(lines):
        is_last = (li == len(lines) - 1)
        next_n  = lines[li + 1]["line_n"] if not is_last else None
        segments = apply_abbrev_tags(line["text"], line["abbrevs"])
        line_toks = []
        if not first_lb_ref[0]:
            line_toks.append(("sol", str(line["line_n"]), None, False, False))
            first_lb_ref[0] = True
        for seg in segments:
            exp = seg["expansion"] if seg["is_abbrev"] else None
            for ttype, ttext in tokenize(seg["text"]):
                tok_exp = exp if (ttype == "word" and seg["is_abbrev"]) else None
                line_toks.append((ttype, ttext, tok_exp, False, False))
        if line_toks and not is_last:
            last = line_toks[-1]
            if line["soft_hyphen"]:
                line_toks[-1] = (last[0], last[1], last[2], False, next_n)
            else:
                line_toks[-1] = (last[0], last[1], last[2], next_n, False)
        raw_tokens.extend(line_toks)
    return raw_tokens


def _offset_is_italic(offset: int, italic_spans: list) -> bool:
    """True si offset cae dentro de algún italic_span."""
    return any(s["offset"] <= offset < s["offset"] + s["length"]
               for s in italic_spans)


def _tokenize_with_italic(span_text: str, span_offset: int,
                           span_abbrevs: list, italic_spans: list) -> list:
    """
    Tokeniza span_text y asigna italic por token según su posición real
    en la línea original (span_offset + posición dentro del span).
    Busca cada token en el texto para obtener su posición exacta,
    evitando desfases causados por espacios que tokenize() descarta.
    """
    toks = []
    segs = apply_abbrev_tags(span_text, span_abbrevs)
    search_from = 0  # posición de búsqueda dentro de span_text
    for seg in segs:
        exp = seg["expansion"] if seg["is_abbrev"] else None
        for ttype, ttext in tokenize(seg["text"]):
            tok_exp = exp if (ttype == "word" and seg["is_abbrev"]) else None
            # Buscar la posición exacta del token en el texto del span
            idx = span_text.find(ttext, search_from)
            if idx == -1:
                idx = search_from  # fallback si no se encuentra
            char_pos_in_line = span_offset + idx
            italic = _offset_is_italic(char_pos_in_line, italic_spans)
            toks.append((ttype, ttext, tok_exp, False, False, italic))
            search_from = idx + len(ttext)
    return toks


def _flatten_spans(lines: list) -> list:
    """
    Devuelve lista de (raw_6tuples, is_sent_end) por SPAN.
    6-tupla: (ttype, ttext, tok_exp, eol, split, is_italic)
    El italic se determina por la posición exacta de cada token en el texto
    de la línea, usando italic_spans del PAGE XML como fuente de verdad.
    """
    result   = []
    first_lb = [False]

    for li, line in enumerate(lines):
        if not line["text"].strip():
            continue
        is_last_line = (li == len(lines) - 1)
        next_n       = lines[li + 1]["line_n"] if not is_last_line else None
        text         = line["text"]
        abbrevs      = line["abbrevs"]
        sent_spans   = line.get("sentence_spans", [])
        italic_spans = line.get("italic_spans", [])

        lb_tok = None
        if not first_lb[0]:
            lb_tok = ("sol", str(line["line_n"]), None, False, False, False)
            first_lb[0] = True

        if not sent_spans:
            # Sin sentence_spans: toda la línea como un span continuo
            span_abbrevs = abbrevs
            toks = []
            if lb_tok:
                toks.append(lb_tok)
            toks.extend(_tokenize_with_italic(text, 0, span_abbrevs, italic_spans))
            if toks and not is_last_line:
                last = toks[-1]
                if line["soft_hyphen"]:
                    toks[-1] = (last[0], last[1], last[2], False, next_n, last[5])
                else:
                    toks[-1] = (last[0], last[1], last[2], next_n, False, last[5])
            result.append((toks, False))
        else:
            for si, span in enumerate(sent_spans):
                is_last_span = (si == len(sent_spans) - 1)
                span_offset  = span["offset"]
                span_text    = text[span_offset: span_offset + span["length"]]

                span_abbrevs = [
                    {**a, "offset": a["offset"] - span_offset}
                    for a in abbrevs
                    if span_offset <= a["offset"] < span_offset + span["length"]
                ]

                toks = []
                if lb_tok and si == 0:
                    toks.append(lb_tok)
                toks.extend(_tokenize_with_italic(
                    span_text, span_offset, span_abbrevs, italic_spans))

                if is_last_span and toks and not is_last_line:
                    last = toks[-1]
                    if line["soft_hyphen"]:
                        toks[-1] = (last[0], last[1], last[2], False, next_n, last[5])
                    else:
                        toks[-1] = (last[0], last[1], last[2], next_n, False, last[5])

                if not is_last_span:
                    is_sent_end = True
                elif not is_last_line:
                    next_line  = lines[li + 1]
                    next_spans = next_line.get("sentence_spans", [])
                    next_continued = bool(next_spans and next_spans[0].get("continued"))
                    is_sent_end = not next_continued
                else:
                    is_sent_end = True
                result.append((toks, is_sent_end))

    return result


def _group_spans_into_sentences(spans: list) -> list:
    """
    Agrupa spans en oraciones según is_sent_end.
    Devuelve lista de listas de raw_6tuples (una lista de spans por oración).
    """
    sentences, current = [], []
    for raw, is_sent_end in spans:
        current.append(raw)
        if is_sent_end:
            sentences.append(current)
            current = []
    if current:
        sentences.append(current)
    return sentences



def _emit_bibl_content(container, tokens: list):
    """Emite tokens con detección bibl/legal SIN añadir <hi> envolvente."""
    grouped = group_legal_tokens(group_bibl_tokens(tokens))
    for tok in grouped:
        if tok["kind"] == "hi_bibl":
            for group in tok["groups"]:
                if group["kind"] == "bibl":
                    bibl = etree.SubElement(container, f"{{{TEI_NS}}}bibl")
                    for t in group["toks"]:
                        emit_token(bibl, t)
                else:
                    for t in group["toks"]:
                        emit_token(container, t)
        elif tok["kind"] == "legal_bibl":
            bibl = etree.SubElement(container, f"{{{TEI_NS}}}bibl")
            bibl.set("type", "legal")
            for t in tok["toks"]:
                emit_token(bibl, t)
        else:
            emit_token(container, tok)


def _join_split_words_6(raw6: list) -> list:
    """
    Llama a join_split_words con 5-tuplas y asigna italic a cada token
    resultante consumiendo una cola ordenada de (text, italic) extraída
    de raw6. Esto es más robusto que el mapeo por índice cuando
    join_split_words fusiona tokens (soft-hyphen) o los reordena.
    """
    from collections import deque

    # Cola de (text, italic) en el orden en que aparecen en raw6
    # (excluyendo sol que no produce tokens en el output)
    queue = deque()
    for tok in raw6:
        ttype = tok[0]
        if ttype == "sol":
            continue
        ttext  = tok[1]
        italic = tok[5] if len(tok) > 5 else False
        queue.append((ttext, italic))

    def _pop_italic(text: str) -> bool:
        """Consume la cola hasta encontrar `text` y devuelve su italic."""
        for _ in range(len(queue)):
            t, i = queue.popleft()
            if t == text:
                return i
            queue.append((t, i))   # no coincide → vuelve al final
        return False               # fallback

    raw5   = [t[:5] for t in raw6]
    tokens = join_split_words(raw5)

    for tok in tokens:
        kind = tok["kind"]
        if kind == "sol":
            tok["italic"] = False
        elif kind == "word_lb":
            # Italic del fragmento izquierdo (pre-guión)
            tok["italic"] = _pop_italic(tok.get("left", ""))
            # Consumir también el fragmento derecho
            _pop_italic(tok.get("right", ""))
        else:
            tok["italic"] = _pop_italic(tok.get("text", ""))

    return tokens


def _emit_sentence_spans(s_el, all_raw6: list):
    """
    Emite una oración abriendo/cerrando <hi rend="italic"> cuando cambia
    el italic entre tokens consecutivos. Acepta lista plana de 6-tuplas.
    """
    from itertools import groupby
    tokens = _join_split_words_6(all_raw6)
    if not any(t["kind"] in ("word","word_lb","amp","pc","dot","abbrev_dot")
               for t in tokens):
        return

    for is_italic, grp in groupby(tokens, key=lambda t: t.get("italic", False)):
        grp = list(grp)
        # sol/lb sin contenido: siempre al nivel de s_el
        if not any(t["kind"] in ("word","word_lb","amp","pc","dot","abbrev_dot")
                   for t in grp):
            for tok in grp:
                emit_token(s_el, tok)
            continue
        container = s_el
        if is_italic:
            container = etree.SubElement(s_el, f"{{{TEI_NS}}}hi")
            container.set("rend", "italic")
        _emit_bibl_content(container, grp)


def _emit_sentences(parent, sentence_list: list):
    """Emite oraciones como <s>, respetando italic por token."""
    for span_raws in sentence_list:
        all_raw6 = []
        for raw in span_raws:
            all_raw6.extend(raw)
        if not any(t[0] in ("word","abbrev_dot","amp","pc","dot")
                   for t in all_raw6):
            continue
        s_el = etree.SubElement(parent, f"{{{TEI_NS}}}s")
        _emit_sentence_spans(s_el, all_raw6)


def _emit_para_block(parent, para_lines: list, join_left: str = None,
                     is_first_block: bool = False):
    """
    Agrupa líneas en párrafos por sangría y emite <p><s>...</s></p>.
    El italic se rastrea por posición exacta de carácter en la línea,
    resolviendo correctamente soft hyphens que cruzan fronteras italic.
    """
    INDENT_THRESHOLD = 60
    paragraphs, current = [], []
    for i, line in enumerate(para_lines):
        if not line["text"].strip():
            continue
        last_has_hyphen = bool(current and current[-1]["soft_hyphen"])
        if i > 0 and line["first_x"] > INDENT_THRESHOLD and current and not last_has_hyphen:
            paragraphs.append(current)
            current = []
        current.append(line)
    if current:
        paragraphs.append(current)

    for pi, para in enumerate(paragraphs):
        p_el      = etree.SubElement(parent, f"{{{TEI_NS}}}p")
        spans     = _flatten_spans(para)
        sentences = _group_spans_into_sentences(spans)

        # join_left: fusionar fragmento de columna anterior con primer token
        if join_left and is_first_block and pi == 0 and sentences:
            first_raws = sentences[0]
            all6 = [t for raw in first_raws for t in raw]
            toks = _join_split_words_6(all6)
            for idx, tok in enumerate(toks):
                if tok["kind"] == "word":
                    toks[idx] = {
                        "kind":      "word_lb",
                        "left":      join_left,
                        "right":     tok["text"],
                        "expansion": tok.get("expansion"),
                        "eol":       tok.get("eol", False),
                        "lb_n":      None,
                        "italic":    tok.get("italic", False),
                    }
                    break
            if any(t["kind"] in ("word","word_lb","amp","pc","dot","abbrev_dot")
                   for t in toks):
                from itertools import groupby
                s_el = etree.SubElement(p_el, f"{{{TEI_NS}}}s")
                for is_ital, grp in groupby(toks, key=lambda t: t.get("italic", False)):
                    grp = list(grp)
                    cont = s_el
                    if is_ital:
                        cont = etree.SubElement(s_el, f"{{{TEI_NS}}}hi")
                        cont.set("rend", "italic")
                    _emit_bibl_content(cont, grp)
            _emit_sentences(p_el, sentences[1:])
        else:
            _emit_sentences(p_el, sentences)

        # Si es el último párrafo y su última línea termina en ¬ (palabra
        # cortada que continúa en la columna siguiente), añadir
        # <lb break="no"/> dentro del último <w> del último <s>.
        # Esto se hace directamente sobre el árbol para evitar que el token
        # pase por join_split_words / group_bibl_tokens (que no lo conocen).
        if pi == len(paragraphs) - 1 and para and para[-1]["soft_hyphen"]:
            all_s = p_el.findall(f"{{{TEI_NS}}}s")
            if all_s:
                all_w = all_s[-1].findall(f".//{{{TEI_NS}}}w")
                if all_w:
                    lb = etree.SubElement(all_w[-1], f"{{{TEI_NS}}}lb")
                    lb.set("break", "no")







def _emit_head(parent, lines: list, head_type: str = None):
    """
    Emite líneas de heading como <head> o <head type="sub">.
    Cada TextLine genera su propio <lb n="X"> al nivel del <head>,
    seguido de los tokens (envueltos en <hi rend="italic"> si procede).
    """
    attrib = {"type": head_type} if head_type else {}
    head_el = etree.SubElement(parent, f"{{{TEI_NS}}}head", attrib)

    for line in lines:
        if not line["text"].strip():
            continue

        # <lb n="X"> al nivel del head (siempre, incluida la primera línea)
        lb = etree.SubElement(head_el, f"{{{TEI_NS}}}lb")
        lb.set("n", str(line["line_n"]))

        # ¿Toda la línea (o casi) es itálica?
        # Usamos 80% para tolerar que el span no incluya puntuación final
        italic_spans = line.get("italic_spans", [])
        line_len     = len(line["text"].rstrip())
        full_italic  = any(
            s["offset"] == 0 and s["length"] >= line_len * 0.8
            for s in italic_spans
        )
        if full_italic:
            container = etree.SubElement(head_el, f"{{{TEI_NS}}}hi")
            container.set("rend", "italic")
        else:
            container = head_el

        # Tokens de esta línea (sin lb inter-línea — ya lo pusimos arriba)
        segments = apply_abbrev_tags(line["text"], line["abbrevs"])
        raw = []
        for seg in segments:
            exp = seg["expansion"] if seg["is_abbrev"] else None
            for ttype, ttext in tokenize(seg["text"]):
                tok_exp = exp if (ttype == "word" and seg["is_abbrev"]) else None
                raw.append((ttype, ttext, tok_exp, False, False))
        for tok in join_split_words(raw):
            emit_token(container, tok)


def _trim_line_by_offset(line: dict, start_offset: int) -> dict:
    """
    Devuelve una copia del line con text e abbrevs recortados desde start_offset.
    Ajusta los offsets de abbrevs al nuevo origen.
    """
    raw      = line["text"][start_offset:]
    stripped = raw.lstrip()
    actual   = start_offset + (len(raw) - len(stripped))
    new_abbrevs = [
        {**a, "offset": a["offset"] - actual}
        for a in line.get("abbrevs", [])
        if a["offset"] >= actual
    ]
    return {**line, "text": stripped, "abbrevs": new_abbrevs}


def _wrap_italic_spans(parent, lines: list, emit_fn):
    """
    Emite tokens agrupando los que caen dentro de italic_spans de cada línea
    en <hi rend="italic">. Llama a emit_fn(container, tok) para cada token.

    Estrategia simplificada: si TODAS las líneas del bloque tienen italic_spans
    que cubren el texto completo, envuelve todo en un único <hi rend="italic">.
    En caso contrario emite sin envolver (el italic vendrá del TEI de origen).
    """
    all_full_italic = all(
        any(s["offset"] == 0 and s["length"] >= len(l["text"].rstrip()) * 0.8
            for s in l.get("italic_spans", []))
        for l in lines if l["text"].strip()
    )
    if all_full_italic:
        hi = etree.SubElement(parent, f"{{{TEI_NS}}}hi")
        hi.set("rend", "italic")
        container = hi
    else:
        container = parent

    raw = _flatten_lines_to_raw_tokens(lines, [False])
    tokens = join_split_words(raw)
    for tok in tokens:
        emit_fn(container, tok)


def _emit_summarium(parent, lines: list):
    """
    Emite el bloque summarium como:
      <div type="summarium"><list>
        <item n="21"><label>21</label><s>...</s></item>
        <item><s>...</s></item>
        ...
      </list></div>

    Agrupa líneas en items usando:
      - index_entry_spans → inicio de item numerado
      - sentence_spans sin continued → fin de item
    """
    div_sum = etree.SubElement(parent, f"{{{TEI_NS}}}div", {"type": "summarium"})
    lst     = etree.SubElement(div_sum, f"{{{TEI_NS}}}list")

    # ── Agrupar líneas en items ───────────────────────────────────────────────
    # Nuevo item cuando:
    #   - la línea tiene index_entry_spans (entrada numerada), o
    #   - el primer sentence_span de la línea NO tiene continued:true
    #     (lo que indica que esta línea inicia una nueva oración, no continúa la anterior)
    item_groups: list = []
    current:     list = []

    for line in lines:
        if not line["text"].strip():
            continue
        has_label = bool(line.get("index_entry_spans"))
        sents     = line.get("sentence_spans", [])
        # Si el primer span no tiene continued → esta línea inicia oración nueva
        first_sent_is_new = sents and not sents[0]["continued"]

        starts_new = has_label or (bool(current) and first_sent_is_new)

        if starts_new and current:
            item_groups.append(current)
            current = []

        current.append(line)

    if current:
        item_groups.append(current)

    # ── Emitir cada item ──────────────────────────────────────────────────────
    for item_lines in item_groups:
        item_el = etree.SubElement(lst, f"{{{TEI_NS}}}item")

        first_line = item_lines[0]
        idx_spans  = first_line.get("index_entry_spans", [])
        content_lines = list(item_lines)

        if idx_spans:
            span       = idx_spans[0]
            label_text = first_line["text"][span["offset"]: span["offset"] + span["length"]]
            item_el.set("n", label_text.strip())
            lbl = etree.SubElement(item_el, f"{{{TEI_NS}}}label")
            lbl.text = label_text.strip()
            # Recortar la primera línea para excluir el número ya emitido en <label>
            content_lines[0] = _trim_line_by_offset(first_line,
                                                     span["offset"] + span["length"])

        # Emitir contenido del item respetando italic_spans
        s_el = etree.SubElement(item_el, f"{{{TEI_NS}}}s")
        _wrap_italic_spans(s_el, content_lines, emit_token)


def lines_to_tei(lines: list, page_n: int, join_left: str = None) -> etree._Element:
    div = etree.Element(
        f"{{{TEI_NS}}}div",
        attrib={"type": "page", "n": str(page_n)},
        nsmap={None: TEI_NS, "xi": XI_NS}
    )

    # ── Agrupar líneas por structure_type consecutivo ─────────────────────────
    struct_blocks: list = []   # [(struct_type, [lines])]
    for line in lines:
        if not line["text"].strip():
            continue
        st = line.get("structure_type")
        if struct_blocks and struct_blocks[-1][0] == st:
            struct_blocks[-1][1].append(line)
        else:
            struct_blocks.append([st, [line]])

    # ── Emitir cada bloque según su tipo ──────────────────────────────────────
    first_para = True
    for struct_type, block_lines in struct_blocks:
        if struct_type in ("heading", "header"):
            _emit_head(div, block_lines)
        elif struct_type == "subheading":
            _emit_head(div, block_lines, head_type="sub")
        elif struct_type == "summarium":
            _emit_summarium(div, block_lines)
        else:
            # paragraph o None → lógica original con sangría
            _emit_para_block(div, block_lines,
                             join_left=join_left,
                             is_first_block=first_para)
            first_para = False

    return div



def build_clean_txt(lines: list) -> str:
    out = []
    prev_region = None
    for line in lines:
        if prev_region and line["region_id"] != prev_region:
            out.append("")
        prev_region = line["region_id"]
        suffix = "¬" if line["soft_hyphen"] else ""
        out.append(line["text"] + suffix)
    return "\n".join(out)


