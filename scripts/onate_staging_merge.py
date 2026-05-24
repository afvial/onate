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
ANNOTATION_RE = re.compile(
    r'@[^@]+@'       # referencias  @Suárez, De legibus@
    r'|\*[^*]+\*'    # cursiva       *verbum*
    r'|¶'            # párrafo
    r'|¬'            # corte de palabra
    r'|//'           # salto de línea / sentencia
)


def strip_anns(text: str) -> str:
    """Texto sin marcas de anotación."""
    return ANNOTATION_RE.sub('', text)


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

        # Extraer anotaciones del texto antiguo
        anns   = extract_anns(old_text)
        merged = apply_anns(new_clean, anns)

        changes += 1
        print(f"  Línea {lid}: '{old_clean[:45]}' → '{new_clean[:45]}'")
        if anns:
            print(f"    Anotaciones: {[a for _, a in anns]}")

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
