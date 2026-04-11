#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
onate_bibl.py
─────────────
Agrupación de tokens en bloques bibliográficos (<hi><bibl>).
Importa de onate_tokens.
"""

from onate_tokens import (
    AUTHOR_ABBREVS, AUTHOR_FULL_NAMES,
    BIBL_INTRA, BIBL_INTER, BIBL_INTER_2, HONORIFIC_PREFIXES, TEI_NS,
)

# Abreviaturas tras las cuales el siguiente token siempre pertenece al bibl,
# independientemente de si está en mayúscula o en BIBL_INTRA.
# Ej: verb. venditio, verb. pretium, verb. emptio
BIBL_EXPECT_NEXT = {"verb.", "verbo"}

# ── Construcción del árbol completo ──────────────────────────────────────────

def join_split_words(para_tokens: list) -> list:
    """
    Une pares de tokens adyacentes que forman una palabra partida por ¬.
    La unión ocurre cuando token[i] tiene split=True y token[i+1] es "word".

    Tokens de entrada: (ttype, ttext, expansion, eol, split)
    Tokens de salida normalizados a dicts:
      {"kind": ..., "text"|"left"+"right": ..., "expansion": ..., "eol": bool}
    """
    result = []
    i = 0
    while i < len(para_tokens):
        ttype, ttext, expansion, eol, split = para_tokens[i]
        if ttype == "sol":
            result.append({"kind": "sol", "text": ttext, "expansion": None, "eol": False})
            i += 1
            continue
        if (split
                and ttype == "word"
                and i + 1 < len(para_tokens)
                and para_tokens[i + 1][0] == "word"):
            r_type, r_text, r_exp, r_eol, r_split = para_tokens[i + 1]
            if expansion and r_exp:
                combined = expansion + r_exp
            elif expansion:
                combined = expansion + r_text
            elif r_exp:
                combined = ttext + r_exp
            else:
                combined = None
            result.append({
                "kind": "word_lb",
                "left": ttext, "right": r_text,
                "expansion": combined, "eol": r_eol,
                "lb_n": split,
            })
            i += 2
        else:
            result.append({
                "kind": ttype, "text": ttext,
                "expansion": expansion, "eol": eol,
            })
            i += 1
    return result



def is_bibl_token(tok: dict) -> bool:
    """Devuelve True si el token mantiene el bloque <hi> abierto."""
    kind = tok["kind"]
    text = tok.get("text", "")
    if kind == "abbrev_dot":
        return True
    if kind in ("pc", "dot"):
        return True
    if kind == "amp":
        return True
    if kind in ("sol", "lb"):
        return True
    if kind == "word":
        if text in BIBL_INTRA or text in BIBL_INTER:
            return True
        if text.isdigit():
            return True
        # Nombres de autor completos (AUTHOR_FULL_NAMES) NO son intra-bibl:
        # cierran el bibl actual y abren uno nuevo vía is_author_token.
        from onate_tokens import AUTHOR_FULL_NAMES
        if text and text[0].isupper() and text not in AUTHOR_FULL_NAMES:
            return True
    return False


def is_intra_bibl_token(tok: dict) -> bool:
    """Devuelve True si el token va DENTRO de un <bibl>."""
    kind = tok["kind"]
    text = tok.get("text", "")
    if kind == "abbrev_dot" and text not in AUTHOR_ABBREVS:
        return True
    if kind == "word" and text in BIBL_INTRA:
        return True
    if kind in ("pc", "dot"):
        return True
    if kind == "word" and text.isdigit():
        return True
    return False


def is_inter_bibl_token(tok: dict, next_tok: dict = None) -> bool:
    """Devuelve True si el token va ENTRE <bibl> dentro del <hi>.
    Cubre tokens simples (ibi) y el primer token de secuencias de dos
    palabras definidas en BIBL_INTER_2 (p.ej. ex parte).
    """
    kind = tok["kind"]
    text = tok.get("text", "")
    if kind == "word" and text in BIBL_INTER:
        return True
    # Secuencia de dos tokens (ex parte, etc.)
    if kind == "word" and next_tok is not None:
        next_text = next_tok.get("text", "")
        if (text, next_text) in BIBL_INTER_2:
            return True
    if kind == "amp":
        if next_tok is not None:
            nt = next_tok.get("text", "")
            if is_author_token(next_tok) or nt in BIBL_INTER:
                return True
        return False
    return False


def is_author_token(tok: dict) -> bool:
    """Devuelve True si el token es nombre de autor (inicio de <bibl>).
    Cubre abbrev_dot (Salon.), word (Bannes) y word_lb (A<lb/>ragon).
    """
    if tok["kind"] == "abbrev_dot" and tok["text"] in AUTHOR_ABBREVS:
        return True
    # Nombre completo sin abreviar
    full = tok.get("text", "") if tok["kind"] == "word" \
        else tok.get("left", "") + tok.get("right", "")
    if tok["kind"] in ("word", "word_lb") and full in AUTHOR_FULL_NAMES:
        return True
    return False


def group_bibl_tokens(tokens: list) -> list:
    """
    Agrupa tokens en bloques hi_bibl:
      {"kind": "hi_bibl", "groups": [
          {"kind": "bibl", "toks": [...]},
          {"kind": "inter", "toks": [...]},
          ...
      ]}
    """
    result = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if is_author_token(tok):
            groups = []
            current_bibl = [tok]
            i += 1
            pending_inter = []

            while i < len(tokens):
                t = tokens[i]
                next_t = tokens[i+1] if i+1 < len(tokens) else None
                if t["kind"] in ("sol", "lb"):
                    current_bibl.append(t)
                    i += 1
                    continue
                # No romper el bibl si el último token es un prefijo
                # honorífico (D., S., B.…): "D. Th." es un único autor.
                prev_is_honorific = bool(
                    current_bibl
                    and current_bibl[-1].get("text") in HONORIFIC_PREFIXES
                )
                # El token anterior era verb./verbo → el siguiente es el lema,
                # siempre pertenece al bibl (p.ej. verb. venditio)
                prev_expects_next = bool(
                    current_bibl
                    and current_bibl[-1].get("text") in BIBL_EXPECT_NEXT
                )
                if is_author_token(t) and not prev_is_honorific and not prev_expects_next:
                    if current_bibl:
                        groups.append({"kind": "bibl", "toks": current_bibl})
                    if pending_inter:
                        groups.append({"kind": "inter", "toks": pending_inter})
                    current_bibl = [t]
                    pending_inter = []
                    i += 1
                elif is_inter_bibl_token(t, next_t) and not prev_expects_next:
                    pending_inter.append(t)
                    i += 1
                    # Si es inicio de secuencia de dos tokens (ex parte),
                    # consumir también el segundo token
                    if (next_t is not None
                            and t.get("kind") == "word"
                            and next_t.get("kind") == "word"
                            and (t.get("text",""), next_t.get("text","")) in BIBL_INTER_2):
                        pending_inter.append(tokens[i])
                        i += 1
                elif is_bibl_token(t) or prev_expects_next:
                    current_bibl.extend(pending_inter)
                    pending_inter = []
                    current_bibl.append(t)
                    i += 1
                else:
                    break

            if current_bibl:
                groups.append({"kind": "bibl", "toks": current_bibl})
            if pending_inter:
                groups.append({"kind": "inter", "toks": pending_inter})
            if groups:
                # Post-proceso: si el último token de un bibl es & (amp),
                # moverlo al inicio del inter siguiente para que quede
                # dentro del mismo <hi> junto a ibi/ex parte.
                for idx in range(len(groups) - 1):
                    g = groups[idx]
                    gnext = groups[idx + 1]
                    if (g["kind"] == "bibl"
                            and g["toks"]
                            and g["toks"][-1].get("kind") == "amp"
                            and gnext["kind"] == "inter"):
                        amp_tok = g["toks"].pop()
                        gnext["toks"].insert(0, amp_tok)
                result.append({"kind": "hi_bibl", "groups": groups})
        else:
            result.append(tok)
            i += 1
    return result



# ── Detección de citas jurídicas (derecho romano / canónico) ──────────────────
#
# Trabaja sobre token dicts (mismo nivel que group_bibl_tokens).
# El resultado es un token {"kind": "legal_bibl", "toks": [...]}
# que onate_tei.py emite como <bibl type="legal"> directamente en <s>.

# Palabras que cierran claramente la cita (prosa argumental)
LEGAL_PROSE_CLEAR = {
    "ergo", "Probatur", "Secundo", "Tertio", "Quarto", "Primo",
    "intelligi", "obtinet", "debet", "potest", "quia", "sed",
}

# abbrev_dot que son fuentes jurídicas
# abbrev_dot que son fuentes o títulos jurídicos (van dentro del bibl)
LEGAL_SOURCE_ABBREVS = {
    "ff.", "C.", "D.", "Inst.", "Nov.", "X.",   # fuentes
    "mand.", "mandata.", "Trebel.", "Falcid.",  # títulos CIC
    "Aquil.", "Falc.", "glos.", "fin.", "ma.",  # otros títulos
}

# Textos de <w> reconocidos como títulos jurídicos
LEGAL_TITLES = {
    "Trebel", "Falcid", "mand", "ma", "Aquil", "loc", "commod",
    "deposit", "pign", "stipul", "verb", "oblig", "iur", "fin",
    "glos", "empti", "vend", "conduct", "locat", "societ",
    "tutel", "curator", "fideicomm",
}


def _is_legal_initiator_tok(tok: dict, next_tok: dict = None) -> bool:
    """True si tok inicia una cita jurídica.

    Reconoce:
      l.   → abbrev_dot con text "l."
      reg. → abbrev_dot con text "reg." seguido de word "iuris"
    """
    if tok["kind"] != "abbrev_dot":
        return False
    if tok["text"] == "l.":
        return True
    if tok["text"] == "reg.":
        return next_tok is not None and next_tok.get("text") == "iuris"
    return False


def _collect_legal_toks(tokens: list, i: int) -> tuple:
    """
    Recolecta todos los tokens de una cita jurídica a partir de la posición i.
    Devuelve (lista_tokens, nueva_i).

    Flags:
      in_initiator   — consumiendo el token iniciador (l. o reg.)
      seen_source    — ya se vio ff./C./D. → palabras desconocidas paran
      expect_incipit — siguiente word/abbrev es incipit (siempre aceptar)
      after_prep     — último token fue ad/in/ibi → l. siguiente es localizador,
                       no nuevo iniciador (p.ej. "ff. ad l. Falcid.")
    """
    toks = []
    in_initiator   = True
    seen_source    = False
    expect_incipit = False
    after_prep     = False   # último token fue preposición intra

    while i < len(tokens):
        tok  = tokens[i]
        kind = tok["kind"]
        text = tok.get("text", "")

        # Saltos de línea siempre intra
        if kind in ("sol", "lb"):
            toks.append(tok); i += 1; continue

        # ── Fase iniciador ────────────────────────────────────────────────────
        if in_initiator:
            toks.append(tok); i += 1
            if kind == "abbrev_dot" and text == "l.":
                in_initiator = False; expect_incipit = True
            elif kind == "abbrev_dot" and text == "reg.":
                if i < len(tokens) and tokens[i].get("text") == "iuris":
                    toks.append(tokens[i]); i += 1
                in_initiator = False; expect_incipit = False
            continue

        # ── & siempre cierra ──────────────────────────────────────────────────
        if kind == "amp":
            break

        # ── Coma cierra ───────────────────────────────────────────────────────
        if kind == "pc" and text == ",":
            break

        # ── Punto siempre intra ───────────────────────────────────────────────
        if kind in ("pc", "dot") and text == ".":
            after_prep = False
            toks.append(tok); i += 1; continue

        # ── abbrev_dot ────────────────────────────────────────────────────────
        if kind == "abbrev_dot":
            # l. después de preposición (ad l. Falcid.) → localizador, no iniciador
            if text == "l." and after_prep:
                after_prep = False
                toks.append(tok); i += 1; continue
            if text in LEGAL_SOURCE_ABBREVS:
                seen_source    = True
                expect_incipit = False
                after_prep     = False
                toks.append(tok); i += 1; continue
            if text == "§.":
                expect_incipit = True
                after_prep     = False
                toks.append(tok); i += 1; continue
            if expect_incipit:
                toks.append(tok); i += 1
                expect_incipit = False; after_prep = False; continue
            break

        # ── word ──────────────────────────────────────────────────────────────
        if kind == "word":
            if text in LEGAL_PROSE_CLEAR:
                break
            if expect_incipit:
                toks.append(tok); i += 1
                expect_incipit = False; after_prep = False; continue
            if text.isdigit():
                after_prep = False
                toks.append(tok); i += 1; continue
            if text in ("ad", "in", "ibi"):
                after_prep = True
                toks.append(tok); i += 1; continue
            if text in LEGAL_TITLES:
                after_prep = False
                toks.append(tok); i += 1; continue
            if not seen_source:
                after_prep = False
                toks.append(tok); i += 1; continue
            break

        # ── word_lb ───────────────────────────────────────────────────────────
        if kind == "word_lb":
            full = tok.get("left", "") + tok.get("right", "")
            if expect_incipit or not seen_source:
                toks.append(tok); i += 1
                expect_incipit = False; after_prep = False; continue
            if full.isdigit() or full in LEGAL_TITLES:
                after_prep = False
                toks.append(tok); i += 1; continue
            break

        break

    # Eliminar preposiciones colgantes al final
    while (toks
           and toks[-1]["kind"] == "word"
           and toks[-1].get("text") in ("ad", "in", "ibi")):
        i -= 1; toks.pop()

    return toks, i


def group_legal_tokens(tokens: list) -> list:
    """
    Recorre una lista plana de token dicts y envuelve las citas jurídicas en
      {"kind": "legal_bibl", "toks": [...]}

    Actúa sobre tokens que NO son ya hi_bibl (escolásticos).
    Llamar después de group_bibl_tokens.
    """
    result = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]

        # Tokens ya agrupados → pasar tal cual
        if tok.get("kind") in ("hi_bibl", "legal_bibl"):
            result.append(tok); i += 1; continue

        next_tok = tokens[i + 1] if i + 1 < len(tokens) else None
        if _is_legal_initiator_tok(tok, next_tok):
            legal_toks, i = _collect_legal_toks(tokens, i)
            if legal_toks:
                result.append({"kind": "legal_bibl", "toks": legal_toks})
        else:
            result.append(tok); i += 1

    return result
