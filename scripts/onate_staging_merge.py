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
    r'|//'           # salto de línea / sentencia
    r'|¶'            # párrafo
    r'|¬'            # corte de palabra
    r'|~'            # corte sin guion
    r'|[@*]'         # apertura/cierre de referencia (@) o cursiva (*)
)

# Anotaciones de corrección manual: {orig|corr}
# orig = lo que dice el facsímil/Transkribus, corr = forma corregida
CHOICE_RE = re.compile(r'\{([^{}|]*)\|([^{}]*)\}')

MACRON_EXPAND = {
    'ā': 'am', 'ē': 'em', 'ī': 'im', 'ō': 'on', 'ô': 'on', 'ū': 'um',
    'Ā': 'Am', 'Ē': 'Em', 'Ī': 'Im', 'Ō': 'On', 'Ū': 'Um',
}

# Abreviaturas que Transkribus expande sistemáticamente (comportamiento del
# modelo, no un error puntual del HTR) y que por eso se corrigen a mano en
# el staging en vez de en Transkribus (ver onate_tokens.ABBREV_SEMICOLON_EXPAN
# para el diccionario completo que sí usa el pipeline TEI). Aquí solo se
# necesita para que la comparación del merge no marque la línea como
# cambiada — de momento, acotado a los casos confirmados.
ABBREV_EXPAND_STAGING = {
    'Itaq;': 'Itaque',
}

def expand_macrons(text: str) -> str:
    for m, exp in MACRON_EXPAND.items():
        text = text.replace(m, exp)
    for abbr, exp in ABBREV_EXPAND_STAGING.items():
        text = text.replace(abbr, exp)
    return text

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
    que ambos lados de la comparación queden normalizados por igual."""
    text = CHOICE_RE.sub(lambda m: m.group(1), text)
    text = ANNOTATION_RE.sub('', text)
    text = re.sub(r'  +', ' ', text)
    return expand_macrons(text)


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
    for lid, new_text in new_map.items():
        if lid not in old_map:
            continue
        el       = old_map[lid]
        old_text = el.text or ''

        old_clean = strip_anns(old_text).strip()
        new_clean = strip_anns(new_text).strip()

        if old_clean == new_clean:
            continue  # sin cambio
        # Ignorar líneas del staging que contienen macrones (anotación manual)
        if any(c in old_text for c in 'āēīōūĀĒĪŌŪ'):
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
    if changes == 0:
        print("✓ Sin cambios de texto — el staging está actualizado.")
        return

    print(f"  {changes} línea(s) con cambios de texto.")

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
