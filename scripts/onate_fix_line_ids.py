#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
onate_fix_line_ids.py
─────────────────────
Renombra las TextLine añadidas a mano en Transkribus (id="l", "l_1", …)
al patrón tr_1_tl_N, en el PAGE XML y en el staging a la vez.

Uso:
    python3 scripts/onate_fix_line_ids.py 52 der
    python3 scripts/onate_fix_line_ids.py 52          # ambas columnas
    python3 scripts/onate_fix_line_ids.py 52 der --dry-run

Numera a partir del tr_1_tl_N más alto del archivo, en orden de aparición.
Si el staging no existe todavía, solo corrige el PAGE XML.
No toca nada si un id raro no aparece exactamente una vez en el staging.
"""
import re
import sys
import argparse
from pathlib import Path


def fix(page, col, dry_run=False):
    tk = Path(f"transkribus/disp63/pg_63_{page}_{col}.xml")
    st = Path(f"staging/disp63/pg_63_{page}_{col}.xml")
    if not tk.exists():
        print(f"{col}: no existe {tk}")
        return
    t = tk.read_text(encoding="utf-8")
    s = st.read_text(encoding="utf-8") if st.exists() else None

    odd = [i for i in re.findall(r'<TextLine id="([^"]+)"', t)
           if not re.fullmatch(r"tr_1_tl_\d+", i)]
    if not odd:
        print(f"{col}: sin ids raros")
        return
    if s is not None:
        for old in odd:
            if s.count(f'<line id="{old}">') != 1:
                print(f'{col}: "{old}" no aparece exactamente una vez en el '
                      f"staging; no se cambia nada")
                return

    n = max((int(x) for x in re.findall(r'id="tr_1_tl_(\d+)"', t)), default=0)
    for old in odd:
        n += 1
        new = f"tr_1_tl_{n}"
        t = t.replace(f'<TextLine id="{old}"', f'<TextLine id="{new}"')
        t = re.sub(rf'<Word id="{re.escape(old)}_w(\d+)"',
                   rf'<Word id="{new}_w\1"', t)
        if s is not None:
            s = s.replace(f'<line id="{old}">', f'<line id="{new}">')
        print(f"{col}: {old} → {new}")

    order = re.findall(
        r'TextLine id="([^"]+)" custom="readingOrder \{index:(\d+);\}', t)[-4:]
    print(f"{col}: últimas líneas (id, índice): {order}")
    if dry_run:
        print(f"{col}: --dry-run, no se escribe nada")
        return
    tk.write_text(t, encoding="utf-8")
    if s is not None:
        st.write_text(s, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[3])
    ap.add_argument("page")
    ap.add_argument("col", nargs="?", choices=["izq", "der"])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    for col in ([a.col] if a.col else ["izq", "der"]):
        fix(a.page, col, a.dry_run)


if __name__ == "__main__":
    main()
