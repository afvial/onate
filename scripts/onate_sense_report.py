#!/usr/bin/env python3
"""
onate_sense_report.py — Recorre senses/disp63/*.json y arma una concordancia
por lema: cada sentido distinto anclado a LiLa (o pendiente), sus
ocurrencias, y cómo se tradujo esa oración al inglés — para comparar
consistencia de traducción de un mismo término a través del corpus.

Uso:
    python3 onate_sense_report.py [--senses-dir senses/disp63]
                                   [--trans-dir translations/disp63]
                                   [--out output/disp63_sense_concordance.md]
"""
import argparse
import glob
import json
import os
from collections import defaultdict


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--senses-dir", default="senses/disp63")
    ap.add_argument("--trans-dir", default="translations/disp63")
    ap.add_argument("--out", default="output/disp63_sense_concordance.md")
    args = ap.parse_args()

    by_lemma = defaultdict(list)

    for path in sorted(glob.glob(os.path.join(args.senses_dir, "*.json"))):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        stem = os.path.splitext(os.path.basename(path))[0]

        trans_path = os.path.join(args.trans_dir, f"{stem}.json")
        translations = {}
        if os.path.exists(trans_path):
            with open(trans_path, encoding="utf-8") as f:
                translations = {s["n"]: s["es"] for s in json.load(f)["sentences"]}

        for entry in data.get("senses", []):
            entry = dict(entry)
            entry["stem"] = stem
            entry["es"] = translations.get(entry["sentence"], "(sin traducción guardada)")
            by_lemma[entry["lemma"]].append(entry)

    lines = ["# Concordancia de sentidos — Disp. LXIII\n"]
    lines.append(f"{sum(len(v) for v in by_lemma.values())} ocurrencias ancladas, "
                  f"{len(by_lemma)} lema(s) distinto(s).\n")

    for lemma in sorted(by_lemma):
        entries = by_lemma[lemma]
        # Un "sentido" se identifica por su lila_uri; si aún no tiene URI,
        # se agrupa por el gloss_en (para no perder de vista lo pendiente).
        def sense_key(e):
            return e.get("lila_uri") or f"(pendiente) {e.get('gloss_en','')}"

        senses = sorted(set(sense_key(e) for e in entries))
        lines.append(f"\n## {lemma}  ({len(entries)} ocurrencia(s), {len(senses)} sentido(s) distinto(s))\n")
        for key in senses:
            sample = next(e for e in entries if sense_key(e) == key)
            lila_uri = sample.get("lila_uri")
            if lila_uri:
                lines.append(f"\n### [{sample.get('gloss_en','')}]({lila_uri})")
                lines.append(f"↗ {lila_uri}\n")
            else:
                lines.append(f"\n### {sample.get('gloss_en','')}  *(lila_uri pendiente)*\n")
            if sample.get("lila_def"):
                lines.append(f"> {sample['lila_def']}\n")
            if sample.get("note"):
                lines.append(f"*{sample['note']}*\n")
            lines.append("| Página/col | §  | Forma | Traducción |")
            lines.append("|---|---|---|---|")
            for e in entries:
                if sense_key(e) != key:
                    continue
                es_short = e["es"][:90] + ("…" if len(e["es"]) > 90 else "")
                lines.append(f"| {e['stem']} | {e['sentence']} | {e['text']} | {es_short} |")

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"OK: {len(by_lemma)} lema(s) -> {args.out}")


if __name__ == "__main__":
    main()
