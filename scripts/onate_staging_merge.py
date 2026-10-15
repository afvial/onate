#!/usr/bin/env python3
"""
onate_staging_merge.py — Aplica cambios de texto del PAGE XML al staging anotado
                          sin perder las anotaciones manuales ni la estructura XML.

Uso:
    python3 scripts/onate_staging_merge.py \\
        staging/disp63/pg_63_39_izq.xml \\
        transkribus/disp63/pg_63_39_izq.xml \\
        [--out staging/disp63/pg_63_39_izq.xml] \\
        [--dry-run]
"""

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    from lxml import etree
except ImportError:
    sys.exit("ERROR: pip install lxml")

# ── Marcas de anotación del staging ──────────────────────────────────────────
# El staging se procesa línea por línea (una <line> a la vez), así que una
# marca de apertura/cierre (@...@, *...*) puede tener sus dos extremos en
# líneas DISTINTAS cuando Transkribus reordena o funde líneas del PAGE XML.
# Por eso @ y * se tratan como marcadores ATÓMICOS (el símbolo suelto), no
# como r'@[^@]+@' que exige encontrar el par completo dentro del mismo
# fragmento de texto: así cada extremo se extrae y reinserta de forma
# independiente, por posición relativa, sin importar en qué línea caiga.
ANNOTATION_RE = re.compile(
    r'^##'           # heading principal (inicio de línea)
    r'|^#'           # sub-heading (inicio de línea)
    r'|^>+'          # summarium: '>>>' inicio de dubium numerado,
                      # '>>' línea de continuación (inicio de línea)
    r'|//'           # salto de línea / sentencia
    r'|¶'            # párrafo
    r'|¬'            # corte de palabra
    r'|~'            # corte sin guion
    r'|[@*]'         # apertura/cierre de referencia (@) o cursiva (*)
)

# Anotaciones de corrección manual: {orig|corr}
# orig = lo que dice el facsímil/Transkribus, corr = forma corregida
CHOICE_RE = re.compile(r'\{([^{}|]*)\|([^{}]*)\}')

# Expansión de macrones: MISMA lógica que onate_tei.py (posición dentro
# de la palabra decide m/n), copiada literalmente de sus tablas
# _MACRON_FINAL/_MACRON_MEDIAL. Antes esto era una sustitución fija por
# vocal (ā siempre -> am) que no coincidía con lo que el pipeline real
# hace — causaba falsos positivos/negativos en el --dry-run para
# palabras donde el macrón medial expande con "n" (tãtam -> tantam),
# y llevó a introducir por error una notación de tilde (ã, ẽ...) que
# el pipeline real NO reconoce (rompe el lemma/tooltip). Esa notación
# ya no hace falta: con esta lógica, el macrón normal (ā) basta.
_MACRON_FINAL = {"ā": "am", "ē": "em", "ī": "im", "ō": "om", "ô": "on", "ū": "um",
                 "Ā": "Am", "Ē": "Em", "Ī": "Im", "Ō": "Om", "Ū": "Um"}
_MACRON_MEDIAL = {"ā": "an", "ē": "en", "ī": "in", "ō": "on", "ô": "on", "ū": "un",
                  "Ā": "An", "Ē": "En", "Ī": "In", "Ō": "On", "Ū": "Un"}
_MACRON_CHARS = set(_MACRON_FINAL)

# Abreviaturas que Transkribus expande sistemáticamente (comportamiento del
# modelo, no un error puntual del HTR) y que por eso se corrigen a mano en
# el staging en vez de en Transkribus (ver onate_tokens.ABBREV_SEMICOLON_EXPAN
# para el diccionario completo que sí usa el pipeline TEI). Aquí solo se
# necesita para que la comparación del merge no marque la línea como
# cambiada — de momento, acotado a los casos confirmados.
ABBREV_EXPAND_STAGING = {
    'Itaq;': 'Itaque',
    'quocunq;': 'quocunque',
    'vnusquisq;': 'vnusquisque',
    'hucusq;': 'hucusque',
}

def _expand_macrons_positional(text: str) -> str:
    """Expande macrones mirando la LETRA siguiente (no solo la posición),
    igual que onate_tei.py._expand_macrons — ver esa función para el
    detalle de la regla (labial->m, otra letra->n, ¬->n, fin real->m).
    Al mirar directamente el carácter siguiente en el texto completo,
    los espacios entre palabras ya actúan como 'fin real' sin necesidad
    de separar la línea en palabras."""
    if not any(c in text for c in _MACRON_CHARS):
        return text
    chars = []
    n = len(text)
    for idx, ch in enumerate(text):
        if ch not in _MACRON_CHARS:
            chars.append(ch)
            continue
        nxt = text[idx + 1] if idx + 1 < n else ''
        if nxt.isalpha() and nxt.lower() in "bpm":
            chars.append(_MACRON_FINAL[ch])
        elif nxt.isalpha() or nxt == '¬':
            chars.append(_MACRON_MEDIAL[ch])
        else:
            chars.append(_MACRON_FINAL[ch])
    return ''.join(chars)

# Las mismas abreviaturas que expande el pipeline TEI (onate_tokens.py):
# Transkribus las escribe EXPANDIDAS (qualiscumque, non, reipublicae) y el
# staging conserva la forma IMPRESA (qualiscumq;, nō, reip). Para comparar,
# ambos lados se normalizan a la forma expandida; al fusionar, la forma
# impresa del staging se restituye.
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from onate_tokens import ABBREV_SEMICOLON_EXPAN, ABBREV_NO_DOT
except Exception:                                   # onate_tokens sin estas tablas
    ABBREV_SEMICOLON_EXPAN, ABBREV_NO_DOT = {}, {}
MACRON_WORDS = {"nō": "non", "Nō": "Non", "NŌ": "NON"}   # = onate_tei._MACRON_WORDS
ABBREV_FORMS = {k: v.replace("ſ", "s") for k, v in
                {**ABBREV_EXPAND_STAGING, **ABBREV_SEMICOLON_EXPAN,
                 **ABBREV_NO_DOT, **MACRON_WORDS}.items() if v}
_WB = r"(?<![\wſ])"            # límite de palabra (las formas pueden acabar en ; o :)
_WE = r"(?![\wſ])"
_ABBR_RE = [(re.compile(_WB + re.escape(a) + _WE), e)
            for a, e in sorted(ABBREV_FORMS.items(), key=lambda kv: -len(kv[0]))]
_MACRON_WORD_RE = re.compile(r"[\wſ]*[āēīōūôĀĒĪŌŪ][\wſ]*")


def expand_abbrevs(text: str) -> str:
    for rx, exp in _ABBR_RE:
        text = rx.sub(exp, text)
    return text


def expand_macrons(text: str) -> str:
    """Abreviaturas de palabra completa primero (quocūq; → quocunque, nō → non),
    después la regla posicional del macrón."""
    return _expand_macrons_positional(expand_abbrevs(text))


def abbreviated_words(old_text: str) -> list:
    """Palabras abreviadas del staging, en orden: [(forma_impresa, expansión, k)],
    donde k = cuántas veces aparece ya esa expansión antes, en el texto
    normalizado (para restituir la aparición correcta: 're non … qui nō')."""
    base = CHOICE_RE.sub(lambda m: m.group(1), old_text)
    hits = []
    for rx, exp in _ABBR_RE:
        for m in rx.finditer(base):
            hits.append((m.start(), m.end(), m.group(), exp))
    for m in _MACRON_WORD_RE.finditer(base):
        if any(a <= m.start() < b for a, b, _, _ in hits):
            continue
        nxt = base[m.end(): m.end() + 1]
        exp = _expand_macrons_positional(m.group() + ("¬" if nxt == "¬" else "")).rstrip("¬")
        hits.append((m.start(), m.end(), m.group(), exp))
    hits.sort()
    out = []
    for a, b, form, exp in hits:
        prefix = strip_anns(base[:a])
        k = len(re.findall(_pat(exp), prefix))
        out.append((form, exp, k))
    return out


_EQUIV = {"s": "[sſ]", "ſ": "[sſ]", "u": "[uv]", "v": "[uv]", "U": "[UV]", "V": "[UV]"}


def _pat(exp: str) -> str:
    """Patrón de palabra completa para una expansión; s/ſ y u/v intercambiables
    (Qvomodocumq; se expande a Quomodocumque, Transkribus escribe Qvomodocumque)."""
    return _WB + "".join(_EQUIV.get(c, re.escape(c)) for c in exp) + _WE


def fold(text: str) -> str:
    """Para comparar: s larga y u/v no cuentan como diferencia."""
    return text.replace("ſ", "s").replace("v", "u").replace("V", "U")


def restore_abbrevs(merged: str, words: list):
    """Sustituye en el texto fusionado la k-ésima aparición de cada expansión
    por la forma impresa. Devuelve (texto, [expansiones no encontradas])."""
    missing = []
    for form, exp, k in reversed(words):      # de atrás adelante: los k no se desplazan
        ms = list(re.finditer(_pat(exp), merged))
        if len(ms) <= k:
            missing.append(exp); continue
        m = ms[k]
        merged = merged[:m.start()] + form + merged[m.end():]
    return merged, missing


def expand_macrons_alt(text: str) -> str:
    """Variante alternativa: usa n en vez de m para nasales."""
    alt = {'am': 'an', 'em': 'en', 'om': 'on', 'um': 'un',
           'Am': 'An', 'Em': 'En', 'Om': 'On', 'Um': 'Un'}
    result = expand_macrons(text)
    for a, b in alt.items():
        result = result.replace(a, b)
    return result


def strip_anns(text: str) -> str:
    """Texto sin marcas de anotación, con macrones expandidos.
    Las anotaciones {orig|corr} se reducen a 'orig' (forma de Transkribus).
    Colapsa espacios múltiples que quedan al quitar un marcador atómico
    (ej. '16.@ @ Palacios' -> '16.  Palacios' -> '16. Palacios'), igual que
    normalize_unicode() hace del lado del texto nuevo de Transkribus, para
    que ambos lados de la comparación queden normalizados por igual.

    Los macrones se expanden ANTES de quitar los marcadores de anotación
    (¬, @, *...): la lógica posicional (final=m, medial=n) necesita ver
    si algo sigue inmediatamente al carácter con macrón — p.ej. 'cō¬'
    debe leerse como medial (algo sigue: ¬, la palabra continúa en la
    siguiente línea) y dar 'con¬', no 'com¬'. Si se quitara el ¬ primero,
    'cō' parecería el final absoluto de la palabra y daría el resultado
    equivocado."""
    text = CHOICE_RE.sub(lambda m: m.group(1), text)
    text = expand_macrons(text)
    text = ANNOTATION_RE.sub('', text)
    text = re.sub(r'  +', ' ', text)
    return text


def extract_anns(text: str) -> list[tuple[float, str]]:
    """
    Devuelve [(posición_relativa, anotación), ...].
    La posición es relativa al texto sin anotaciones (0.0 = inicio, 1.0 = fin).
    """
    clean = strip_anns(text)
    total = len(clean) or 1
    result = []
    for m in ANNOTATION_RE.finditer(text):
        before = strip_anns(text[:m.start()])
        result.append((len(before) / total, m.group()))
    return result


def apply_anns(new_text: str, anns: list[tuple[float, str]]) -> str:
    """Inserta las anotaciones en el nuevo texto por posición relativa."""
    if not anns:
        return new_text
    chars = list(new_text)
    offset = 0
    for rel, ann in sorted(anns, key=lambda x: x[0]):
        pos = min(int(rel * len(new_text)), len(chars))
        chars.insert(pos + offset, ann)
        offset += 1
    return ''.join(chars)


def normalize_staging(page_xml: Path) -> dict[str, str]:
    """
    Corre onate_normalize.py y devuelve {line_id: text_content}.
    """
    normalize = Path(__file__).parent / 'onate_normalize.py'
    if not normalize.exists():
        sys.exit(f"ERROR: no se encuentra {normalize}")

    with tempfile.NamedTemporaryFile(suffix='.xml', delete=False) as f:
        tmp = Path(f.name)

    r = subprocess.run(
        [sys.executable, str(normalize), str(page_xml), '--out', str(tmp)],
        capture_output=True, text=True
    )
    if r.returncode != 0:
        sys.exit(f"ERROR en onate_normalize.py:\n{r.stderr}")

    lines = parse_lines(tmp)
    tmp.unlink()
    return lines


def parse_lines(xml_path: Path) -> dict[str, str]:
    """Parsea el staging XML y devuelve {line_id: text_content}."""
    tree = etree.parse(str(xml_path))
    result = {}
    for el in tree.findall('.//line'):
        lid = el.get('id', '')
        result[lid] = el.text or ''
    return result


def _macron_diff_is_isolated(old_text: str, new_clean: str) -> bool:
    """
    True si CADA palabra del staging que contiene macrón, ya expandida,
    aparece literalmente en new_clean — es decir, el macrón no es la
    causa de que old_clean != new_clean (el cambio real está en otra
    parte de la línea, p.ej. un punto final que falta). En ese caso es
    seguro dejar que el merge normal se aplique: new_clean ya trae esa
    palabra bien, así que reinsertar anotaciones sobre new_clean no
    pierde nada.

    False si alguna palabra con macrón, expandida, NO aparece en
    new_clean (Transkribus leyó esa palabra distinto — p.ej. 'coran' en
    vez de 'coram') — ahí sí hace falta revisión manual, porque no hay
    forma segura de saber si el nuevo texto es una mejora real o un
    error de lectura.
    """
    for word in old_text.split():
        if not any(c in word for c in 'āēīōūĀĒĪŌŪ'):
            continue
        expanded = strip_anns(word).strip()
        if expanded and expanded not in new_clean:
            return False
    return True


def main():
    ap = argparse.ArgumentParser(
        description='Aplica cambios de texto al staging conservando anotaciones.')
    ap.add_argument('staging',   type=Path)
    ap.add_argument('page_xml',  type=Path)
    ap.add_argument('--out',     type=Path, default=None)
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    if not args.staging.exists():
        sys.exit(f"ERROR: no se encuentra {args.staging}")
    if not args.page_xml.exists():
        sys.exit(f"ERROR: no se encuentra {args.page_xml}")

    out_path = args.out or args.staging

    print(f"Staging actual:  {args.staging}")
    print(f"PAGE XML nuevo:  {args.page_xml}")
    print(f"Salida:          {out_path}")

    # ── Leer staging actual (con anotaciones) ────────────────────────────────
    tree    = etree.parse(str(args.staging))
    old_map = {}
    for el in tree.findall('.//line'):
        old_map[el.get('id', '')] = el

    # ── Obtener texto nuevo desde normalize ──────────────────────────────────
    new_map = normalize_staging(args.page_xml)

    # ── Comparar y fusionar ──────────────────────────────────────────────────
    changes = 0
    macron_warnings = []
    for lid, new_text in new_map.items():
        if lid not in old_map:
            continue
        el       = old_map[lid]
        old_text = el.text or ''

        old_clean = strip_anns(old_text).strip()
        new_clean = strip_anns(new_text).strip()      # mismo criterio en los dos lados

        if fold(old_clean) == fold(new_clean):
            continue  # sin cambio (o solo ſ/s, u/v)
        # Líneas del staging con macrones (ā, ē, ī, ō, ū): el macrón no es
        # un marcador atómico como @/*/¬ — extract_anns()/apply_anns() no
        # lo reconocen ni lo reinsertan. Si se aplicara el merge normal,
        # el texto fusionado saldría de new_clean (siempre sin macrones,
        # Transkribus nunca los escribe), perdiéndolo para siempre aunque
        # la palabra en sí no haya cambiado. Por eso se avisa y se deja
        # la línea intacta para revisión manual, en vez de sobrescribirla
        # o saltarla en silencio (que ocultaría cambios reales en el resto
        # de la línea).
        # Palabras abreviadas del staging (macrón, qualiscumq;, nō, reip…):
        # Transkribus trae la forma expandida. Si la expansión de cada una
        # sigue en el texto nuevo, la diferencia está en otra parte de la
        # línea: se fusiona y luego se restituye la forma impresa. Si alguna
        # no está (Transkribus leyó esa palabra distinto), revisión manual.
        abbr_words = abbreviated_words(old_text)
        # cada abreviatura necesita su aparición (la k-ésima) en el texto nuevo
        lost = [e for _, e, k in abbr_words
                if len(re.findall(_pat(e), new_clean)) <= k]
        if lost:
            print(f"  ⚠ Línea {lid}: abreviatura cuya expansión no está en el "
                  f"texto nuevo ({', '.join(lost)}) — no se aplica "
                  f"automáticamente. Revisar manualmente:")
            print(f"      staging:    '{old_clean}'")
            print(f"      transkribus: '{new_clean}'")
            macron_warnings.append(lid)
            continue
        # Ignorar líneas cuyo texto base es vacío pero tienen anotaciones
        if not old_clean and old_text.strip():
            continue

        # Anotaciones de corrección {orig|corr}: la palabra 'orig' debe seguir
        # presente en el texto nuevo para poder reinsertar la marca con
        # seguridad. Si Transkribus cambió justo esa palabra, no se toca la
        # línea y se avisa para revisión manual.
        choices = CHOICE_RE.findall(old_text)
        skip_line = False
        for orig, corr in choices:
            if expand_macrons(orig) not in new_clean:
                print(f"  ⚠ Línea {lid}: corrección manual "
                      f"{{{orig}|{corr}}} no encontrada en el texto nuevo "
                      f"('{new_clean[:60]}'). Línea NO actualizada — "
                      f"revisar manualmente.")
                skip_line = True
        if skip_line:
            continue

        # Extraer anotaciones del texto antiguo
        anns   = extract_anns(old_text)
        merged = apply_anns(new_clean, anns)

        # Restituir las formas impresas de las abreviaturas (qualiscumq;, nō…)
        merged, missing = restore_abbrevs(merged, abbr_words)
        if missing:
            print(f"  ⚠ Línea {lid}: no se pudo restituir {missing}; revisar.")

        # Reinsertar las anotaciones {orig|corr} en el texto fusionado
        for orig, corr in choices:
            merged = merged.replace(expand_macrons(orig),
                                     f'{{{orig}|{corr}}}', 1)

        changes += 1
        print(f"  Línea {lid}: '{old_clean}' → '{new_clean}'")
        if anns:
            print(f"    Anotaciones: {[a for _, a in anns]}")
        if choices:
            print(f"    Correcciones preservadas: "
                  f"{[f'{{{o}|{c}}}' for o, c in choices]}")

        if not args.dry_run:
            el.text = merged

    print()
    if changes == 0 and not macron_warnings:
        print("✓ Sin cambios de texto — el staging está actualizado.")
        return

    if changes:
        print(f"  {changes} línea(s) con cambios de texto.")
    if macron_warnings:
        print(f"  {len(macron_warnings)} línea(s) con abreviatura pendiente(s) "
              f"de revisión manual: {', '.join(macron_warnings)}")

    if args.dry_run:
        print("  (--dry-run: no se ha escrito nada)")
        return

    # ── Backup y escritura ───────────────────────────────────────────────────
    bak = args.staging.with_suffix(args.staging.suffix + '.bak')
    shutil.copy2(args.staging, bak)
    print(f"  Backup → {bak}")

    tree.write(str(out_path), encoding='UTF-8', xml_declaration=True,
               pretty_print=True)
    print(f"  → {out_path}")


if __name__ == '__main__':
    main()
