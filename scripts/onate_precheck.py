#!/usr/bin/env python3
"""
Informe previo de una columna (v2): sospechosos en formato de
correcciones/disp63/pg_63_P_C.tsv, todos comentados (#).
Se apoya en el TEI ya procesado: una palabra con enlace a LiLa (o en las
excepciones, o nombre propio) se considera bien leída.
Uso: python3 scripts/onate_precheck.py 48 izq [--anadir]
"""
import argparse, re, sys, unicodedata
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import onate_tokens as TK

LETRA = r"A-Za-zÀ-ÿſæœęĘāēīōūãẽĩõũÆŒ"
PAL = re.compile(rf"[{LETRA}]+")
CONF = [("n", "u"), ("u", "n"), ("c", "e"), ("e", "c"), ("f", "s"), ("s", "f"), ("r", "t"), ("t", "r"),
        ("i", "l"), ("l", "i"), ("a", "e"), ("e", "a"), ("o", "e"), ("e", "o"), ("rn", "m"), ("m", "rn"),
        ("h", "b"), ("b", "h"), ("g", "t"), ("a", "u"), ("u", "a"), ("d", "u"), ("r", "x")]
MACRON_FIN = ("um", "em", "am", "unt", "ent", "ant", "ont", "ione", "ionem")


def norm(w):
    w = (w.lower().replace("ſ", "s").replace("æ", "ae").replace("œ", "oe")
          .replace("ę", "ae").replace("v", "u").replace("j", "i"))
    return "".join(c for c in unicodedata.normalize("NFD", w) if not unicodedata.combining(c))


def limpia(t):
    t = t.replace("&amp;", "&")
    t = re.sub(r"\{([^|{}]*)\|[^{}]*\}", r"\1", t)
    t = re.sub(r"\[[-+=][^\]]*\]", "", t)
    t = re.sub(r"\{_\d*\}", "", t)
    t = t.replace("//", "").replace("¶", "").replace("-|", "")
    t = re.sub(r"^(#+|>{2,3}\d*)", "", t)
    return re.sub(r"[@*^]", "", t).strip()


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("pagina"); ap.add_argument("columna")
    ap.add_argument("--anadir", action="store_true")
    a = ap.parse_args()
    stem = f"pg_63_{a.pagina}_{a.columna}"
    lineas = re.findall(r'<line id="([^"]+)">([^<]*)</line>',
                        Path(f"staging/disp63/{stem}.xml").read_text(encoding="utf-8"))

    # Palabras «buenas»: con enlace a LiLa, en las excepciones o nombres propios (todo el corpus)
    exc = {l.split("\t")[0] for l in Path("lila/excepciones.tsv").read_text(encoding="utf-8").splitlines() if l}
    buenas, voc = set(), Counter()
    fuentes = list(Path("src/disp63").glob("pg_*.xml")) + [Path("output/disp63_bibl_completo.xml")]
    for src in (f for f in fuentes if f.exists()):
        for m in re.finditer(r'<w ([^>]*)>([^<]+)</w>', src.read_text(encoding="utf-8")):
            at, w = m.group(1), m.group(2)
            lem = (re.search(r'lemma="([^"]*)"', at) or [None, ""])[1]
            voc[norm(w)] += 1
            if "lemmaRef" in at or lem in exc or 'pos="PROPN"' in at:
                buenas.add(norm(w))
    conocida = lambda w: norm(w) in buenas
    abrevs = {x.lower() for x in TK.ABBREV_WITH_DOT}
    filas = []

    lemas = {}
    srcp = Path(f"src/disp63/{stem}.xml")
    if srcp.exists():
        for m in re.finditer(r'<w ([^>]*)>([^<]+)</w>', srcp.read_text(encoding="utf-8")):
            lm = re.search(r'lemma="([^"]*)"', m.group(1))
            if lm: lemas[norm(m.group(2))] = lm.group(1)
    # Palabras de la columna, con las partidas entre líneas ya unidas
    toks, resto = [], None
    for lid, txt in lineas:
        pals = PAL.findall(limpia(txt))
        if resto and pals:
            toks.append((resto[0], resto[1] + pals[0], True)); pals = pals[1:]
        resto = None
        if pals and re.search(r"[¬~]\s*$", txt):
            resto = (lid, pals[-1]); pals = pals[:-1]
        toks += [(lid, w, False) for w in pals]

    # 1. Cortes sin marcar
    for k, (lid, txt) in enumerate(lineas[:-1]):
        lim = limpia(txt); pals = PAL.findall(lim); sig = PAL.findall(limpia(lineas[k + 1][1]))
        if pals and sig and not re.search(r"[¬~]\s*$|-\|\s*$", txt) and not re.search(r"[.,;:?!\]]$", lim):
            if not conocida(pals[-1]) and conocida(pals[-1] + sig[0]):
                filas.append((lid, f"{pals[-1]}<", f"{pals[-1]}~<", f"corte sin marcar: {pals[-1]}+{sig[0]} (¿~ o ¬?)"))

    # 2. Lecturas dudosas (solo palabras sin análisis fiable)
    for lid, w, partida in toks:
        if len(w) < 3 or conocida(w) or w.isupper() or any(c in w for c in "āēīōūãẽĩõũ"):
            continue
        if (w + ".").lower() in abrevs:
            continue
        lem_w = lemas.get(norm(w))
        if lem_w and norm(lem_w) != norm(w):
            continue   # analizada: si falla, es un problema de lema
        sug = {w[:m.start()] + y + w[m.end():] for x, y in CONF for m in re.finditer(re.escape(x), w)}
        sug = sorted((c for c in sug if conocida(c)), key=lambda c: -voc[norm(c)])
        pre = "palabra partida; " if partida else ""
        filas.append((lid, w, sug[0] if sug else w,
                      pre + (f"¿lectura? propuestas: {' / '.join(sug[:3])}" if sug
                             else "sin análisis fiable: revisar en el facsímil")))

    # 3. Macrón probable: palabras cuya caja es estrecha para el texto transcrito
    #    (Transkribus desarrolla nō → non, pretiū → pretium; la caja mide lo impreso)
    from lxml import etree
    import statistics
    NS = "http://schema.primaresearch.org/PAGE/gts/pagecontent/2013-07-15"
    T = lambda n: f"{{{NS}}}{n}"
    pgp = Path(f"transkribus/disp63/{stem}.xml")
    cands = []
    if pgp.exists():
        for line in etree.parse(str(pgp)).iter(T("TextLine")):
            datos = []
            for w in line.findall(T("Word")):
                u = w.find(f"{T('TextEquiv')}/{T('Unicode')}")
                txt = re.sub(r"[^" + LETRA + "]", "", (u.text or "") if u is not None else "")
                pts = [tuple(map(int, q.split(","))) for q in w.find(T("Coords")).get("points").split()]
                ancho = max(q[0] for q in pts) - min(q[0] for q in pts)
                if len(txt) >= 2 and ancho > 0 and not any(c in txt for c in "āēīōūãẽĩõũ"):
                    datos.append((txt, ancho / len(txt)))
            if len(datos) < 4:
                continue
            med = statistics.median(r for _, r in datos)
            for txt, r in datos:
                if r < med * 0.78:   # al menos ~1 letra «de más» en palabras cortas y medias
                    cands.append((r / med, line.get("id"), txt))
    for ratio, lid, w in sorted(cands)[:10]:
        filas.append((lid, w, w, f"¿abreviada en el impreso? caja estrecha ({ratio:.0%} del ancho normal): ¿macrón, q;…?"))

    # 4. Abreviaturas no registradas (punto seguido de minúscula o número)
    for lid, txt in lineas:
        for m in re.finditer(rf"\b([{LETRA}]{{1,6}})\.\s+(?=[a-zſæœ0-9])", limpia(txt)):
            ab = m.group(1) + "."
            if ab.lower() not in abrevs and not conocida(m.group(1)):
                filas.append((lid, ab, ab, "¿abreviatura no registrada? (añadirla a onate_tokens.py)"))

    # 6. Cajas rotas en el PAGE XML (anchura cero, amontonadas, fuera de orden)
    from collections import Counter as _C
    from lxml import etree as _et
    _NS = "http://schema.primaresearch.org/PAGE/gts/pagecontent/2013-07-15"
    _T = lambda n: f"{{{_NS}}}{n}"
    _pg = Path(f"transkribus/disp63/{stem}.xml")
    if _pg.exists():
        for _line in _et.parse(str(_pg)).iter(_T("TextLine")):
            _cs = []
            for _w in _line.findall(_T("Word")):
                _pts = [tuple(map(int, q.split(","))) for q in _w.find(_T("Coords")).get("points").split()]
                _cs.append((min(p[0] for p in _pts), max(p[0] for p in _pts)))
            if len(_cs) < 2:
                continue
            _cero = sum(1 for i, f in _cs if f - i <= 3)
            _amont = sum(n for n in _C(i for i, _ in _cs).values() if n > 1)
            _desord = sum(1 for (i1, _), (i2, _) in zip(_cs, _cs[1:]) if i2 < i1 - 5)
            if _cero or _amont or _desord:
                _lid = _line.get("id")
                filas.append(("(cajas)", _lid, "",
                              f"cajas rotas: {_cero} de anchura cero, {_amont} amontonadas, {_desord} fuera de orden "
                              f"→ python3 scripts/onate_rehacer_cajas.py {a.pagina} {a.columna} {_lid}"))

    # 5. Lemas problemáticos de esta columna
    src = Path(f"src/disp63/{stem}.xml")
    if src.exists():
        vistos = set()
        for m in re.finditer(r'<w ([^>]*)>([^<]+)</w>', src.read_text(encoding="utf-8")):
            at, w = m.group(1), m.group(2)
            lem = (re.search(r'lemma="([^"]*)"', at) or [None, ""])[1]
            pos = (re.search(r'pos="([^"]*)"', at) or [None, ""])[1]
            if not lem or "lemmaRef" in at or lem in exc or (lem, pos) in vistos or pos in ("PUNCT", "NUM", "X"):
                continue
            vistos.add((lem, pos))
            if pos == "PROPN" and w[:1].isupper() and not lem[:1].isupper():
                prop = "¿nombre común con mayúscula? → MANUAL_LEMMA con el lema en minúscula"
            elif pos == "PROPN":
                prop = "nombre propio: autor (excepciones.tsv) o lugar (lugares.tsv); o nombre común con mayúscula"
            elif pos == "ADJ" and re.search(r"(a|um)$", lem):
                base = lem[:-1] if lem.endswith("a") else lem[:-2]
                prop = f"¿adjetivo con el lema en femenino/neutro (→ {base}us) o sustantivo mal categorizado (→ NOUN)?"
            elif pos == "ADJ" and lem.endswith("o"):
                prop = "ADJ con lema verbal: ¿participio (VERB) o adverbio?"
            else:
                prop = "sin enlace a LiLa: comprobar con lila_candidatos.py (¿«elegir lema»?)"
            filas.append(("(lema)", w, lem, f"{prop} [{lem}, {pos}]"))

    vistas, salida = set(), []
    for lid, o, n, nota in filas:
        if (lid, o) in vistas: continue
        vistas.add((lid, o)); salida.append(f"#{lid}\t{o}\t{n}\t\t{nota}")
    print(f"# Informe previo de {stem}: {len(salida)} sospechosos\n" + "\n".join(salida))
    if a.anadir and salida:
        p = Path(f"correcciones/disp63/{stem}.tsv"); p.parent.mkdir(parents=True, exist_ok=True)
        if not p.exists(): p.write_text("linea\toriginal\tnuevo\tpage\tnota\n", encoding="utf-8")
        with p.open("a", encoding="utf-8") as f:
            f.write("# ── informe previo ──\n" + "\n".join(salida) + "\n")
        print(f"\nAñadidas al final de {p}")


if __name__ == "__main__":
    main()
