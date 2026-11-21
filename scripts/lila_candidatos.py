#!/usr/bin/env python3
"""Candidatos de LiLa para una o varias formas: categoría, género, flexión,
formas escritas y familia (palabras de la misma base). Para resolver los
«elegir lema» y «categoría distinta» de la revisión.
Uso: python3 scripts/lila_candidatos.py panis [tempus …]"""
import sys, re
txt = open("cache/lemmaBank.ttl", encoding="utf-8").read()
bloques = re.findall(r"\n(lilaLemma:\d+\b.*?\.\s*)(?=\n\S)", txt, flags=re.S)
for forma in sys.argv[1:]:
    cands = [b for b in bloques if re.search(rf'"{re.escape(forma)}"@la', b)]
    print(f"══ «{forma}»: {len(cands)} candidatos")
    for b in cands:
        pos = re.search(r"hasPOS\s+lila:(\w+)", b)
        gen = re.search(r"hasGender\s+lila:(\w+)", b)
        inf = re.search(r"hasInflectionType\s+lila:(\w+)", b)
        reps = re.findall(r'"([^"]+)"@la', b)
        print(f"  {b.split()[0]}  pos={pos and pos.group(1)}  género={gen and gen.group(1)}  "
              f"flexión={inf and inf.group(1)}  formas={reps}")
        for base in re.findall(r"lilaBase:\d+", b):
            fam = sorted({w for x in bloques if re.search(rf"hasBase[^;.]*\b{base}\b", x)
                          for w in re.findall(r'writtenRep[^;.]*?"([^"]+)"@la', x)})
            print(f"     {base}: {len(fam)} → {', '.join(fam[:12])}{' …' if len(fam) > 12 else ''}")
        for v in re.findall(r"lemmaVariant\s+(lilaLemma:\d+)", b):
            m = re.search(rf"\n{re.escape(v)}\b.*?\"([^\"]+)\"@la", txt, flags=re.S)
            print(f"     variante {v}: {m.group(1) if m else '?'}")
    print()
