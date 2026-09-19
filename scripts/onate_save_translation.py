#!/usr/bin/env python3
"""
onate_save_translation.py — Guarda o actualiza la traducción de una oración
puntual en translations/disp63/<stem>.json, creando el archivo si no existe.

Uso:
    python3 onate_save_translation.py <translations_json> <n> "<text in English>"
"""
import argparse
import json
import os


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("translations_json")
    ap.add_argument("n", type=int)
    ap.add_argument("en")
    args = ap.parse_args()

    data = {"sentences": []}
    if os.path.exists(args.translations_json):
        with open(args.translations_json, encoding="utf-8") as f:
            data = json.load(f)

    sentences = data.get("sentences", [])
    for s in sentences:
        if s["n"] == args.n:
            s["en"] = args.en
            break
    else:
        sentences.append({"n": args.n, "en": args.en})

    sentences.sort(key=lambda s: s["n"])
    data["sentences"] = sentences

    os.makedirs(os.path.dirname(args.translations_json), exist_ok=True)
    with open(args.translations_json, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"Guardado §{args.n} en {args.translations_json} ({len(sentences)} oraciones en total).")


if __name__ == "__main__":
    main()
