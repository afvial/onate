#!/usr/bin/env python3
"""
onate_normalize.py — Convierte PAGE XML de Transkribus → staging/ (formato ligero)

El output es un XML minimalista pensado para edición manual:

  <lines>
    <line id="tr_1_tl_1">vt D. Aug. ait lib. 11. de</line>
    <line id="tr_1_tl_2">Ciuit. Dei cap. 16. [ Emptor semper in¬</line>
    ...
  </lines>

Sobre este archivo el editor añade marcas editoriales antes de page2tei:
  ¶      → nueva <p> antes de esta posición
  //     → límite de oración
  *…*    → itálica
  @…@    → referencia bibliográfica
  @@     → cierra bibl actual y abre nueva

Advertencias emitidas (no corregidas automáticamente):
  - Unicode que termina sin guión pero la línea siguiente empieza en minúscula

Uso:
  python3 onate_normalize.py transkribus/disp63/pg_63_35_der.xml
  python3 onate_normalize.py transkribus/disp63/pg_63_35_der.xml --out staging/disp63/pg_63_35_der.xml
  python3 onate_normalize.py transkribus/disp63/pg_63_35_der.xml --dry-run
"""

import argparse
import re
import sys
from pathlib import Path
from lxml import etree

PAGE_NS = "http://schema.primaresearch.org/PAGE/gts/pagecontent/2013-07-15"
PAGE    = f"{{{PAGE_NS}}}"


# ── Normalización de texto Unicode ───────────────────────────────────────────

def normalize_unicode(text: str) -> str:
    """Strip + colapso de espacios múltiples internos."""
    if not text:
        return text
    text = text.strip()
    text = re.sub(r"  +", " ", text)
    return text


# ── Advertencia: continuación sospechosa ─────────────────────────────────────

def check_continuation(lines: list[tuple[str, str]]) -> list[str]:
    """
    Emite advertencias cuando una línea NO termina en guión pero la siguiente
    empieza en minúscula (posible corte de palabra no marcado).
    lines: lista de (id, texto_unicode)
    """
    warnings = []
    for i in range(len(lines) - 1):
        curr_id, curr_text = lines[i]
        _, next_text = lines[i + 1]
        if not curr_text or not next_text:
            continue
        ends_hyphen = curr_text.rstrip().endswith("¬") or curr_text.rstrip().endswith("-")
        next_starts_lower = next_text.lstrip() and next_text.lstrip()[0].islower()
        if not ends_hyphen and next_starts_lower:
            warnings.append(
                f"  posible corte sin guión: {curr_id!r} → «{curr_text[-20:]}» / «{next_text[:20]}»"
            )
    return warnings


# ── Pipeline principal ───────────────────────────────────────────────────────

def normalize(input_path: Path, output_path: Path, dry_run: bool):
    parser = etree.XMLParser(remove_blank_text=False)
    tree   = etree.parse(str(input_path), parser)
    root   = tree.getroot()

    total_warnings = []
    unicode_cleaned = 0
    lines_removed   = 0

    # Recoger TextLine en orden de readingOrder
    text_lines = root.findall(f".//{PAGE}TextLine")

    def reading_order(tl):
        custom = tl.get("custom", "")
        m = re.search(r"readingOrder\s*\{index:(\d+)", custom)
        return int(m.group(1)) if m else 9999

    text_lines.sort(key=reading_order)

    line_texts = []  # (id, texto_normalizado)

    for tl in text_lines:
        tl_id = tl.get("id", "?")
        unicode_elem = tl.find(f"{PAGE}TextEquiv/{PAGE}Unicode")
        raw  = (unicode_elem.text or "").strip() if unicode_elem is not None else ""
        norm = normalize_unicode(raw)

        if norm != raw:
            unicode_cleaned += 1

        if not norm:
            total_warnings.append(f"  {tl_id}: Unicode vacío → eliminado")
            lines_removed += 1
            continue

        line_texts.append((tl_id, norm))

    # Advertencias de continuación sospechosa
    cont_warns = check_continuation(line_texts)
    if cont_warns:
        total_warnings.append("Continuaciones sospechosas:")
        total_warnings.extend(cont_warns)

    # ── Resumen ──────────────────────────────────────────────────────────────
    print(f"→ {input_path.name}", file=sys.stderr)
    print(f"  unicode limpiados: {unicode_cleaned}", file=sys.stderr)
    print(f"  líneas eliminadas: {lines_removed}", file=sys.stderr)

    if total_warnings:
        print("Advertencias:", file=sys.stderr)
        for w in total_warnings:
            print(f"  ⚠ {w}", file=sys.stderr)

    if dry_run:
        print("(dry-run: no se escribió ningún archivo)", file=sys.stderr)
        return

    # ── Construir XML de staging ligero ──────────────────────────────────────
    lines_root = etree.Element("lines")
    for tl_id, text in line_texts:
        line_elem = etree.SubElement(lines_root, "line")
        line_elem.set("id", tl_id)
        line_elem.text = text

    output_path.parent.mkdir(parents=True, exist_ok=True)
    staging_tree = etree.ElementTree(lines_root)
    staging_tree.write(str(output_path), encoding="UTF-8", xml_declaration=True,
                       pretty_print=True)
    print(f"✓ Guardado: {output_path}", file=sys.stderr)


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description="Normaliza PAGE XML de Transkribus para el pipeline editorial"
    )
    ap.add_argument("input", help="Archivo PAGE XML de transkribus/")
    ap.add_argument("--out", default=None,
                    help="Ruta de salida (default: staging/<misma estructura>)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Mostrar cambios sin escribir el archivo")
    args = ap.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: no existe {input_path}", file=sys.stderr)
        sys.exit(1)

    if args.out:
        output_path = Path(args.out)
    else:
        # transkribus/disp63/pg_63_35_der.xml → staging/disp63/pg_63_35_der.xml
        try:
            rel = input_path.relative_to("transkribus")
            output_path = Path("staging") / rel
        except ValueError:
            output_path = Path("staging") / input_path.name

    normalize(input_path, output_path, args.dry_run)


if __name__ == "__main__":
    main()
