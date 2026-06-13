#!/usr/bin/env python3
"""
onate_ls_lookup.py — Lookup de lemas latinos en el Lewis & Short (Perseus)

Dado un archivo TEI del proyecto Oñate, extrae todos los lemas únicos
y devuelve sus definiciones del Lewis & Short como JSON o CSV.

Uso:
    python3 onate_ls_lookup.py src/disp63/pg_63_39_izq.xml
    python3 onate_ls_lookup.py src/disp63/pg_63_39_izq.xml --format csv
    python3 onate_ls_lookup.py src/disp63/pg_63_39_izq.xml --out translations.json

El índice ls_index.json debe estar en el mismo directorio que este script,
o se puede especificar con --index.

Fuente del diccionario:
    Lewis & Short (1879), Perseus Digital Library.
    Licencia: CC BY-SA 3.0
"""

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from lxml import etree

TEI_NS = "http://www.tei-c.org/ns/1.0"

# ── Normalización ortográfica ──────────────────────────────────────────────────

def normalize_lemma(lemma: str) -> list[str]:
    """
    Genera variantes ortográficas de un lema para buscar en el Lewis & Short.
    El L&S usa 'j' inicial y 'v' consonántica; los lemas del TEI usan 'i/u'.
    """
    lemma = lemma.lower().strip()
    variants = set()
    variants.add(lemma)

    # i inicial -> j  (iustitia -> justitia)
    v1 = re.sub(r'^i', 'j', lemma)
    variants.add(v1)

    # v -> u  (indiuisibilis -> indivisibilis)
    v2 = lemma.replace("v", "u")
    variants.add(v2)
    variants.add(re.sub(r'^i', 'j', v2))

    # u -> v
    v3 = lemma.replace("u", "v")
    variants.add(v3)

    # ae -> e  (aestimatio -> estimatio — raro pero por si acaso)
    v4 = lemma.replace("ae", "e")
    variants.add(v4)

    # añadir sufijo numérico para homógrafos
    for v in list(variants):
        variants.add(v + "1")
        variants.add(v + "2")

    return list(variants)


# ── Carga del índice ───────────────────────────────────────────────────────────

def load_index(index_path: Path) -> dict:
    with open(index_path, encoding="utf-8") as f:
        return json.load(f)


def lookup(lemma: str, index: dict) -> dict | None:
    """
    Busca un lema en el índice y devuelve {'key': ..., 'short': ..., 'full': ...}
    o None si no se encuentra.
    """
    for variant in normalize_lemma(lemma):
        if variant in index:
            entry = index[variant]
            return {
                "key":   variant,
                "short": entry.get("short", ""),
                "full":  entry.get("full", ""),
            }
    return None


# ── Extracción de lemas del TEI ────────────────────────────────────────────────

def extract_lemmas(tei_path: Path) -> list[tuple[str, str]]:
    """
    Devuelve lista de (lemma, pos) únicos del archivo TEI.
    """
    parser = etree.XMLParser(recover=True)
    tree = etree.parse(str(tei_path), parser)

    seen = set()
    results = []

    for w in tree.findall(f".//{{{TEI_NS}}}w"):
        lemma = w.get("lemma", "").strip()
        pos   = w.get("pos", "").strip()
        if lemma and lemma not in seen:
            seen.add(lemma)
            results.append((lemma, pos))

    return sorted(results)


# ── Output ─────────────────────────────────────────────────────────────────────

def to_json(rows: list[dict], out_path: Path | None):
    data = {r["lemma"]: r for r in rows}
    text = json.dumps(data, ensure_ascii=False, indent=2)
    if out_path:
        out_path.write_text(text, encoding="utf-8")
        print(f"→ {out_path}", file=sys.stderr)
    else:
        print(text)


def to_csv(rows: list[dict], out_path: Path | None):
    fields = ["lemma", "pos", "ls_key", "short_def", "found"]
    if out_path:
        fh = open(out_path, "w", newline="", encoding="utf-8")
    else:
        fh = sys.stdout

    writer = csv.DictWriter(fh, fieldnames=fields)
    writer.writeheader()
    for r in rows:
        writer.writerow({
            "lemma":     r["lemma"],
            "pos":       r["pos"],
            "ls_key":    r.get("ls_key", ""),
            "short_def": r.get("short_def", ""),
            "found":     r["found"],
        })

    if out_path:
        fh.close()
        print(f"→ {out_path}", file=sys.stderr)


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("tei",    type=Path, help="Archivo TEI de entrada")
    ap.add_argument("--index", type=Path, default=None,
                    help="Ruta al ls_index.json (default: mismo directorio que el script)")
    ap.add_argument("--format", choices=["json", "csv"], default="json")
    ap.add_argument("--out",   type=Path, default=None,
                    help="Archivo de salida (default: stdout)")
    args = ap.parse_args()

    # Localizar índice
    index_path = args.index or (Path(__file__).parent / "ls_index.json")
    if not index_path.exists():
        sys.exit(f"ERROR: no se encuentra {index_path}\n"
                 f"Descarga el Lewis & Short con:\n"
                 f"  python3 onate_build_ls_index.py")

    print(f"Cargando índice Lewis & Short...", file=sys.stderr)
    index = load_index(index_path)
    print(f"  {len(index)} entradas", file=sys.stderr)

    # Extraer lemas
    lemmas = extract_lemmas(args.tei)
    print(f"Lemas únicos en {args.tei.name}: {len(lemmas)}", file=sys.stderr)

    # Lookup
    rows = []
    found = not_found = 0
    for lemma, pos in lemmas:
        entry = lookup(lemma, index)
        if entry:
            found += 1
            rows.append({
                "lemma":     lemma,
                "pos":       pos,
                "ls_key":    entry["key"],
                "short_def": entry["short"],
                "full_def":  entry["full"],
                "found":     True,
            })
        else:
            not_found += 1
            rows.append({
                "lemma":   lemma,
                "pos":     pos,
                "ls_key":  "",
                "short_def": "",
                "full_def":  "",
                "found":   False,
            })

    print(f"  Encontrados: {found} / {len(lemmas)} "
          f"({100*found//len(lemmas)}%)", file=sys.stderr)
    print(f"  Sin cobertura: {not_found}", file=sys.stderr)

    # Output
    if args.format == "json":
        to_json(rows, args.out)
    else:
        to_csv(rows, args.out)


if __name__ == "__main__":
    main()
