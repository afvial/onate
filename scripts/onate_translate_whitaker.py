#!/usr/bin/env python3
"""
onate_translate_whitaker.py — Traduce lemas latinos usando Whitaker's Words.

Toma el JSON producido por onate_ls_lookup.py y genera un CSV con
traducciones al inglés para cada lema. No requiere API ni conexión
a internet — usa el archivo DICTLINE.GEN de Whitaker's Words localmente.

El archivo DICTLINE.GEN debe estar en el mismo directorio que el script,
o se puede especificar con --dictline. Se puede descargar con:
    curl -sL https://raw.githubusercontent.com/ArchimedesDigital/open_words/master/open_words/data/DICTLINE.GEN -o scripts/DICTLINE.GEN

Uso:
    python3 onate_translate_whitaker.py translations_39_izq.json
    python3 onate_translate_whitaker.py translations_39_izq.json --out translations_en.csv
    python3 onate_translate_whitaker.py translations_39_izq.json --max-senses 2
"""

import argparse
import csv
import json
import re
import sys
from pathlib import Path


def parse_dictline(path: Path) -> list:
    """
    Carga DICTLINE.GEN y devuelve lista de (stem1, stem2, definición).
    Formato de cada línea:
        stem1(19) stem2(19) stem3(19) stem4(19) POS info... definición;
    """
    entries = []
    with open(path, encoding="latin-1") as f:
        for line in f:
            line = line.rstrip("\r\n")
            if len(line) < 100:
                continue
            s1 = line[0:19].strip().lower()
            s2 = line[19:38].strip().lower()
            rest = line[76:].strip()
            # La definición son las palabras en minúsculas después de los
            # códigos en mayúsculas
            m = re.search(r'[a-z].*', rest)
            defn = m.group(0).rstrip(";").strip() if m else ""
            if s1 and defn:
                entries.append((
                    s1.replace("j", "i").replace("v", "u"),
                    s2.replace("j", "i").replace("v", "u"),
                    defn
                ))
    return entries


def find_lemma(lemma: str, entries: list) -> str | None:
    """
    Busca el stem más largo que sea prefijo del lema.
    El stem de Whitaker es el lema sin la desinencia flexiva,
    así que el lema siempre empieza por el stem.
    """
    lemma_n = lemma.lower().replace("j", "i").replace("v", "u")
    best_defn = None
    best_len  = 0
    for s1, s2, defn in entries:
        for stem in [s1, s2]:
            if not stem:
                continue
            if lemma_n.startswith(stem) and len(stem) > best_len:
                best_defn = defn
                best_len  = len(stem)
    return best_defn


def shorten(defn: str, max_senses: int) -> str:
    """Devuelve las primeras max_senses acepciones separadas por '; '."""
    parts = [p.strip() for p in defn.split(";") if p.strip()]
    return "; ".join(parts[:max_senses])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input",     type=Path,
                    help="JSON de onate_ls_lookup.py")
    ap.add_argument("--out",     type=Path, default=None,
                    help="CSV de salida (default: <input>_whitaker.csv)")
    ap.add_argument("--dictline", type=Path, default=None,
                    help="Ruta a DICTLINE.GEN (default: mismo dir que el script)")
    ap.add_argument("--max-senses", type=int, default=3,
                    help="Número máximo de acepciones (default: 3)")
    args = ap.parse_args()

    out_path = args.out or args.input.with_name(
        args.input.stem + "_whitaker.csv"
    )

    # Localizar DICTLINE.GEN
    dictline = args.dictline or (Path(__file__).parent / "DICTLINE.GEN")
    if not dictline.exists():
        sys.exit(
            f"ERROR: no se encuentra {dictline}\n"
            f"Descárgalo con:\n"
            f"  curl -sL https://raw.githubusercontent.com/ArchimedesDigital/"
            f"open_words/master/open_words/data/DICTLINE.GEN "
            f"-o scripts/DICTLINE.GEN"
        )

    # Cargar diccionario
    print(f"Cargando Whitaker's Words ({dictline.name})...", file=sys.stderr)
    entries = parse_dictline(dictline)
    print(f"  {len(entries)} entradas", file=sys.stderr)

    # Cargar lemas
    with open(args.input, encoding="utf-8") as f:
        data = json.load(f)
    items = list(data.values()) if isinstance(data, dict) else data

    # Filtrar números puros
    items = [i for i in items
             if not str(i.get("lemma", "")).strip().isdigit()]

    print(f"Lemas a traducir: {len(items)}", file=sys.stderr)

    # Traducir
    rows = []
    found = not_found = 0

    for item in items:
        lemma = item.get("lemma", "")
        pos   = item.get("pos", "")

        defn = find_lemma(lemma, entries)
        if defn:
            found += 1
            translation = shorten(defn, args.max_senses)
        else:
            not_found += 1
            translation = ""

        rows.append({
            "lemma":       lemma,
            "pos":         pos,
            "translation": translation,
            "all_senses":  defn or "",
            "ls_short":    item.get("short_def", "")[:100],
            "ls_found":    item.get("found", False),
        })

    pct = 100 * found // max(len(items), 1)
    print(f"  Encontrados:   {found} / {len(items)} ({pct}%)",
          file=sys.stderr)
    print(f"  Sin cobertura: {not_found}", file=sys.stderr)

    # Escribir CSV
    fieldnames = ["lemma", "pos", "translation", "all_senses",
                  "ls_short", "ls_found"]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"→ {out_path}", file=sys.stderr)

    # Mostrar los que no se encontraron
    missing = [r["lemma"] for r in rows if not r["translation"]]
    if missing:
        print(f"\nSin traducción ({len(missing)}):", file=sys.stderr)
        for m in missing:
            print(f"  {m}", file=sys.stderr)


if __name__ == "__main__":
    main()
