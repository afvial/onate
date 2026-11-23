#!/usr/bin/env python3
"""
Ordena correcciones/disp63/pg_63_P_C.tsv por número de línea.
Cabecera arriba; filas comentadas (#) en su línea; orden relativo conservado
dentro de cada línea; filas sin número de línea al final.
Uso: python3 scripts/onate_ordenar_correcciones.py 49 izq
"""
import re, sys
from pathlib import Path
p = Path(f"correcciones/disp63/pg_63_{sys.argv[1]}_{sys.argv[2]}.tsv")
lineas = p.read_text(encoding="utf-8").splitlines()
cab = [l for l in lineas if l.startswith("linea\t")][:1] or ["linea\toriginal\tnuevo\tpage\tnota"]
def clave(item):
    k, l = item
    m = re.match(r"#?tr_1_tl_(\d+)\t", l)
    return (0, int(m.group(1)), k) if m else (1, 0, k)
resto = [(k, l) for k, l in enumerate(lineas) if not l.startswith("linea\t") and l.strip()
         and not re.match(r"#\s*──", l)]
p.write_text("\n".join(cab + [l for _, l in sorted(resto, key=clave)]) + "\n", encoding="utf-8")
print(f"ordenado {p} ({len(resto)} filas)")
