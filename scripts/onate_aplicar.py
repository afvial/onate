#!/usr/bin/env python3
"""
Aplica las decisiones de revisión de una columna, anotadas en
correcciones/disp63/pg_63_P_C.tsv (separado por tabuladores):

    linea       original    nuevo                 page   nota
    tr_1_tl_2   imputent    imputēt                      macrón
    tr_1_tl_4   @Corrad.    @{Corrad.|Conrad.}           errata
    tr_1_tl_8   Cinopem     [inopē                       corchete leído C

- Staging: sustituye «original» por «nuevo» en esa línea (primera aparición).
- PAGE XML (columna «page»): «si» siempre, «no» nunca; vacía = automático,
  solo si cambia la lectura y no solo las marcas editoriales (macrones, ſ,
  @ * // ¶ ^ ~ ¬, [-…] [=…], {sic|corr}). Si cambia el número de palabras,
  corrige el texto de la línea y avisa de que hay que revisar las cajas.
- Si alguna corrección falla, no escribe nada.

Uso: python3 scripts/onate_aplicar.py 47 der [--dry-run] [--procesar]
"""
import argparse, csv, re, subprocess, sys, unicodedata
from pathlib import Path
from lxml import etree

sys.path.insert(0, str(Path(__file__).parent))
try:
    from onate_tei import _expand_macrons
except Exception:
    _expand_macrons = lambda t: None

NS = "http://schema.primaresearch.org/PAGE/gts/pagecontent/2013-07-15"
T = lambda n: f"{{{NS}}}{n}"
PUNT = ".,;:"


def impreso(t: str) -> str:
    """Forma impresa sin marcas editoriales (lo que va al PAGE XML)."""
    t = t.replace("&amp;", "&")
    t = re.sub(r"\{([^|{}]*)\|[^{}]*\}", r"\1", t)     # {sic|corr} → sic
    t = re.sub(r"\[[-+=][^\]]*\]", "", t)               # [-x] [+x] [=x]
    t = re.sub(r"\{_\d*\}", "", t)                      # huecos {_}
    t = t.replace("//", "").replace("¶", "")
    t = re.sub(r"[@*^¬~]", "", t)
    return re.sub(r"\s+", " ", t).strip()


def lectura(t: str) -> str:
    """Para comparar: forma impresa con macrones expandidos, sin ſ ni ligaduras (los acentos sí cuentan)."""
    t = " ".join((_expand_macrons(w) or w) for w in impreso(t).split())
    for a, b in (("ſ", "s"), ("æ", "ae"), ("Æ", "Ae"), ("œ", "oe"), ("Œ", "Oe"), ("ę", "ae")):
        t = t.replace(a, b)
    return t   # los acentos (planè, è) cuentan como lectura: van también al PAGE XML


def xml_esc(t: str) -> str:
    return t.replace("&amp;", "&").replace("&", "&amp;")


def main():
    ap = argparse.ArgumentParser(description="Aplica correcciones/disp63/pg_63_P_C.tsv")
    ap.add_argument("pagina"); ap.add_argument("columna")
    ap.add_argument("--dry-run", action="store_true", help="muestra los cambios sin escribir")
    ap.add_argument("--procesar", action="store_true", help="procesa la página al terminar")
    a = ap.parse_args()

    stem = f"pg_63_{a.pagina}_{a.columna}"
    tsv = Path(f"correcciones/disp63/{stem}.tsv")
    if not tsv.exists():
        tsv.parent.mkdir(parents=True, exist_ok=True)
        tsv.write_text("linea\toriginal\tnuevo\tpage\tnota\n", encoding="utf-8")
        sys.exit(f"Creada la plantilla {tsv}: rellénala y vuelve a ejecutar.")

    import subprocess as _sp
    _sp.run([sys.executable, str(Path(__file__).parent / "onate_ordenar_correcciones.py"), a.pagina, a.columna],
            stdout=_sp.DEVNULL)
    st_path = Path(f"staging/disp63/{stem}.xml")
    pg_path = Path(f"transkribus/disp63/{stem}.xml")
    s = st_path.read_text(encoding="utf-8")
    tree = etree.parse(str(pg_path))
    U = lambda el: el.find(f"{T('TextEquiv')}/{T('Unicode')}")

    with tsv.open(encoding="utf-8") as f:
        filas = [r for r in csv.DictReader(f, delimiter="\t")
                 if (r.get("linea") or "").strip() and not r["linea"].startswith("#")]

    ok = err = pg = 0
    hechas = set()
    for r in filas:
        lid, orig, nuevo = r["linea"].strip(), r["original"], r["nuevo"]
        modo = (r.get("page") or "").strip().lower()
        m = re.search(rf'(<line id="{re.escape(lid)}">)([^<]*)(</line>)', s)
        if not m:
            print(f"✗ {lid}: no existe la línea en el staging"); err += 1; continue
        texto = m.group(2)
        if xml_esc(nuevo) in texto:
            print(f"· {lid}: ya estaba aplicado «{nuevo}»")
            continue
        if xml_esc(orig) not in texto:
            if xml_esc(nuevo) in texto:
                print(f"· {lid}: ya estaba aplicado «{nuevo}»")
            else:
                print(f"✗ {lid}: no encuentro «{orig}» en «{texto}»"); err += 1
            continue
        s = s[:m.start(2)] + texto.replace(xml_esc(orig), xml_esc(nuevo), 1) + s[m.end(2):]
        ok += 1
        hechas.add((lid, orig, nuevo))

        if modo == "no" or (modo != "si" and lectura(orig) == lectura(nuevo)):
            print(f"✓ {lid}: «{orig}» → «{nuevo}»   (solo staging)"); continue
        line = tree.find(f".//{T('TextLine')}[@id='{lid}']")
        if line is None:
            print(f"⚠ {lid}: «{orig}» → «{nuevo}»   (no está en el PAGE XML)"); continue
        po, pn = impreso(orig), impreso(nuevo)
        te = U(line)
        if te is not None and te.text and po in te.text:
            te.text = te.text.replace(po, pn, 1)
        pg += 1
        if len(po.split()) != len(pn.split()):
            print(f"✓ {lid}: «{orig}» → «{nuevo}»   (PAGE: texto de la línea; ⚠ cambia el nº de palabras: revisar cajas)")
            continue
        hecho = True
        for wo, wn in zip(po.split(), pn.split()):
            if wo == wn:
                continue
            co, cn = wo.rstrip(PUNT), wn.rstrip(PUNT)
            for w in line.findall(T("Word")):
                u = U(w)
                if u is not None and (u.text or "").rstrip(PUNT) == co:
                    u.text = u.text.replace(co, cn, 1); break
            else:
                hecho = False
        print(f"✓ {lid}: «{orig}» → «{nuevo}»   (PAGE: {'palabra y línea' if hecho else 'línea; ⚠ palabra no encontrada'})")

    print(f"\n{ok} aplicadas · {err} con error · {pg} también en el PAGE XML")
    if a.dry_run:
        print("(dry-run: no se ha escrito nada)"); return
    if err:
        sys.exit("Hay errores: no se ha escrito nada. Corrige el TSV y vuelve a ejecutar.")
    st_path.write_text(s, encoding="utf-8")
    tree.write(str(pg_path), encoding="UTF-8", xml_declaration=True)
    print(f"Escritos {st_path} y {pg_path}")
    lineas_tsv = tsv.read_text(encoding="utf-8").splitlines()
    marcadas = 0
    for k, l in enumerate(lineas_tsv):
        c = l.split("\t")
        if len(c) >= 3 and not l.startswith("#") and (c[0].strip(), c[1], c[2]) in hechas:
            lineas_tsv[k] = "#✓" + l; marcadas += 1
    tsv.write_text("\n".join(lineas_tsv) + "\n", encoding="utf-8")
    print(f"{marcadas} filas marcadas como hechas (#✓) en {tsv}")
    if a.procesar:
        subprocess.run(["./procesar_pagina.sh", a.pagina, a.columna, "--skip", "search,rdf"])


if __name__ == "__main__":
    main()
