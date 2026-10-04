#!/usr/bin/env python3
"""
onate_lila.py — Etapa `lila`: enlaza cada <w lemma pos> con el LiLa Lemma Bank.

Añade @lemmaRef (p. ej. lemmaRef="lila:107402") a todos los <w> con @lemma.
Como LatinCy deja el mismo lema en <orig>/<reg> (y en <expan>, <corr>),
el enlace queda coherente sin emparejar nada: se resuelve por (lema, POS).

Se ejecuta después de `nlp`, sobre los archivos de página de src/. Es
determinista: en cada ejecución recalcula todos los lemmaRef a partir de
  1) cache/lila_index.json   (generado por onate_lila_index.py)
  2) lila/excepciones.tsv    (tus decisiones manuales; tienen prioridad)
así que regenerar una página con page2tei/nlp no pierde nada.

Informes de lo que no se pudo enlazar automáticamente:
  lila/pendientes.tsv          GLOBAL, una fila por (lema, POS), con páginas y
                               líneas: para decisiones en excepciones.tsv
  lila/paginas/<columna>.tsv   POR COLUMNA, una fila por aparición, ordenada
                               por línea: para revisar con el facsímil

Uso:
    python3 scripts/onate_lila.py src/disp63/pg_63_39_izq.xml
    python3 scripts/onate_lila.py src/disp63/pg_*.xml        # todas
    python3 scripts/onate_lila.py --dry-run src/disp63/pg_63_39_izq.xml

Excepciones (lila/excepciones.tsv, separado por tabuladores):
    lema        upos    ref           nota
    sero        VERB    lila:124505   sembrar (no 'entrelazar')
    Salas       PROPN   -             autor moderno: va al listPerson
    secundus    *       lila:127507   '*' = cualquier POS
  ref: lila:N (lema), lilah:N (hipolema) o '-' (no enlazar).
"""

import argparse
import csv
import json
import sys
import unicodedata
from pathlib import Path

from lxml import etree

TEI_NS = "http://www.tei-c.org/ns/1.0"
W = f"{{{TEI_NS}}}w"
LB = f"{{{TEI_NS}}}lb"
ROMAN_RE = __import__("re").compile(r"[ivxlcdmIVXLCDMjJ]+\.?")

# UPOS (LatinCy) → categorías de LiLa: [preferida, alternativas...]
POS_MAP = {
    # Sin cruce nombre común ↔ propio: 'Molina' (autor) no es 'molina' (molino).
    "NOUN":  ["noun"],
    "PROPN": ["proper_noun"],
    "ADJ":   ["adjective", "determiner", "numeral"],
    "VERB":  ["verb"],
    "AUX":   ["verb"],                       # sum, possum… son verbos en LiLa
    "ADV":   ["adverb", "particle"],
    "ADP":   ["adposition", "adverb"],
    "CCONJ": ["coordinating_conjunction", "adverb"],
    "SCONJ": ["subordinating_conjunction", "adverb"],
    "DET":   ["determiner", "pronoun", "adjective"],
    "PRON":  ["pronoun", "determiner"],
    "NUM":   ["numeral", "adjective", "determiner"],   # unus, ambo: determiner en LiLa
    "PART":  ["particle", "adverb"],
    "INTJ":  ["interjection"],
}

# Estados del informe (los dos primeros se enlazan automáticamente)
OK, ALT, AMBIG, POSDIF, NOTFOUND, EXC = (
    "ok", "pos_alternativo", "ambiguo", "pos_distinta", "no_encontrado", "excepcion")


def norm(s: str) -> str:
    """Debe coincidir con onate_lila_index.norm()."""
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.lower().replace("v", "u").replace("j", "i")
    s = s.replace("æ", "ae").replace("œ", "oe")
    return s.strip()


def ref_of(c) -> str:
    return ("lila:" if c["type"] == "lemma" else "lilah:") + c["id"]


def fmt_cands(cands) -> str:
    return "; ".join(
        f"{ref_of(c)} {c['pos']}{'' if c.get('canon', True) else ' (variante)'}"
        for c in cands)


def resolve(lemma, upos, index, exceptions):
    """Devuelve (ref|None, estado, candidatos_relevantes)."""
    for key in ((lemma, upos), (lemma, "*")):
        if key in exceptions:
            ref = exceptions[key]
            return (None if ref == "-" else ref), EXC, []

    cands = index.get(norm(lemma), [])
    if not cands:
        return None, NOTFOUND, []

    tiers = POS_MAP.get(upos, [])
    for i, pos in enumerate(tiers):
        pool = [c for c in cands if c["pos"] == pos]
        if not pool:
            continue
        # preferir forma de cita sobre variante gráfica, y lema sobre hipolema
        pool = [c for c in pool if c.get("canon", True)] or pool
        pool = [c for c in pool if c["type"] == "lemma"] or pool
        if len(pool) == 1:
            return ref_of(pool[0]), (OK if i == 0 else ALT), pool
        return None, AMBIG, pool          # homógrafos: decide el editor
    return None, POSDIF, cands


def load_exceptions(path: Path):
    exc = {}
    if not path.exists():
        return exc
    with path.open(encoding="utf-8") as fh:
        for row in csv.reader(fh, delimiter="\t"):
            if not row or row[0].startswith("#") or row[0] == "lema":
                continue
            if len(row) < 3:
                print(f"aviso: línea de excepción incompleta: {row}", file=sys.stderr)
                continue
            exc[(row[0].strip(), row[1].strip())] = row[2].strip()
    return exc


def set_lemmaref(w, ref):
    """Pone/quita @lemmaRef dejándolo justo detrás de @lemma."""
    attrs = [(k, v) for k, v in w.attrib.items() if k != "lemmaRef"]
    if ref:
        pos = next((i for i, (k, _) in enumerate(attrs) if k == "lemma"), len(attrs) - 1)
        attrs.insert(pos + 1, ("lemmaRef", ref))
    w.attrib.clear()
    for k, v in attrs:
        w.set(k, v)


def process_page(path: Path, index, exceptions, dry_run=False):
    tree = etree.parse(str(path))
    page_state = {}
    occurrences = []      # pendientes de esta columna, una fila por aparición
    changed = 0
    line = None
    for el in tree.getroot().iter(W, LB):
        # El número de línea es el del último <lb n> visto en orden de
        # documento; una palabra partida cuenta en la línea donde empieza.
        if el.tag == LB:
            if el.get("n"):
                line = el.get("n")
            continue
        w = el
        lemma, upos = w.get("lemma"), w.get("pos")
        if not lemma or not upos:
            continue
        if not any(ch.isalpha() for ch in lemma) or (
                upos == "NUM" and ROMAN_RE.fullmatch(lemma)):
            # cifras arábigas ("347") y números romanos ("LXIII"): no son lemas
            set_lemmaref(w, None)
            continue
        ref, status, cands = resolve(lemma, upos, index, exceptions)
        if w.get("lemmaRef") != ref:
            changed += 1
        set_lemmaref(w, ref)
        key = f"{lemma}\t{upos}"
        st = page_state.setdefault(key, {"estado": status, "ref": ref,
                                          "candidatos": fmt_cands(cands), "n": 0,
                                          "lineas": []})
        # orig/reg (y sic/corr) duplican la palabra: solo se cuenta la forma
        # que analiza LatinCy, para que n sean apariciones reales.
        if w.getparent().tag not in (f"{{{TEI_NS}}}orig", f"{{{TEI_NS}}}sic"):
            st["n"] += 1
            if status not in (OK, EXC):
                form = "".join(w.itertext()).strip()
                occurrences.append((line or "", form, lemma, upos, status,
                                    ref or "", fmt_cands(cands)))
        if line is not None and line not in st["lineas"]:
            st["lineas"].append(line)
    if not dry_run and changed:
        data = etree.tostring(tree, xml_declaration=True, encoding="UTF-8")
        path.write_bytes(data + b"\n")   # conservar el salto de línea final
    return page_state, occurrences, changed


def write_page_report(stem, occurrences, folder: Path):
    """Pendientes de una columna, ordenados por línea (para revisar con el facsímil)."""
    folder.mkdir(parents=True, exist_ok=True)
    out = folder / f"{stem}.tsv"
    if not occurrences:
        out.unlink(missing_ok=True)      # columna sin pendientes: sin archivo
        return 0
    with out.open("w", encoding="utf-8", newline="") as fh:
        wr = csv.writer(fh, delimiter="\t", lineterminator="\n")
        wr.writerow(["linea", "forma", "lema", "upos", "estado", "asignado", "candidatos"])
        for row in sorted(occurrences, key=lambda r: (_num(r[0]), r[2])):
            wr.writerow(row)
    return len(occurrences)


def _num(n: str):
    return (0, int(n)) if n.isdigit() else (1, n)


def write_report(state, path: Path):
    """Informe global: una fila por (lema, POS) pendiente, con sus páginas."""
    rows = {}
    for page, entries in state.items():
        for key, st in entries.items():
            if st["estado"] in (OK, EXC):
                continue
            r = rows.setdefault(key, {**st, "n": 0, "ubic": []})
            r["n"] += st["n"]
            lineas = st.get("lineas") or []      # estado.json antiguo: sin líneas
            r["ubic"].append((page, lineas))
    order = {AMBIG: 0, POSDIF: 1, ALT: 2, NOTFOUND: 3}
    with path.open("w", encoding="utf-8", newline="") as fh:
        wr = csv.writer(fh, delimiter="\t", lineterminator="\n")
        wr.writerow(["estado", "lema", "upos", "asignado", "candidatos", "n", "ubicacion"])
        for key, r in sorted(rows.items(), key=lambda kv: (order[kv[1]["estado"]], -kv[1]["n"], kv[0])):
            lemma, upos = key.split("\t")
            ubic = "; ".join(
                f"{page} l.{','.join(sorted(lineas, key=_num))}" if lineas else page
                for page, lineas in sorted(r["ubic"]))
            wr.writerow([r["estado"], lemma, upos, r["ref"] or "", r["candidatos"],
                         r["n"], ubic])
    return len(rows)


def main():
    ap = argparse.ArgumentParser(description="Enlaza <w> con el LiLa Lemma Bank (@lemmaRef).")
    ap.add_argument("pages", nargs="+", type=Path)
    ap.add_argument("--index", type=Path, default=Path("cache/lila_index.json"))
    ap.add_argument("--excepciones", type=Path, default=Path("lila/excepciones.tsv"))
    ap.add_argument("--estado", type=Path, default=Path("lila/estado.json"))
    ap.add_argument("--informe", type=Path, default=Path("lila/pendientes.tsv"))
    ap.add_argument("--paginas", type=Path, default=Path("lila/paginas"),
                    help="carpeta de informes por columna")
    ap.add_argument("--dry-run", action="store_true", help="no escribe los XML")
    args = ap.parse_args()

    if not args.index.exists():
        sys.exit(f"No existe {args.index}. Genéralo con scripts/onate_lila_index.py")
    index = json.loads(args.index.read_text(encoding="utf-8"))["entries"]
    exceptions = load_exceptions(args.excepciones)

    args.estado.parent.mkdir(parents=True, exist_ok=True)
    state = json.loads(args.estado.read_text(encoding="utf-8")) if args.estado.exists() else {}

    for path in args.pages:
        page_state, occurrences, changed = process_page(path, index, exceptions, args.dry_run)
        state[path.stem] = page_state
        if not args.dry_run:
            write_page_report(path.stem, occurrences, args.paginas)
        counts = {}
        for st in page_state.values():
            counts[st["estado"]] = counts.get(st["estado"], 0) + 1
        resumen = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
        print(f"{path.stem}: {len(page_state)} pares (lema, POS) → {resumen}; "
              f"{changed} <w> modificados{' (dry-run)' if args.dry_run else ''}")

    if not args.dry_run:
        args.estado.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
        n = write_report(state, args.informe)
        print(f"Informe global: {n} pares pendientes de revisión → {args.informe}")


if __name__ == "__main__":
    main()
