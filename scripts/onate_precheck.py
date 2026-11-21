#!/usr/bin/env python3
"""
Informe previo de una columna: lista de sospechosos en formato de
correcciones/disp63/pg_63_P_C.tsv, todos comentados (#), para comprobarlos
en el facsímil y activar los que valgan.
Uso: python3 scripts/onate_precheck.py 48 der [--anadir]
  --anadir   añade las filas al final del archivo de correcciones
"""
import argparse, json, re, sys, unicodedata
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import onate_tokens as TK

LETRA = r"A-Za-zÀ-ÿſæœęĘāēīōūãẽĩõũÆŒ"
PAL = re.compile(rf"[{LETRA}]+")
CONFUSIONES = [("n", "u"), ("u", "n"), ("c", "e"), ("e", "c"), ("f", "s"), ("s", "f"), ("r", "t"),
               ("t", "r"), ("i", "l"), ("l", "i"), ("a", "e"), ("e", "a"), ("o", "e"), ("e", "o"),
               ("rn", "m"), ("m", "rn"), ("ii", "u"), ("h", "b"), ("b", "h"), ("g", "t")]
MACRON_FIN = ("um", "em", "am", "unt", "ent", "ant", "ont")
MACRON_SIL = re.compile(r"(?i)(con|com|[aeiou]n[tcdgsqf]|[aeiou]m[pb])")


def norm(w):
    w = w.lower().replace("ſ", "s").replace("æ", "ae").replace("œ", "oe").replace("ę", "ae").replace("v", "u").replace("j", "i")
    return "".join(c for c in unicodedata.normalize("NFD", w) if not unicodedata.combining(c))


def limpia(t):
    """Texto de la línea sin marcas editoriales (como en onate_aplicar.impreso)."""
    t = t.replace("&amp;", "&")
    t = re.sub(r"\{([^|{}]*)\|[^{}]*\}", r"\1", t)
    t = re.sub(r"\[[-+=][^\]]*\]", "", t)
    t = re.sub(r"\{_\d*\}", "", t)
    t = t.replace("//", "").replace("¶", "").replace("-|", "")
    t = re.sub(r"^(#+|>{2,3}\d*)", "", t)
    return re.sub(r"[@*^]", "", t).strip()


def vocabulario():
    voc = Counter()
    idx = Path("html/disp63/search_index.js")
    if idx.exists():
        s = idx.read_text(encoding="utf-8")
        d = json.loads(s[s.index("{"):s.rindex("}") + 1]); F = d["fields"]
        for r in d["tokens"]:
            t = dict(zip(F, r)); voc[norm(str(t.get("f", "")))] += 1
    lb = Path("cache/lemmaBank.ttl")
    if lb.exists():
        for w in re.findall(r'"([^"]+)"@la', lb.read_text(encoding="utf-8")):
            voc[norm(w)] += 2
    return voc


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("pagina"); ap.add_argument("columna")
    ap.add_argument("--anadir", action="store_true")
    a = ap.parse_args()
    stem = f"pg_63_{a.pagina}_{a.columna}"
    s = Path(f"staging/disp63/{stem}.xml").read_text(encoding="utf-8")
    lineas = re.findall(r'<line id="([^"]+)">([^<]*)</line>', s)
    voc = vocabulario()
    conocida = lambda w: voc[norm(w)] >= 2
    abrevs = {x.lower() for x in TK.ABBREV_WITH_DOT} | {x.lower() for x in getattr(TK, "ABBREV_WITH_SEMICOLON", [])}
    filas = []

    largos = sorted(len(limpia(t)) for _, t in lineas) or [0]
    llena = largos[int(len(largos) * 0.7)]

    for k, (lid, txt) in enumerate(lineas):
        limpio = limpia(txt)
        pals = PAL.findall(limpio)
        # 1. corte sin marcar
        if pals and k + 1 < len(lineas) and not re.search(r"[¬~]\s*$|-\|\s*$", txt) and not re.search(r"[.,;:?!\]]\s*$", limpio):
            ult = pals[-1]; sig = PAL.findall(limpia(lineas[k + 1][1]))
            if sig and not conocida(ult) and conocida(ult + sig[0]):
                filas.append((lid, f"{ult}<", f"{ult}~<", f"corte sin marcar: {ult}+{sig[0]} = {ult + sig[0]} (¿~ o ¬?)"))
        # 2. lecturas dudosas
        for w in pals:
            if len(w) < 3 or conocida(w) or w.isupper():
                continue
            sug = set()
            for x, y in CONFUSIONES:
                for m in re.finditer(re.escape(x), w):
                    c = w[:m.start()] + y + w[m.end():]
                    if conocida(c): sug.add(c)
            if sug:
                filas.append((lid, w, sorted(sug, key=lambda c: -voc[norm(c)])[0], f"palabra desconocida; ¿{' / '.join(sorted(sug))}?"))
            elif not any(ch in w for ch in "āēīōūãẽĩõũ"):
                filas.append((lid, w, w, "palabra desconocida (sin propuesta): revisar en el facsímil"))
        # 3. macrón probable (final de línea llena)
        if len(limpio) >= llena and pals:
            for w in pals[-2:]:
                if any(ch in w for ch in "āēīōūãẽĩõũ"): continue
                nw = norm(w)
                if nw.endswith(MACRON_FIN) or MACRON_SIL.search(nw):
                    filas.append((lid, w, w, "¿macrón? (final de línea llena): mirar el facsímil y poner la forma con macrón"))
        # 4. abreviaturas desconocidas
        for m in re.finditer(rf"[{LETRA}]+(\.|q;)", limpio):
            ab = m.group(0)
            if ab.lower() not in abrevs and len(ab) <= 8 and not conocida(ab.rstrip(".;")) :
                filas.append((lid, ab, ab, "¿abreviatura no registrada? (añadirla a onate_tokens.py)"))

    # 5. lemas problemáticos (TEI ya procesado)
    src = Path(f"src/disp63/{stem}.xml")
    if src.exists():
        exc = {l.split("\t")[0] for l in Path("lila/excepciones.tsv").read_text(encoding="utf-8").splitlines() if l}
        vistos = set()
        for m in re.finditer(r'<w ([^>]*)>([^<]+)</w>', src.read_text(encoding="utf-8")):
            at, w = m.group(1), m.group(2)
            lem = (re.search(r'lemma="([^"]*)"', at) or [None, ""])[1]
            pos = (re.search(r'pos="([^"]*)"', at) or [None, ""])[1]
            if not lem or "lemmaRef" in at or lem in exc or (lem, pos) in vistos or pos in ("PUNCT", "NUM", "X"):
                continue
            vistos.add((lem, pos))
            motivo = ("lema con mayúscula fuera de nombre propio" if lem[0].isupper() and pos != "PROPN"
                      else "nombre propio: ¿autor o lugar? (excepción o lugares.tsv)" if pos == "PROPN"
                      else "sin enlace a LiLa: ¿lema erróneo o «elegir lema»?")
            filas.append(("(lema)", w, lem, f"{motivo} [{lem}, {pos}]"))

    vistas, salida = set(), []
    for lid, o, n, nota in filas:
        if (lid, o, nota) in vistas: continue
        vistas.add((lid, o, nota))
        salida.append(f"#{lid}\t{o}\t{n}\t\t{nota}")
    print(f"# Informe previo de {stem}: {len(salida)} sospechosos\n" + "\n".join(salida))
    if a.anadir and salida:
        p = Path(f"correcciones/disp63/{stem}.tsv"); p.parent.mkdir(parents=True, exist_ok=True)
        if not p.exists(): p.write_text("linea\toriginal\tnuevo\tpage\tnota\n", encoding="utf-8")
        with p.open("a", encoding="utf-8") as f:
            f.write(f"# ── informe previo ──\n" + "\n".join(salida) + "\n")
        print(f"\nAñadidas al final de {p}")


if __name__ == "__main__":
    main()
