#!/usr/bin/env python3
"""
onate_translate.py — Traduce lemas latinos al inglés usando Claude API.

Toma el JSON producido por onate_ls_lookup.py y genera un CSV con una
traducción breve al inglés para cada lema, usando la definición del
Lewis & Short como contexto y teniendo en cuenta el registro escolástico
del corpus de Oñate (s. XVII).

Uso:
    python3 onate_translate.py translations_39_izq.json
    python3 onate_translate.py translations_39_izq.json --out translations_39_izq_en.csv
    python3 onate_translate.py translations_39_izq.json --batch 20

El script procesa los lemas en lotes para no sobrecargar la API.
Los lemas ya traducidos en una ejecución anterior se omiten si
se especifica --resume con el CSV de salida existente.
"""

import argparse
import csv
import json
import sys
import time
from pathlib import Path

import anthropic

SYSTEM_PROMPT = """You are a Latin-English translator specializing in
Scholastic philosophy and theology of the 17th century.

Your task: given a list of Latin lemmas (dictionary forms) with their
Part-of-Speech and — when available — their Lewis & Short dictionary
definition, provide a SHORT English translation for each lemma.

Rules:
- 1–4 words maximum per translation (e.g. "price, value" or "justice")
- Use terminology appropriate for Scholastic philosophy (Oñate, De Iustitia
  et Iure, 1646): prefer "just price" over "fair price", "estimation" over
  "assessment", etc.
- For proper nouns (authors, place names): write the conventional English
  or Latinized form (e.g. "Aristotle", "Conrad")
- For numbers or particles with no semantic content: write "-"
- Respond ONLY with a JSON object: {"lemma1": "translation1", ...}
- No preamble, no explanation, no markdown fences."""


def load_ls_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_existing_csv(path: Path) -> dict:
    """Carga traducciones ya hechas de un CSV previo."""
    existing = {}
    if path.exists():
        with open(path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("translation"):
                    existing[row["lemma"]] = row["translation"]
    return existing


def translate_batch(client: anthropic.Anthropic,
                    batch: list[dict]) -> dict:
    """
    Envía un lote de lemas a Claude y devuelve {lemma: translation}.
    """
    # Construir el mensaje de entrada
    lines = []
    for item in batch:
        ls_def = item.get("short_def", "").strip()
        # Limpiar diacríticos del L&S de la forma de cita
        ls_preview = ls_def[:120] if ls_def else "(no L&S entry)"
        lines.append(
            f'- "{item["lemma"]}" ({item["pos"]}): {ls_preview}'
        )

    user_msg = (
        "Translate these Latin lemmas to English "
        "(Scholastic philosophy context):\n\n"
        + "\n".join(lines)
    )

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )

    raw = response.content[0].text.strip()

    # Limpiar posibles ```json ... ``` si los hay
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        print(f"  ⚠ JSON inválido en respuesta, reintentando...",
              file=sys.stderr)
        print(f"  Raw: {raw[:200]}", file=sys.stderr)
        return {}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input",  type=Path,
                    help="JSON de onate_ls_lookup.py")
    ap.add_argument("--out",  type=Path, default=None,
                    help="CSV de salida (default: <input>_en.csv)")
    ap.add_argument("--batch", type=int, default=25,
                    help="Lemas por llamada a la API (default: 25)")
    ap.add_argument("--resume", action="store_true",
                    help="Retomar traducción anterior si existe el CSV")
    ap.add_argument("--only-found", action="store_true",
                    help="Traducir solo los lemas con entrada en el L&S")
    args = ap.parse_args()

    # Archivo de salida
    out_path = args.out or args.input.with_name(
        args.input.stem + "_en.csv"
    )

    # Cargar datos
    data = load_ls_json(args.input)
    # El JSON puede ser {lemma: {...}} o [{lemma:..., pos:..., ...}]
    if isinstance(data, dict):
        items = list(data.values())
    else:
        items = data

    # Filtrar si se pide
    if args.only_found:
        items = [i for i in items if i.get("found")]

    # Excluir números puros
    items = [i for i in items
             if not str(i.get("lemma", "")).strip().isdigit()]

    print(f"Lemas a traducir: {len(items)}", file=sys.stderr)

    # Cargar traducciones previas si --resume
    existing = {}
    if args.resume:
        existing = load_existing_csv(out_path)
        print(f"  Ya traducidos: {len(existing)}", file=sys.stderr)

    # Filtrar los ya traducidos
    pending = [i for i in items
               if i.get("lemma") not in existing]
    print(f"  Pendientes: {len(pending)}", file=sys.stderr)

    # Cliente Anthropic
    client = anthropic.Anthropic()

    # Procesar en lotes
    results = dict(existing)
    total_batches = (len(pending) + args.batch - 1) // args.batch

    for batch_i in range(total_batches):
        batch = pending[batch_i * args.batch:(batch_i + 1) * args.batch]
        print(f"  Lote {batch_i+1}/{total_batches} "
              f"({len(batch)} lemas)...", file=sys.stderr)

        translations = translate_batch(client, batch)

        for item in batch:
            lemma = item["lemma"]
            results[lemma] = translations.get(lemma, "")

        # Pausa entre lotes para no saturar la API
        if batch_i < total_batches - 1:
            time.sleep(0.5)

    # Escribir CSV
    fieldnames = ["lemma", "pos", "translation", "ls_key",
                  "short_def", "found"]

    # Reconstruir con orden original
    rows = []
    for item in items:
        lemma = item.get("lemma", "")
        rows.append({
            "lemma":      lemma,
            "pos":        item.get("pos", ""),
            "translation": results.get(lemma, ""),
            "ls_key":     item.get("ls_key", ""),
            "short_def":  item.get("short_def", "")[:120],
            "found":      item.get("found", False),
        })

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"→ {out_path}  ({len(rows)} lemas)", file=sys.stderr)
    print(f"  Traducidos: {sum(1 for r in rows if r['translation'])}",
          file=sys.stderr)


if __name__ == "__main__":
    main()
