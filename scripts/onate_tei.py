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
    _apply_long_s_roots, apply_abbrev_tags, tokenize,
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
    long_s_orig = None
    if not reg and not is_abbrev:
        key = text.lower()
        if key in LONG_S:
            orig_form = LONG_S[key]
            # Preservar mayúscula inicial si la tiene
            if text and text.isupper():
                orig_form = orig_form.upper()
            elif text and text[0].isupper():
                orig_form = orig_form[0].upper() + orig_form[1:]
            if orig_form != text:
                long_s_orig = orig_form
        else:
            long_s_orig = _apply_long_s_roots(text)

    # Detección automática ae→æ y ę→ae (solo si no hay ya un choice)
    ae_orig = None
    ae_reg  = None
    if not reg and not long_s_orig and not is_abbrev:
        if "ae" in text:
            ae_orig = text.replace("ae", "æ")
            if ae_orig == text:
                ae_orig = None
        elif "ę" in text or "Ę" in text:
            ae_reg  = text.replace("ę", "ae").replace("Ę", "Ae")
            if ae_reg == text:
                ae_orig = ae_reg = None
            else:
                ls = LONG_S.get(ae_reg) or LONG_S.get(ae_reg.lower()) or _apply_long_s_roots(ae_reg) or ae_reg
                ae_orig = ls.replace("ae", "ę").replace("æ", "ę").replace("Ae", "Ę").replace("Æ", "Ę")

    if is_abbrev and expansion:
        tag_type = classify_tag(text, expansion)

        choice = etree.SubElement(parent, f"{{{TEI_NS}}}choice")
        if tag_type == "abbr":
            inner  = etree.SubElement(choice, f"{{{TEI_NS}}}abbr")
            w      = etree.SubElement(inner,  f"{{{TEI_NS}}}w")
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
    elif long_s_orig:
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
        w_reg.text = ae_reg if ae_reg else text
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
            w_exp.text = macron_exp.replace("ſ", "s")
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
    if full and full.isupper():
        orig_full = orig_full.upper()
    elif full and full[0].isupper():
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
        ls_full = long_s_left + long_s_right
        macron_exp = _expand_macrons(ls_full) if any(c in ls_full for c in MACRON_MAP) else None
        if macron_exp and macron_exp != ls_full:
            outer  = etree.SubElement(parent, f"{{{TEI_NS}}}choice")
            abbr   = etree.SubElement(outer,  f"{{{TEI_NS}}}abbr")
            inner  = etree.SubElement(abbr,   f"{{{TEI_NS}}}choice")
            orig   = etree.SubElement(inner,  f"{{{TEI_NS}}}orig")
            _make_w_lb(orig, long_s_left, long_s_right)
            reg_el = etree.SubElement(inner,  f"{{{TEI_NS}}}reg")
            w_reg  = etree.SubElement(reg_el, f"{{{TEI_NS}}}w")
            w_reg.text = full_text
            expan  = etree.SubElement(outer,  f"{{{TEI_NS}}}expan")
            w_exp  = etree.SubElement(expan,  f"{{{TEI_NS}}}w")
            w_exp.text = macron_exp.replace("ſ", "s")
        else:
            choice = etree.SubElement(parent, f"{{{TEI_NS}}}choice")
            orig   = etree.SubElement(choice, f"{{{TEI_NS}}}orig")
            _make_w_lb(orig, long_s_left, long_s_right)
            reg_el = etree.SubElement(choice, f"{{{TEI_NS}}}reg")
            w_reg  = etree.SubElement(reg_el, f"{{{TEI_NS}}}w")
            w_reg.text = full_text
    elif any(c in full_text for c in MACRON_MAP):
        macron_exp = _expand_macrons(full_text)
        if macron_exp and macron_exp != full_text:
            ls_exp = _apply_long_s_roots(macron_exp) or macron_exp
            macron_reverse = {v: k for k, v in MACRON_MAP.items()}
            orig_ls = ls_exp
            for letters, macron_char in sorted(macron_reverse.items(), key=lambda x: -len(x[0])):
                orig_ls = orig_ls.replace(letters, macron_char, 1)
            w_left  = orig_ls[:len(left)]
            w_right = orig_ls[len(left):]
            choice = etree.SubElement(parent, f"{{{TEI_NS}}}choice")
            abbr   = etree.SubElement(choice, f"{{{TEI_NS}}}abbr")
            _make_w_lb(abbr, w_left, w_right)
            expan  = etree.SubElement(choice, f"{{{TEI_NS}}}expan")
            w_exp  = etree.SubElement(expan,  f"{{{TEI_NS}}}w")
            w_exp.text = macron_exp.replace("ſ", "s")
        else:
            _make_w_lb(parent, left, right)
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
    """Emite <bibl type="legal"> para una cita jurídica."""
    bibl = etree.SubElement(parent, f"{{{TEI_NS}}}bibl")
    bibl.set("type", "legal")
    for tok in legal_tok["toks"]:
        emit_token(bibl, tok)


def emit_hi_bibl(parent, hi_tok: dict):
    """Emite bloques bibliográficos como <bibl> directo al padre.
    La itálica viene exclusivamente de las marcas *…* del staging.
    """
    groups = hi_tok["groups"]
    if not groups:
        return
    for group in groups:
        if group["kind"] == "bibl":
            bibl = etree.SubElement(parent, f"{{{TEI_NS}}}bibl")
            for tok in group["toks"]:
                emit_token(bibl, tok)
        else:
            for tok in group["toks"]:
                emit_token(parent, tok)


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
        choice = etree.SubElement(parent, f"{{{TEI_NS}}}choice")
        abbr   = etree.SubElement(choice, f"{{{TEI_NS}}}abbr")
        w      = etree.SubElement(abbr,   f"{{{TEI_NS}}}w")
        w.text = tok["text"]
        expan  = etree.SubElement(choice, f"{{{TEI_NS}}}expan")
        w_exp  = etree.SubElement(expan,  f"{{{TEI_NS}}}w")
        w_exp.text = ABBREV_EXPAN.get(tok["text"], ABBREV_EXPAN.get(tok["text"].lower(), ""))
    elif kind == "sic":
        choice  = etree.SubElement(parent, f"{{{TEI_NS}}}choice")
        sic_el  = etree.SubElement(choice, f"{{{TEI_NS}}}sic")
        w_sic   = etree.SubElement(sic_el, f"{{{TEI_NS}}}w")
        w_sic.text = tok["text"]
        corr_el = etree.SubElement(choice, f"{{{TEI_NS}}}corr")
        corr_el.text = tok.get("expansion") or ""
    elif kind == "sic_lb":
        # Palabra errónea cortada con guion: <choice><sic><w>left</w></sic><corr/></choice><lb break="no"/><w>right</w>
        choice  = etree.SubElement(parent, f"{{{TEI_NS}}}choice")
        sic_el  = etree.SubElement(choice, f"{{{TEI_NS}}}sic")
        w_sic   = etree.SubElement(sic_el, f"{{{TEI_NS}}}w")
        w_sic.text = tok["left"]
        corr_el = etree.SubElement(choice, f"{{{TEI_NS}}}corr")
        corr_el.text = tok.get("expansion") or ""
        lb = etree.SubElement(parent, f"{{{TEI_NS}}}lb")
        lb.set("break", "no")
        if tok.get("lb_n"):
            lb.set("n", str(tok["lb_n"]))
        add_w(parent, tok["right"])
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
        segments = apply_abbrev_tags(line["text"], line["abbrevs"], line.get("sic_spans", []))
        line_toks = []
        if not first_lb_ref[0]:
            line_toks.append(("sol", str(line["line_n"]), None, False, False))
            first_lb_ref[0] = True
        for seg in segments:
            exp = seg["expansion"] if seg["is_abbrev"] else None
            is_sic = seg.get("is_sic", False)
            sic_corr = seg.get("corr", None)
            for ttype, ttext in tokenize(seg["text"]):
                if is_sic and ttype == "word":
                    line_toks.append(("sic", ttext, sic_corr, False, False))
                else:
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
    """True si offset cae dentro de algún italic_span con italic:True."""
    return any(s.get("italic", True) and
               s["offset"] <= offset < s["offset"] + s["length"]
               for s in italic_spans)


def _tokenize_with_italic(span_text: str, span_offset: int,
                           span_abbrevs: list, italic_spans: list,
                           sic_spans: list = None) -> list:
    """
    Tokeniza span_text y asigna italic por token según su posición real
    en la línea original (span_offset + posición dentro del span).
    Busca cada token en el texto para obtener su posición exacta,
    evitando desfases causados por espacios que tokenize() descarta.
    """
    toks = []
    segs = apply_abbrev_tags(span_text, span_abbrevs, sic_spans or [])
    search_from = 0  # posición de búsqueda dentro de span_text
    for seg in segs:
        exp = seg["expansion"] if seg["is_abbrev"] else None
        is_sic = seg.get("is_sic", False)
        sic_corr = seg.get("corr", None)
        for ttype, ttext in tokenize(seg["text"]):
            idx = span_text.find(ttext, search_from)
            if idx == -1:
                idx = search_from
            char_pos_in_line = span_offset + idx
            italic = _offset_is_italic(char_pos_in_line, italic_spans)
            if is_sic and ttype == "word":
                toks.append(("sic", ttext, sic_corr, False, False, italic))
            else:
                tok_exp = exp if (ttype == "word" and seg["is_abbrev"]) else None
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
            toks.extend(_tokenize_with_italic(text, 0, span_abbrevs, italic_spans, line.get("sic_spans", [])))
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
                span_sic = [
                    {**s, "offset": s["offset"] - span_offset}
                    for s in line.get("sic_spans", [])
                    if span_offset <= s["offset"] < span_offset + span["length"]
                ]
                toks.extend(_tokenize_with_italic(
                    span_text, span_offset, span_abbrevs, italic_spans, span_sic))

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
    if not any(t["kind"] in ("word","word_lb","amp","pc","dot","abbrev_dot","sic","sic_lb")
               for t in tokens):
        return

    for is_italic, grp in groupby(tokens, key=lambda t: t.get("italic", False)):
        grp = list(grp)
        if not any(t["kind"] in ("word","word_lb","amp","pc","dot","abbrev_dot","sic","sic_lb")
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
        # Nueva <p> por sangría (Transkribus) o por marca ¶ (staging)
        indent_break    = i > 0 and line["first_x"] > INDENT_THRESHOLD and not last_has_hyphen
        editorial_break = line.get("paragraph_break", False) and current
        if (indent_break or editorial_break) and current:
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
            if any(t["kind"] in ("word","word_lb","amp","pc","dot","abbrev_dot","sic","sic_lb")
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
    Procesa línea a línea pero fusiona palabras partidas con soft hyphen
    pasando el primer token de la línea siguiente cuando hay ¬.
    """
    attrib = {"type": head_type} if head_type else {}
    head_el = etree.SubElement(parent, f"{{{TEI_NS}}}head", attrib)

    # Pre-tokenizar todas las líneas
    line_raws = []
    for line in lines:
        if not line["text"].strip():
            line_raws.append([])
            continue
        segments = apply_abbrev_tags(line["text"], line["abbrevs"], line.get("sic_spans", []))
        raw = []
        for seg in segments:
            exp = seg["expansion"] if seg["is_abbrev"] else None
            for ttype, ttext in tokenize(seg["text"]):
                tok_exp = exp if (ttype == "word" and seg["is_abbrev"]) else None
                raw.append((ttype, ttext, tok_exp, False, False))
        line_raws.append(raw)

    skip_lb = set()  # line indices whose lb was already emitted via soft-hyphen
    for li, line in enumerate(lines):
        if not line["text"].strip():
            continue
        is_last = (li == len(lines) - 1)

        # <lb n="X"> — omitir si esta línea fue consumida por soft-hyphen anterior
        if li not in skip_lb:
            lb = etree.SubElement(head_el, f"{{{TEI_NS}}}lb")
            lb.set("n", str(line["line_n"]))

        # ¿Toda la línea es itálica?
        italic_spans = line.get("italic_spans", [])
        line_len     = len(line["text"].rstrip())
        full_italic  = any(
            s["offset"] == 0 and s["length"] >= line_len * 0.8
            for s in italic_spans
        )
        container = etree.SubElement(head_el, f"{{{TEI_NS}}}hi") if full_italic else head_el
        if full_italic:
            container.set("rend", "italic")

        raw = list(line_raws[li])
        if not raw:
            continue  # línea consumida por soft hyphen anterior

        if line["soft_hyphen"] and not is_last:
            # Añadir primer token de la línea siguiente para fusión
            next_raw = line_raws[li + 1]
            next_n   = lines[li + 1]["line_n"]
            if raw and next_raw:
                last = raw[-1]
                raw[-1] = (last[0], last[1], last[2], False, next_n)
                raw.append(next_raw[0])  # primer token de la siguiente línea
        
        for tok in join_split_words(raw):
            emit_token(container, tok)
        
        # Si hubo soft hyphen, la siguiente línea empieza desde el token 1
        if line["soft_hyphen"] and not is_last:
            line_raws[li + 1] = line_raws[li + 1][1:]
            skip_lb.add(li + 1)


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
    new_italic = [
        {**s, "offset": max(0, s["offset"] - actual),
         "length": s["length"] - max(0, actual - s["offset"])}
        for s in line.get("italic_spans", [])
        if s["offset"] + s["length"] > actual
    ]
    return {**line, "text": stripped, "abbrevs": new_abbrevs,
            "italic_spans": new_italic}


def _wrap_italic_spans(parent, lines: list, emit_fn):
    """
    Emite tokens sin envolver en <hi> automáticamente.
    La itálica viene exclusivamente de las marcas *…* del staging.
    """
    container = parent

    raw    = _flatten_lines_to_raw_tokens(lines, [False])
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


