#!/usr/bin/env python3
"""
onate_sense_report.py — Recorre senses/disp63/*.json y arma una concordancia
por lema: cada synset asignado, sus ocurrencias, y cómo se tradujo esa
oración al español — para comparar consistencia de traducción de un mismo
término a través del corpus.

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
                translations = {s["n"]: s["en"] for s in json.load(f)["sentences"]}

        for entry in data.get("senses", []):
            entry = dict(entry)
            entry["stem"] = stem
            entry["en"] = translations.get(entry["sentence"], "(sin traducción guardada)")
            by_lemma[entry["lemma"]].append(entry)

    lines = ["# Concordancia de sentidos — Disp. LXIII\n"]
    lines.append(f"{sum(len(v) for v in by_lemma.values())} ocurrencias ancladas, "
                  f"{len(by_lemma)} lema(s) distinto(s).\n")

    for lemma in sorted(by_lemma):
        entries = by_lemma[lemma]
        synsets = sorted(set(e["synset"] for e in entries))
        lines.append(f"\n## {lemma}  ({len(entries)} ocurrencia(s), {len(synsets)} sentido(s) distinto(s))\n")
        for synset in synsets:
            sample = next(e for e in entries if e["synset"] == synset)
            lines.append(f"\n### {synset} — *{sample.get('synset_name','')}*")
            lines.append(f"> {sample.get('synset_def','')}\n")
            lines.append("| Página/col | §  | Forma | Translation (EN) |")
            lines.append("|---|---|---|---|")
            for e in entries:
                if e["synset"] != synset:
                    continue
                en_short = e["en"][:90] + ("…" if len(e["en"]) > 90 else "")
                lines.append(f"| {e['stem']} | {e['sentence']} | {e['text']} | {en_short} |")

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"OK: {len(by_lemma)} lema(s) -> {args.out}")


if __name__ == "__main__":
    main()
