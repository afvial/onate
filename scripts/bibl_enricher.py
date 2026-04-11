#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bibl_enricher.py
────────────────
Enriquece automáticamente los elementos <bibl> de archivos de página TEI
del proyecto Pedro de Oñate, De contractibus — Tractatus XXI.

Proceso en tres pasos para cada archivo:
  0. Detecta secuencias bibliográficas y las envuelve en <bibl>
     (integra onate_add_bibl.py; respeta <bibl> existentes salvo --force-bibl)
  1. Para cada <bibl> sin @corresp:
     a. Extrae la abreviatura del autor
     b. La busca en el catálogo WORKS
     c. Añade @corresp, @cert al <bibl>
     d. Añade <author ref="..."> envolviendo el nombre del autor
     e. Convierte <w>N</w> numéricos en <biblScope unit="?">
     f. Corrige <expan><w/></expan> vacíos
  2. Envuelve cada <bibl> en <cit xml:id="...">

Uso:
    python3 bibl_enricher.py <archivo_entrada.xml> [archivo_salida.xml]

    Si no se especifica salida, escribe <entrada>_bibl.xml

    python3 bibl_enricher.py --batch ./src/disp63/ ./bibl/disp63/
        Procesa todos los .xml de src/ → directorio de salida bibl/

Opciones:
    --dry-run      Muestra cambios sin escribir archivos
    --report       Genera informe de coincidencias y casos pendientes
    --force-bibl   Reconstruye <bibl> aunque ya existan
                   (útil tras edición manual del src/)

Ejemplos:
    python3 bibl_enricher.py pg_63_35_izq.xml
    python3 bibl_enricher.py pg_63_35_izq.xml pg_63_35_izq_bibl.xml
    python3 bibl_enricher.py --batch ./src/disp63/ ./bibl/disp63/
    python3 bibl_enricher.py pg_63_35_izq.xml --report --dry-run
    python3 bibl_enricher.py pg_63_35_izq.xml --force-bibl
"""

import sys
import re
import unicodedata
from pathlib import Path
from lxml import etree
from copy import deepcopy

XML_NS = "http://www.w3.org/XML/1998/namespace"

def xml_attr(local):
    return f"{{{XML_NS}}}{local}"

def column_from_filename(path: Path) -> str:
    """Extrae etiqueta única de columna+página del nombre del fichero.
    pg_63_35_izq_bibl.xml → 'p35_izq'
    pg_63_36_der_bibl.xml → 'p36_der'
    Garantiza xml:id únicos al ensamblar múltiples páginas.
    """
    stem  = path.stem.lower().replace('_bibl', '')
    parts = stem.split('_')

    col   = 'col'
    page  = ''

    for part in parts:
        if part in ('izq', 'der', 'left', 'right', 'a', 'b'):
            col = part
        elif part.isdigit() and len(part) >= 2:
            page = part   # toma el último número de 2+ cifras

    prefix = f"p{page}_" if page else ""
    return f"{prefix}{col}"

# ─────────────────────────────────────────────────────────────────────────────
# NAMESPACE
# ─────────────────────────────────────────────────────────────────────────────

NS  = "http://www.tei-c.org/ns/1.0"
NSM = {"t": NS}

def tag(local):
    return f"{{{NS}}}{local}"

# ─────────────────────────────────────────────────────────────────────────────
# CATÁLOGO DE AUTORIDADES
# Clave: fragmento de abreviatura (case-insensitive, sin puntuación)
# Valor: (bib_id, pers_id, cert)
# ─────────────────────────────────────────────────────────────────────────────

WORKS = {
    # Filosofía clásica
    "arist":      ("bib_Arist_Ethica",       "pers_Aristoteles",    "high"),
    # Patrística
    "aug":        ("bib_Aug_CivDei",         "pers_Augustinus",     "high"),
    # Teología escolástica medieval
    "dth":        ("bib_Aquinas_ST",         "pers_ThomasAquinas",  "high"),
    "caiet":      ("bib_Caietanus_ST",       "pers_Caietanus",      "high"),
    "bannes":     ("bib_Bannes_ST",          "pers_Bannes",         "high"),
    "aragon":     ("bib_Aragon_ST",          "pers_Aragon",         "high"),
    "salon":      ("bib_Salon_ST",           "pers_Salon",          "high"),
    # Jesuitas
    "valent":     ("bib_Valentia_Comm",      "pers_Valentia",       "high"),
    "molin":      ("bib_Molina_IurIure",     "pers_Molina",         "high"),
    "salas":      ("bib_Salas_Contr",        "pers_Salas",          "high"),
    "tolet":      ("bib_Toletus_Peccat",     "pers_Toletus",        "high"),
    "reginald":   ("bib_Reginald_Praxis",    "pers_Reginaldus",     "high"),
    "lessius":    ("bib_Lessius_IusIure",    "pers_Lessius",        "high"),
    "filliuc":    ("bib_Filliucci_QMor",     "pers_Filliucci",      "high"),
    "bonacin":    ("bib_Bonacina_Contr",     "pers_Bonacina",       "high"),
    "azor":       ("bib_Azor_InstMor",       "pers_Azor",           "high"),
    # Escuela de Salamanca
    "sotus":      ("bib_Soto_IusIure",       "pers_Soto",           "high"),
    "couar":      ("bib_Covarrubias_Var",    "pers_Covarrubias",    "high"),
    # Summistas / medievales tardíos
    "anton":      ("bib_Antoninus_Summa",    "pers_Antoninus",      "high"),
    "sylu":       ("bib_Sylvestrina",        "pers_Prierias",       "high"),
    "med":        ("bib_Medina_Restit",      "pers_Medina",         "high"),
    "medin":      ("bib_Medina_Restit",      "pers_Medina",         "high"),
    "conrad":     ("bib_Summenhart_Contr",   "pers_Summenhart",     "high"),
    "gabr":       ("bib_Biel_Sent",          "pers_Biel",           "high"),
    "manuel":     ("bib_Manuel_Sum",         "pers_Manuel",         "medium"),
    "faustus":    ("bib_Faustus_Empt",       "pers_Faustus_inc",    "low"),
    # Formas no abreviadas (nombre completo en <w>)
    "dth":        ("bib_Aquinas_ST",         "pers_ThomasAquinas",  "high"),
    "reginald":   ("bib_Reginald_Praxis",    "pers_Reginaldus",     "high"),
    "sotus":      ("bib_Soto_IusIure",       "pers_Soto",           "high"),
    "soto":       ("bib_Soto_IusIure",       "pers_Soto",           "high"),
    "lessius":    ("bib_Lessius_IusIure",    "pers_Lessius",        "high"),
    "summist":    ("bib_Sylvestrina",        "pers_Prierias",       "medium"),
    "summistae":  ("bib_Sylvestrina",        "pers_Prierias",       "medium"),
    "summistæ":   ("bib_Sylvestrina",        "pers_Prierias",       "medium"),
    "salon":      ("bib_Salon_ST",           "pers_Salon",          "high"),
    # Franciscanos / Nominalistas medievales
    "scot":       ("bib_Scotus_Sent",         "pers_Scotus",         "high"),
    "scotus":     ("bib_Scotus_Sent",         "pers_Scotus",         "high"),
    "mai":        ("bib_Maior_Sent",          "pers_Maior",          "high"),
    "maior":      ("bib_Maior_Sent",          "pers_Maior",          "high"),
    # Navarrus — dos obras distintas; se distingue por contexto
    # Si el bibl contiene "restit" → _Restit; si contiene "cap" + número alto → _Manual
    "nau":        ("bib_Navarrus_Manual",    "pers_Navarrus",       "high"),  # default
    "nauarr":     ("bib_Navarrus_Manual",    "pers_Navarrus",       "high"),  # default
    # Summistae (referencia genérica)
    "summist":    ("bib_Sylvestrina",        None,                  "medium"),
}

# Palabras clave dentro del <bibl> para desambiguar casos especiales
CONTEXT_RULES = [
    # (clave_autor, palabra_en_bibl, bib_id_resultado)
    ("nau",    "restit",    "bib_Navarrus_Restit"),
    ("nauarr", "restit",    "bib_Navarrus_Restit"),
    ("nau",    "restitut",  "bib_Navarrus_Restit"),
    ("nauarr", "restitut",  "bib_Navarrus_Restit"),
    ("aug",    "trinitat",  "bib_Aug_DeTrin"),
    ("aug",    "trin",      "bib_Aug_DeTrin"),
]

# Abreviaturas de unidades → atributo @unit en biblScope
UNIT_MAP = {
    "lib":      "book",
    "libro":    "book",
    "p":        "part",
    "pars":     "part",
    "parte":    "part",
    "cap":      "chap",
    "capit":    "chap",
    "q":        "quaestio",
    "quaest":   "quaestio",
    "ar":       "articulus",
    "art":      "articulus",
    "artic":    "articulus",
    "ad":       "ad",
    "d":        "dist",
    "dist":     "dist",
    "disp":     "disput",
    "disput":   "disput",
    "punct":    "punct",
    "tract":    "tract",
    "dub":      "dub",
    "dubium":   "dub",
    "tit":      "tit",
    "n":        "n",
    "nu":       "n",
    "num":      "n",
    "numero":   "n",
    "verb":     "lemma",
    "in":       "sent",    # In [I/II/III/IV] Sententiarum
}

# ─────────────────────────────────────────────────────────────────────────────
# UTILIDADES
# ─────────────────────────────────────────────────────────────────────────────

def normalize_key(text: str) -> str:
    """Elimina puntuación, diacríticos y pasa a minúsculas."""
    text = text.strip().lower()
    text = ''.join(c for c in unicodedata.normalize('NFD', text)
                   if unicodedata.category(c) != 'Mn')
    text = re.sub(r'[^a-z0-9]', '', text)
    return text


def get_text_content(elem) -> str:
    """Extrae todo el texto de un elemento y sus descendientes."""
    return ''.join(elem.itertext()).strip()


# Abreviaturas estructurales (no son nombres de autor)
STRUCTURAL_ABBRS = {
    'lib', 'libro', 'cap', 'capit', 'q', 'quaest', 'ar', 'art',
    'artic', 'n', 'nu', 'num', 'p', 'pars', 'd', 'dist', 'disp',
    'disput', 'punct', 'tract', 'dub', 'tit', 'verb', 'verbo',
    'iust', 'iustitia', 'contract', 'contractib', 'empt', 'emptione',
    'restit', 'restitut', 'sum', 'summa', 'controuerſ', 'controuers',
    'seqq', 'in', 'de', 'ad',
    # Divisiones internas de obra
    'sect', 'sectio', 'par', 'paragr', 'col', 'concl', 'prop',
    'coroll', 'obs', 'scholion', 'probl', 'theor', 'membr', 'membrum',
}


def get_author_candidates(bibl_elem) -> list:
    """
    Extrae candidatos a nombre de autor del <bibl>.
    Devuelve lista de textos en orden de prioridad.
    """
    candidates = []

    # 1. Pares de abbr consecutivos (p.ej. D. + Th. → D.Th.)
    abbrs = bibl_elem.findall(f".//{tag('abbr')}")
    abbr_texts = [get_text_content(a).rstrip('.') for a in abbrs]
    if len(abbr_texts) >= 2:
        combined = abbr_texts[0] + abbr_texts[1]
        candidates.append(combined)  # p.ej. "DTh"

    # 2. Primera abbr que no sea estructural
    for abbr in abbrs:
        txt = get_text_content(abbr).rstrip('.').lower()
        txt_norm = normalize_key(txt)
        if txt_norm not in STRUCTURAL_ABBRS:
            candidates.append(get_text_content(abbr))
            break

    # 3. Primer <w> hijo directo de <bibl> (nombres sin abreviar).
    #    Usa get_text_content() para reunir texto aunque la palabra esté
    #    partida por un <lb break="no"/> interno (p.ej. <w>Me<lb/>din</w>).
    for child in bibl_elem:
        if child.tag == tag('w'):
            txt = get_text_content(child)
            if txt and normalize_key(txt) not in STRUCTURAL_ABBRS:
                candidates.append(txt)
                break
        # también en <choice>/<orig> o <choice>/<reg>
        if child.tag == tag('choice'):
            for sub in child:
                if sub.tag in (tag('orig'), tag('reg'), tag('abbr')):
                    w = sub.find(tag('w'))
                    if w is not None:
                        txt = get_text_content(w)
                        if txt and normalize_key(txt) not in STRUCTURAL_ABBRS:
                            candidates.append(txt)
                            break

    # 4. Cualquier <w> descendiente con texto no numérico y no estructural.
    #    También usa get_text_content() para cubrir <lb break="no"/> internos.
    for w in bibl_elem.findall(f".//{tag('w')}"):
        txt = get_text_content(w)
        if txt and not txt.isdigit() and                 normalize_key(txt) not in STRUCTURAL_ABBRS:
            candidates.append(txt)
            break

    return candidates


def get_abbr_text(bibl_elem) -> str:
    """Devuelve el mejor candidato a nombre de autor."""
    candidates = get_author_candidates(bibl_elem)
    return candidates[0] if candidates else ""


def bibl_contains(bibl_elem, keyword: str) -> bool:
    """Comprueba si el texto completo del <bibl> contiene la palabra clave."""
    full = get_text_content(bibl_elem).lower()
    return keyword in full


def apply_context_rules(key: str, bib_id: str, bibl_elem) -> str:
    """Aplica reglas contextuales para desambiguar."""
    for autor_key, context_word, alt_bib in CONTEXT_RULES:
        if autor_key == key and bibl_contains(bibl_elem, context_word):
            return alt_bib
    return bib_id


def lookup_single(key: str, bibl_elem) -> tuple:
    """Busca una clave normalizada en el catálogo."""
    # Búsqueda exacta
    if key in WORKS:
        bib_id, pers_id, cert = WORKS[key]
        bib_id = apply_context_rules(key, bib_id, bibl_elem)
        return bib_id, pers_id, cert
    # Búsqueda por prefijo (≥3 chars)
    if len(key) >= 3:
        hits = [(k, v) for k, v in WORKS.items() if k.startswith(key[:4])]
        if not hits and len(key) >= 3:
            hits = [(k, v) for k, v in WORKS.items() if k.startswith(key[:3])]
        if len(hits) == 1:
            bib_id, pers_id, cert = hits[0][1]
            bib_id = apply_context_rules(hits[0][0], bib_id, bibl_elem)
            return bib_id, pers_id, cert
    return None, None, None


def lookup_author(abbr_raw: str, bibl_elem) -> tuple:
    """
    Busca el autor en el catálogo probando todos los candidatos.
    Devuelve (bib_id, pers_id, cert) o (None, None, None).
    """
    # Obtener todos los candidatos del <bibl>
    candidates = get_author_candidates(bibl_elem)
    # Añadir también el texto raw recibido
    candidates = [abbr_raw] + candidates

    for candidate in candidates:
        key = normalize_key(candidate)
        if not key or len(key) < 2:
            continue
        result = lookup_single(key, bibl_elem)
        if result[0] is not None:
            return result

    return None, None, None


def get_prev_abbr_unit(bibl_elem, w_elem) -> str:
    """
    Intenta determinar la unidad de un número mirando
    el último token estructural (abbr o <w> en UNIT_MAP) que lo precede
    dentro del <bibl>.
    Así «ad 1» queda unit="ad" en vez de heredar el abbr anterior.
    """
    prev_token = None
    for child in bibl_elem.iter():
        if child is w_elem:
            break
        if child.tag == tag('abbr'):
            txt = get_text_content(child).rstrip('.').lower()
            if txt:
                prev_token = txt
        elif child.tag == tag('w') and child.text:
            # Un <w> cuyo texto coincide con una clave de UNIT_MAP se trata
            # como token estructural (p.ej. «ad» en «ad primum»).
            txt = child.text.strip().rstrip('.').lower()
            if txt in UNIT_MAP:
                prev_token = txt
    if prev_token:
        return UNIT_MAP.get(prev_token, "?")
    return "?"

# ─────────────────────────────────────────────────────────────────────────────
# TRANSFORMACIONES
# ─────────────────────────────────────────────────────────────────────────────

def fix_empty_expan(bibl_elem):
    """Completa <expan><w/></expan> vacíos con un placeholder."""
    for expan in bibl_elem.findall(f".//{tag('expan')}"):
        w = expan.find(tag('w'))
        if w is not None and (not w.text or not w.text.strip()):
            w.text = None
            sup = etree.SubElement(expan, tag('supplied'))
            sup.set('resp', '#editor_AV')
            sup.set('cert', 'low')
            sup.text = '[expan. desideratur]'


def add_corresp_cert(bibl_elem, bib_id: str, cert: str):
    """Añade @corresp y @cert al <bibl> si no los tiene."""
    if 'corresp' not in bibl_elem.attrib:
        bibl_elem.set('corresp', f'#{bib_id}')
    if 'cert' not in bibl_elem.attrib:
        bibl_elem.set('cert', cert)


def _is_author_choice(choice_elem) -> bool:
    """
    True si el <choice> representa un nombre de autor
    (su <abbr><w> no es una abreviatura estructural).
    """
    abbr = choice_elem.find(tag('abbr'))
    if abbr is None:
        return False
    w = abbr.find(tag('w'))
    if w is None:
        return False
    txt = get_text_content(w).rstrip('.').lower()
    return normalize_key(txt) not in STRUCTURAL_ABBRS


def wrap_author(bibl_elem, pers_id: str):
    """
    Envuelve en <author ref="#pers_id"> el token o tokens que identifican
    al autor dentro del <bibl>. Lógica de prioridad:

      1. Primer <w> hijo directo no numérico y no estructural (nombre sin
         abreviar, p.ej. <w>Soto</w> o <w>Me<lb break="no"/>din</w>).
         Si el <w> siguiente es también de autor (compuesto), se incluyen ambos.
      2. Primer <choice> hijo directo cuya <abbr> no sea estructural.
         Si el <choice> siguiente también es de autor (p.ej. S. + Faust.),
         se incluyen ambos dentro del mismo <author>.

    Solo actúa si no existe ya un <author> en el <bibl>.
    """
    if bibl_elem.find(tag('author')) is not None:
        return  # ya tiene author

    children = list(bibl_elem)
    author_el = etree.Element(tag('author'))
    if pers_id:
        author_el.set('ref', f'#{pers_id}')

    # ── Prioridad 1: <w> hijo directo no estructural ──────────────────────────
    # Solo si no hay ningún <choice> de autor que lo preceda en la lista de hijos.
    # Caso Sylu. verb. emptio: el <choice>Sylu.</choice> precede a <w>emptio</w>,
    # así que la prioridad 1 cede a la prioridad 2 para no confundir el lema con
    # el nombre del autor.
    author_choice_before_w = any(
        _is_author_choice(c)
        for c in children
        if c.tag == tag('choice')
    )
    if not author_choice_before_w:
        for i, child in enumerate(children):
            if child.tag != tag('w'):
                continue
            txt = get_text_content(child)
            if not txt or txt.isdigit() or normalize_key(txt) in STRUCTURAL_ABBRS:
                continue
            # Encontrado el <w> del autor; insertar <author> en su posición
            bibl_elem.insert(i, author_el)
            bibl_elem.remove(child)
            author_el.append(child)
            # ¿El siguiente hermano también es nombre de autor?
            siblings = list(bibl_elem)
            if i + 1 < len(siblings):
                nxt = siblings[i + 1]
                if nxt.tag == tag('w'):
                    nxt_txt = get_text_content(nxt)
                    if nxt_txt and not nxt_txt.isdigit() and                             normalize_key(nxt_txt) not in STRUCTURAL_ABBRS:
                        bibl_elem.remove(nxt)
                        author_el.append(nxt)
            return

    # ── Prioridad 2: <choice> cuya abbr no sea estructural ───────────────────
    for i, child in enumerate(children):
        if child.tag != tag('choice'):
            continue
        if not _is_author_choice(child):
            continue
        # Encontrado el <choice> del autor
        bibl_elem.insert(i, author_el)
        bibl_elem.remove(child)
        author_el.append(child)
        # ¿El siguiente hermano también es <choice> de autor? (p.ej. S. + Faust.)
        siblings = list(bibl_elem)
        if i + 1 < len(siblings):
            nxt = siblings[i + 1]
            if nxt.tag == tag('choice') and _is_author_choice(nxt):
                bibl_elem.remove(nxt)
                author_el.append(nxt)
        return


def mark_numeric_w(bibl_elem):
    """
    Convierte <w>N</w> con contenido numérico en
    <biblScope unit="?"><w>N</w></biblScope>
    marcados para revisión manual (unit="?").
    Solo actúa sobre <w> que sean hijos directos del <bibl>
    y que no estén ya dentro de un <biblScope>.
    """
    children = list(bibl_elem)
    for i, child in enumerate(children):
        if child.tag == tag('w') and child.text and \
           child.text.strip().isdigit():
            # determinar unidad por el abbr precedente
            unit = get_prev_abbr_unit(bibl_elem, child)
            scope = etree.Element(tag('biblScope'))
            scope.set('unit', unit)
            # heredar tail del <w>
            scope.tail = child.tail
            child.tail = None
            bibl_elem.insert(i, scope)
            bibl_elem.remove(child)
            scope.append(child)



# ─────────────────────────────────────────────────────────────────────────────
# PASO 0: DETECCIÓN Y ENVOLTURA DE <bibl>
# Lógica extraída de onate_add_bibl.py
# ─────────────────────────────────────────────────────────────────────────────

# Apellidos de autores sin punto abreviativo (formas completas en el impreso).
# Incluir tanto la raíz abreviada como las formas latinas completas (-us, -ius…)
# que pueden aparecer en el texto tipográfico sin punto abreviativo.
AUTHOR_NAMES = {
    # Formas abreviadas (raíz)
    "Bannes", "Aragon", "Salon", "Lessius", "Salas",
    "Tolet", "Couar", "Gabr", "Manuel", "Conrad",
    "Valent", "Caiet", "Reginald", "Bonacin", "Filliuc",
    "Medin", "Sotus", "Soto", "Azor", "Anton", "Sylu",
    "Scotus", "Maior",
    # Formas latinas completas
    "Reginaldus", "Bannez", "Aragonius", "Salonius",
    "Lessius", "Molina", "Navarrus", "Covarrubias",
    "Bonacina", "Filliucius", "Medina", "Azorius",
    "Antoninus", "Sylvester", "Conradus", "Sotus",
    "Valentinus", "Caietanus", "Scotus", "Maior",
    "Toletus", "Salas", "Gabriel", "Faustus",
}

# Abreviaturas de autor que inician un nuevo <bibl>
AUTHOR_ABBREVS_BIBL = {
    "Arist.", "Aristot.", "Aug.", "August.", "Th.", "Thom.",
    "Cic.", "Plat.", "Plut.", "Ambr.", "Hier.", "Greg.",
    "Ign.", "Tert.", "Orig.", "Bas.", "Chrys.", "D.",
    "Nau.", "Mol.", "Molin.", "Less.", "Lessius.", "Leff.",
    "Sal.", "Salas.", "Salon.", "Couar.", "Couarr.",
    "Bonac.", "Bonacin.", "Regin.", "Reginald.",
    "Azor.", "Tolet.", "Sot.", "Sotus.", "Med.", "Medin.",
    "Filliuc.", "Filliucc.", "Gabr.", "Manuel.",
    "Anton.", "Sylu.", "Conrad.",
    "Faust.", "Faustus.", "Valent.", "Aragon.", "Caiet.",
    "Bannes.", "Bann.", "S.",
    "Scot.", "Scotus.", "Mai.", "Maior.",
}

# Tokens que pertenecen al interior de un <bibl>
BIBL_INTRA_TOKENS = {
    "cap.", "lib.", "q.", "n.", "art.", "ar.", "disp.", "disput.",
    "tract.", "tit.", "dub.", "punct.", "sect.", "par.", "prop.",
    "concl.", "coroll.", "obs.", "def.", "theor.", "prol.",
    "p.", "pp.", "tom.", "vol.", "pars.", "part.",
    "var.", "verb.", "sum.", "inst.", "instit.",
    "ethic.", "mor.", "restit.", "restitut.",
    "iust.", "contract.", "contractib.", "empt.", "emptione.",
    "peccat.", "septem.", "trinitate.",
    "reip.", "repub.", "ff.", "seqq.", "iun.", "contr.",
}

BIBL_INTER_TOKENS = {"ibi"}


def _get_w_text(elem) -> str:
    """Extrae el texto visible de un elemento <w> o <choice>."""
    if elem.tag == tag('w'):
        parts = [elem.text or ""]
        for child in elem:
            if child.tail:
                parts.append(child.tail)
        return "".join(parts).strip()
    if elem.tag == tag('choice'):
        for inner in elem:
            if inner.tag in (tag('abbr'), tag('orig')):
                w = inner.find(tag('w'))
                if w is not None:
                    return _get_w_text(w)
    return (elem.text or "").strip()


def _is_author_elem(elem) -> bool:
    """True si el elemento es una abreviatura o nombre de autor."""
    if elem.tag == tag('choice'):
        abbr = elem.find(tag('abbr'))
        if abbr is not None:
            w = abbr.find(tag('w'))
            if w is not None and (w.text or "").strip() in AUTHOR_ABBREVS_BIBL:
                return True
    if elem.tag == tag('w'):
        if (elem.text or "").strip() in AUTHOR_NAMES:
            return True
    return False


def _is_bibl_cont(elem, next_elem=None) -> bool:
    """True si el elemento puede continuar (pertenecer a) un <bibl> abierto."""
    if elem.tag in (tag('lb'), tag('pc')):
        return True

    if elem.tag == tag('choice'):
        abbr = elem.find(tag('abbr'))
        if abbr is not None:
            w = abbr.find(tag('w'))
            if w is not None:
                txt = (w.text or "").strip()
                if txt in AUTHOR_ABBREVS_BIBL:
                    return False   # nuevo autor → cierra bibl actual
                if txt in BIBL_INTRA_TOKENS:
                    return True
        return False

    if elem.tag == tag('w'):
        txt = (elem.text or "").strip()
        if txt.isdigit():
            return True
        if txt in BIBL_INTRA_TOKENS or txt in BIBL_INTER_TOKENS:
            return True
        if txt in AUTHOR_NAMES:
            return False           # nuevo autor → cierra bibl actual
        if txt and txt[0].isupper():
            return True
        if txt in ("&", "&amp;", "et"):
            return next_elem is not None and _is_author_elem(next_elem)

    return False


def wrap_bibls_in_container(parent, force: bool = False) -> int:
    """
    Detecta secuencias bibliográficas en parent y las envuelve en <bibl>.
    Respeta <bibl> ya existentes salvo force=True.
    Devuelve número de <bibl> añadidos.
    """
    children = list(parent)
    if not children:
        return 0

    # Si ya hay bibl en cualquier descendiente (no solo hijo directo) y no force,
    # respetar los tags corregidos manualmente (hi, s, etc.) sin tocarlos.
    if not force and any(d.tag == tag('bibl') for d in parent.iter()
                         if d is not parent):
        return 0

    # Si force, aplanar bibl existentes
    if force:
        expanded = []
        for c in children:
            if c.tag == tag('bibl'):
                expanded.extend(list(c))
            else:
                expanded.append(c)
        for c in list(parent):
            parent.remove(c)
        for c in expanded:
            parent.append(c)
        children = list(parent)

    # Agrupar tokens en secuencias bibl
    i = 0
    groups = []   # lista de ('bibl'|'elem', [elementos])
    while i < len(children):
        elem     = children[i]
        next_e   = children[i+1] if i+1 < len(children) else None

        if _is_author_elem(elem):
            bibl_elems = [elem]
            i += 1
            while i < len(children):
                e  = children[i]
                ne = children[i+1] if i+1 < len(children) else None
                if _is_author_elem(e):
                    groups.append(('bibl', bibl_elems))
                    bibl_elems = [e]
                    i += 1
                elif _is_bibl_cont(e, ne):
                    bibl_elems.append(e)
                    i += 1
                else:
                    break
            groups.append(('bibl', bibl_elems))
        else:
            groups.append(('elem', [elem]))
            i += 1

    # Reconstruir parent
    for c in list(parent):
        parent.remove(c)

    added = 0
    for kind, elems in groups:
        if kind == 'bibl' and elems:
            b = etree.SubElement(parent, tag('bibl'))
            for e in elems:
                b.append(e)
            added += 1
        else:
            for e in elems:
                parent.append(e)

    return added




def detect_and_wrap_bibls(root, force: bool = False) -> int:
    """
    Paso 0: recorre todos los <s> y <hi rend=\"italic\"> del árbol
    y aplica wrap_bibls_in_container a cada uno.
    Devuelve el total de <bibl> añadidos.
    """
    total = 0
    for container in list(root.iter(tag('s'))) + list(root.iter(tag('hi'))):
        total += wrap_bibls_in_container(container, force=force)
    return total


def add_cit_wrappers(bibls_to_wrap: list, col_label: str) -> int:
    """
    Envuelve en <cit xml:id="..."> únicamente los <bibl> de la lista
    bibls_to_wrap (los recién enriquecidos en el Paso 1 de esta ejecución).

    Al operar solo sobre los bibls procesados en esta pasada, el script es
    idempotente: ejecuciones repetidas no duplican <cit> ni alteran <bibl>
    que ya estaban envueltos o que el editor corrió manualmente.
    """
    counter = 0
    for bibl in bibls_to_wrap:
        parent = bibl.getparent()
        if parent is None or parent.tag == tag('cit'):
            continue  # ya tiene cit o es raíz (no debería ocurrir, pero por si acaso)

        counter += 1
        corresp = bibl.get('corresp', '')
        base    = corresp.lstrip('#').replace('bib_', '') or 'noref'
        xml_id  = f"cit_{col_label}_{base}_{counter}"

        cit = etree.Element(tag('cit'))
        cit.set(xml_attr('id'), xml_id)
        cit.tail  = bibl.tail
        bibl.tail = None

        idx = list(parent).index(bibl)
        parent.insert(idx, cit)
        parent.remove(bibl)
        cit.append(bibl)

    return counter


def enrich_bibl(bibl_elem, report: list, dry_run: bool = False):
    """
    Aplica todas las transformaciones a un <bibl> sin @corresp.
    Los <bibl type="legal"> se saltan — serán enriquecidos en una fase posterior.
    """
    if bibl_elem.get('type') == 'legal':
        return
    abbr_raw = get_abbr_text(bibl_elem)
    bib_id, pers_id, cert = lookup_author(abbr_raw, bibl_elem)

    status = "OK" if bib_id else "NO_MATCH"
    report.append({
        "abbr":    abbr_raw,
        "bib_id":  bib_id,
        "pers_id": pers_id,
        "cert":    cert,
        "status":  status,
    })

    if dry_run or not bib_id:
        return

    fix_empty_expan(bibl_elem)
    add_corresp_cert(bibl_elem, bib_id, cert)
    wrap_author(bibl_elem, pers_id)
    mark_numeric_w(bibl_elem)

# ─────────────────────────────────────────────────────────────────────────────
# PROCESAMIENTO DE ARCHIVO
# ─────────────────────────────────────────────────────────────────────────────

def process_file(input_path: Path, output_path: Path,
                 dry_run: bool = False, verbose: bool = True,
                 force_bibl: bool = False) -> list:
    """
    Lee un archivo de página TEI, aplica los tres pasos del pipeline
    y escribe el resultado.
    Devuelve el informe de transformaciones.

    force_bibl=True → reconstruye <bibl> aunque ya existan
                       (útil tras edición manual del src/)
    """
    parser = etree.XMLParser(remove_blank_text=True)
    tree   = etree.parse(str(input_path), parser)
    root   = tree.getroot()

    # ── Paso 0: detectar y envolver secuencias bibliográficas en <bibl> ─────────
    bibl_added = 0
    if not dry_run:
        bibl_added  = detect_and_wrap_bibls(root, force=force_bibl)

    report = []
    total  = 0
    enriched = 0
    enriched_bibls = []   # <bibl> procesados en esta ejecución → candidatos a <cit>

    for bibl in list(root.iter(tag('bibl'))):
        # Saltar bibls que ya tienen @corresp o @xml:id propios
        if 'corresp' in bibl.attrib or (
            '{http://www.w3.org/XML/1998/namespace}id' in bibl.attrib):
            continue
        total += 1
        enrich_bibl(bibl, report, dry_run)
        if report and report[-1]['status'] == 'OK':
            enriched += 1
        # Registrar siempre (OK o NO_MATCH) para envolver en <cit>
        if not dry_run:
            enriched_bibls.append(bibl)

    # ── Paso 2: envolver SOLO los <bibl> recién enriquecidos en <cit xml:id> ────
    #   (idempotente: no toca bibls de ejecuciones anteriores ni ediciones manuales)
    col_label = column_from_filename(input_path)
    cit_added = 0
    if not dry_run:
        cit_added = add_cit_wrappers(enriched_bibls, col_label)

    if verbose:
        print(f"\n{'[DRY-RUN] ' if dry_run else ''}{input_path.name}")
        if not dry_run:
            print(f"  <bibl> detectados y añadidos   : {bibl_added}")
        print(f"  <bibl> encontrados sin @corresp : {total}")
        print(f"  Enriquecidos automáticamente   : {enriched}")
        print(f"  Sin coincidencia (revisar)     : {total - enriched}")
        if not dry_run:
            print(f"  <cit> añadidos                 : {cit_added}")

    if not dry_run:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        tree.write(str(output_path),
                   xml_declaration=True,
                   encoding='UTF-8',
                   pretty_print=True)
        if verbose:
            print(f"  → Escrito en: {output_path}")

    return report


def print_report(report: list):
    """Imprime un informe detallado de las transformaciones."""
    print("\n" + "═" * 60)
    print("INFORME DE ENRIQUECIMIENTO")
    print("═" * 60)

    ok       = [r for r in report if r['status'] == 'OK']
    no_match = [r for r in report if r['status'] == 'NO_MATCH']

    print(f"\n✓ Coincidencias automáticas ({len(ok)}):")
    for r in ok:
        print(f"  {r['abbr']:<20} → {r['bib_id']} [{r['cert']}]")

    if no_match:
        print(f"\n✗ Sin coincidencia — requieren revisión manual ({len(no_match)}):")
        for r in no_match:
            print(f"  {r['abbr']}")
        print("\n  → Para estos casos use bibl_encoder.py o añada")
        print("    la clave al diccionario WORKS de este script.")

    print()

# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]

    if not args or args[0] in ('-h', '--help'):
        print(__doc__)
        sys.exit(0)

    dry_run    = '--dry-run'    in args
    do_report  = '--report'    in args
    force_bibl = '--force-bibl' in args
    args = [a for a in args if not a.startswith('--')]

    # Modo batch
    if args and args[0] == '--batch':
        # ya filtrado arriba — no puede llegar aquí con --batch en args
        pass

    # Detectar --batch antes del filtrado
    raw_args = sys.argv[1:]
    if '--batch' in raw_args:
        idx = raw_args.index('--batch')
        src_dir = Path(raw_args[idx + 1])
        out_dir = Path(raw_args[idx + 2]) if len(raw_args) > idx + 2 else src_dir
        xmls = sorted(src_dir.glob('*.xml'))
        if not xmls:
            print(f"No se encontraron .xml en {src_dir}")
            sys.exit(1)
        all_report = []
        for xml in xmls:
            suffix = '_bibl' if '_bibl' not in xml.stem else ''
            out = out_dir / (xml.stem + suffix + '.xml')
            r = process_file(xml, out, dry_run=dry_run,
                             force_bibl=force_bibl)
            all_report.extend(r)
        if do_report:
            print_report(all_report)
        sys.exit(0)

    # Modo fichero único
    if not args:
        print("Error: especifique un archivo de entrada.")
        sys.exit(1)

    input_path = Path(args[0])
    if not input_path.exists():
        print(f"Error: no existe {input_path}")
        sys.exit(1)

    if len(args) >= 2:
        output_path = Path(args[1])
    else:
        output_path = input_path.with_stem(input_path.stem + '_bibl')

    report = process_file(input_path, output_path,
                         dry_run=dry_run, force_bibl=force_bibl)

    if do_report:
        print_report(report)


if __name__ == '__main__':
    main()
