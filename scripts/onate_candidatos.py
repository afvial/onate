#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
onate_candidatos.py
───────────────────
Propone los términos y las expresiones multipalabra que conviene revisar
para el léxico OntoLex.

Uso:
    python3 scripts/onate_candidatos.py xml/disp63_bibl_completo.xml     (dependencias)
    python3 scripts/onate_candidatos.py html/disp63/search_index.js      (ventana)

Escribe (sin sobrescribir decisiones ya tomadas):
    lexico/terminos_candidatos.yaml     sustantivos y adjetivos frecuentes
    lexico/expresiones_candidatas.yaml  pares de lemas que forman expresión
    html/disp63/candidatos.html         informe con contextos y enlaces

Expresiones, con el XML completo (recomendado): se usan las dependencias
sintácticas que escribe onate_nlp.py (@n, @head, @deprel) dentro de cada <s>:
  · amod: adjetivo que modifica a un sustantivo        (pretium legale)
  · nmod en genitivo: sustantivo que depende de otro    (aestimatio reipublicae)
  · conj de los anteriores: coordinados                 (pretium legale & naturale)
Así se encuentran también pares separados por muchas palabras y se evitan
los que solo están cerca por casualidad. Para cada par se indica cuántas
veces además concuerdan en caso y número (control de errores del análisis).

Con el índice de la concordancia (modo antiguo): se buscan pares de LEMAS
dentro de la misma oración (aprox.: entre signos . ; : ?), a una distancia
de hasta --ventana palabras y en cualquier orden:
  · adjetivo + sustantivo que concuerdan en caso y número
        (legale pretium, pretio legali, pretium … legale)
  · sustantivo + sustantivo en genitivo
        (aestimatio reipublicae, pretium rerum)
Se ordenan por frecuencia y por asociación (log-likelihood de Dunning).
Las palabras de las referencias bibliográficas (cap., q., n., lib.…) se
descartan: son abreviaturas, no términos.
"""
import re
import sys
import json
import math
import html
import argparse
import collections
from pathlib import Path

CITE_LEMMAS = {  # aparato de citas: no son términos de la doctrina
    "numerus", "capitulum", "quaestio", "liber", "articulus", "disputatio",
    "punctum", "tractatus", "uerbum", "verbum", "sectio", "dubium", "dubius",
    "pars", "titulus", "distinctio", "controuersia", "controversia", "paragraphus",
    "lex", "glossa", "summa", "tomus", "folium", "pagina", "conclusio", "notabile",
}
SENT_END = {".", ";", ":", "?", "!"}


def load_index(path):
    s = Path(path).read_text(encoding="utf-8")
    s = s[s.index("{"): s.rstrip().rstrip(";").rindex("}") + 1]
    d = json.loads(s)
    F = d["fields"]
    at = {k: F.index(k) for k in F}
    toks = []
    for i, r in enumerate(d["tokens"]):
        t = {k: r[at[k]] for k in F}
        t["i"] = i
        t["feats"] = dict(x.split("=", 1) for x in (t["m"] or "").split("|") if "=" in x)
        t["abbr"] = t["d"] != t["f"] and t["d"].endswith(".")
        toks.append(t)
    return d, toks


def load_xml(path):
    """Oraciones <s> del XML completo, con dependencias. Devuelve (meta, chunks)."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from onate_ontolex import read_sentences
    sents = read_sentences(path)
    i, out = 0, []
    for s in sents:
        ch = []
        for t in s["toks"]:
            t = dict(t, i=i, pg=t["pg"], c=t["col"], sid=s["id"]); i += 1
            t["feats"] = dict(x.split("=", 1) for x in (t["m"] or "").split("|") if "=" in x)
            t["abbr"] = t["d"] != t["f"] and t["d"].endswith(".")
            ch.append(t)
        out.append(ch)
    meta = {"source": Path(path).name, "generated": "", "colPrefix": "pg_63_"}
    return meta, out


def chunks(toks):
    """Oraciones aproximadas: misma columna, cortadas en . ; : ? !"""
    cur, col = [], None
    for t in toks:
        c = (t["pg"], t["c"])
        if c != col and cur:
            yield cur; cur = []
        col = c
        if t["p"] == "PUNCT":
            if t["f"] in SENT_END and cur:
                yield cur; cur = []
            continue
        cur.append(t)
    if cur:
        yield cur


def is_term(t):
    return (t["p"] in ("NOUN", "ADJ") and t["l"] and not t["abbr"]
            and t["l"].lower() not in CITE_LEMMAS and len(t["l"]) > 2)


# Casos que LatinCy confunde a menudo en formas idénticas (3.ª decl.:
# legali, naturali = dativo o ablativo; legalis = nominativo o vocativo)
CASE_GROUP = {"Nom": "N", "Voc": "N", "Dat": "D", "Abl": "D"}


def agree(a, b):
    fa, fb = a["feats"], b["feats"]
    if "Case" not in fa or "Case" not in fb:
        return False
    ca, cb = fa["Case"], fb["Case"]
    # neutro: nominativo, acusativo y vocativo tienen siempre la misma forma
    # (pretium legale & consuetudinarium: Acc / Nom según LatinCy)
    neut = "Neut" in (fa.get("Gender"), fb.get("Gender"))
    grp = lambda c: "N" if neut and c in ("Nom", "Acc", "Voc") else CASE_GROUP.get(c, c)
    if ca != cb and grp(ca) != grp(cb):
        return False
    if "Number" in fa and "Number" in fb and fa["Number"] != fb["Number"]:
        return False
    return True


def g2(k11, k12, k21, k22):
    """Log-likelihood de Dunning para una tabla 2×2."""
    def h(*ks):
        n = sum(ks)
        return sum(k * math.log(k / n) for k in ks if k > 0)
    return 2 * (h(k11, k12, k21, k22) - h(k11 + k12, k21 + k22) - h(k11 + k21, k12 + k22))


def add_pair(pair, key, kind, order, A, B, ch):
    e = pair[key]
    e["n"] += 1; e["kind"] = kind; e["order"][order] += 1
    e["surface"][" ".join(t["f"].lower() for t in sorted((A, B), key=lambda t: t["i"]))] += 1
    if agree(A, B) or kind == "sust+gen":
        e["agree"] += 1
    if len(e["ex"]) < 4:
        e["ex"].append((A, B, ch))


def pairs_dep(ch, pair, _ventana=None):
    """Pares a partir de las dependencias de la oración."""
    # t["k"]: posición en la oración; t["hidx"]: posición del núcleo (onate_ontolex.read_sentences)
    up = lambda t: ch[t["hidx"]] if t.get("hidx") not in (None, -1) else None
    gen = lambda t: t["feats"].get("Case") == "Gen"
    for t in ch:
        if not is_term(t):
            continue
        rel, h = t.get("rel", ""), up(t)
        coord = False
        # coordinados: se sube por la cadena de conj mientras el núcleo sea de
        # la misma categoría (naturale → legale → pretium)
        while rel == "conj" and h is not None and h["p"] == t["p"]:
            coord = True
            rel, h = h.get("rel", ""), up(h)
        if h is None or not is_term(h) or h["l"] == t["l"]:
            continue
        # adjetivo coordinado colgado directamente del sustantivo (pretium
        # legale & consuetudinarium → consuetudinarium conj pretium): se
        # acepta como modificador solo si concuerda con él
        if rel == "conj" and t["p"] == "ADJ" and h["p"] == "NOUN" and agree(h, t):
            rel, coord = "amod", True
        if rel == "amod" and t["p"] == "ADJ" and h["p"] == "NOUN":
            order = "coordinado" if coord else ("sust-adj" if h["i"] < t["i"] else "adj-sust")
            add_pair(pair, (h["l"], t["l"]), "sust+adj", order, h, t, ch)
        elif rel == "nmod" and t["p"] == h["p"] == "NOUN" and gen(t):
            order = "coordinado" if coord else ("sust-gen" if h["i"] < t["i"] else "gen-sust")
            add_pair(pair, (h["l"], t["l"]), "sust+gen", order, h, t, ch)


def pairs_window(ch, pair, ventana):
    """Pares por proximidad (modo antiguo, sin dependencias)."""
    seen = set()
    for x in range(len(ch)):
        for y in range(x + 1, min(len(ch), x + 1 + ventana)):
            A, B = ch[x], ch[y]
            if not (is_term(A) and is_term(B)) or A["l"] == B["l"]:
                continue
            kind = None
            if {A["p"], B["p"]} == {"ADJ", "NOUN"} and agree(A, B):
                noun, adj = (A, B) if A["p"] == "NOUN" else (B, A)
                key, kind = (noun["l"], adj["l"]), "sust+adj"
                order = "sust-adj" if noun is A else "adj-sust"
            elif A["p"] == B["p"] == "NOUN" and B["feats"].get("Case") == "Gen" and A["feats"].get("Case") != "Gen":
                key, kind, order = (A["l"], B["l"]), "sust+gen", "sust-gen"
            elif A["p"] == B["p"] == "NOUN" and A["feats"].get("Case") == "Gen" and B["feats"].get("Case") != "Gen":
                key, kind, order = (B["l"], A["l"]), "sust+gen", "gen-sust"
            if not kind or (key, x, y) in seen:
                continue
            if kind == "sust+adj":
                # adjetivos coordinados con el primero: pretium legale,
                # naturale & conuentionale → cada uno forma par con pretium
                npos = x if noun is A else y
                k = (y if adj is B else x) + 1
                while k < len(ch) and (ch[k]["p"] in ("CCONJ",) or (ch[k]["p"] == "ADJ" and is_term(ch[k]))):
                    if ch[k]["p"] == "ADJ" and ch[k]["l"] != adj["l"]:
                        kk = (noun["l"], ch[k]["l"])
                        sk = (kk, min(npos, k), max(npos, k))
                        if sk not in seen:
                            seen.add(sk)
                            ee = pair[kk]; ee["n"] += 1; ee["kind"] = "sust+adj"; ee["order"]["coordinado"] += 1
                            ee["surface"][f'{noun["f"].lower()} … {ch[k]["f"].lower()}'] += 1
                            if len(ee["ex"]) < 4: ee["ex"].append((noun, ch[k], ch))
                    k += 1
            seen.add((key, x, y))
            e = pair[key]
            e["n"] += 1; e["kind"] = kind; e["order"][order] += 1
            e["surface"][" ".join(t["f"].lower() for t in (A, B))] += 1
            if len(e["ex"]) < 4:
                e["ex"].append((A, B, ch))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[3])
    ap.add_argument("fuente", help="xml/disp63_bibl_completo.xml (dependencias) o html/disp63/search_index.js")
    ap.add_argument("--min", type=int, default=3, help="frecuencia mínima (por defecto 3)")
    ap.add_argument("--ventana", type=int, default=3, help="solo con el índice: distancia máxima entre lemas (3)")
    ap.add_argument("--terminos", type=int, default=60, help="cuántos términos listar (60)")
    ap.add_argument("--outdir", default=".", help="raíz del proyecto (por defecto, la actual)")
    a = ap.parse_args()

    if a.fuente.endswith(".xml"):
        mode = "dep"
        d, sents = load_xml(a.fuente)
        toks = [t for ch in sents for t in ch]
    else:
        mode = "ventana"
        d, toks = load_index(a.fuente)
        sents = list(chunks(toks))
    root = Path(a.outdir)

    # ── términos ─────────────────────────────────────────────────────────────
    term = collections.defaultdict(lambda: {"n": 0, "forms": collections.Counter(), "pages": set(), "ex": []})
    for t in toks:
        if is_term(t):
            e = term[(t["l"], t["p"])]
            e["n"] += 1
            e["forms"][t["f"].lower()] += 1
            e["pages"].add(int(t["pg"]) if t["pg"].isdigit() else t["pg"])
            if len(e["ex"]) < 3:
                e["ex"].append(t)
    terms = sorted(term.items(), key=lambda kv: -kv[1]["n"])[: a.terminos]

    # ── expresiones ──────────────────────────────────────────────────────────
    unig = collections.Counter()
    pair = collections.defaultdict(lambda: {"n": 0, "kind": "", "order": collections.Counter(),
                                            "surface": collections.Counter(), "ex": [], "agree": 0})
    n_chunks = 0
    for ch in sents:
        if not ch:
            continue                   # parte final de una oración partida (va con la inicial)
        n_chunks += 1
        for t in ch:
            if is_term(t):
                unig[t["l"]] += 1
        (pairs_dep if mode == "dep" else pairs_window)(ch, pair, a.ventana)
    N = sum(unig.values()) or 1
    cands = []
    for (l1, l2), e in pair.items():
        if e["n"] < a.min:
            continue
        k11 = e["n"]; k12 = max(unig[l1] - k11, 0); k21 = max(unig[l2] - k11, 0)
        k22 = max(N - k11 - k12 - k21, 0)
        e["g2"] = g2(k11, k12, k21, k22)
        cands.append(((l1, l2), e))
    cands.sort(key=lambda kv: (-kv[1]["n"], -kv[1]["g2"]))

    # ── salidas ──────────────────────────────────────────────────────────────
    lex = root / "lexico"; lex.mkdir(parents=True, exist_ok=True)
    loc = lambda t: f'p{t["pg"]}{t["c"]} l.{t["ln"]}'

    def write_once(path, text):
        if path.exists():
            alt = path.with_suffix(".nuevo.yaml")
            alt.write_text(text, encoding="utf-8")
            print(f"  {path} ya existe (con tus decisiones): escrito {alt}", file=sys.stderr)
        else:
            path.write_text(text, encoding="utf-8")
            print(f"  → {path}", file=sys.stderr)

    y = [f"# Términos candidatos para el inventario de sentidos",
         f"# Generado de {d.get('source','?')} ({d.get('generated','?')})",
         f"# estado: pendiente | incluir | excluir     sentidos: se rellenan al incluir", ""]
    for (l, p), e in terms:
        pages = sorted(e["pages"], key=lambda v: (isinstance(v, str), v))
        y += [f"{l}:", f"  pos: {p}", f"  apariciones: {e['n']}",
              f"  formas: [{', '.join(f for f, _ in e['forms'].most_common(6))}]",
              f"  paginas: {pages[0]}–{pages[-1]}" if len(pages) > 1 else f"  paginas: {pages[0]}",
              f"  estado: pendiente", f"  sentidos: []", ""]
    write_once(lex / "terminos_candidatos.yaml", "\n".join(y))

    y = [f"# Expresiones multipalabra candidatas",
         (f"# Pares unidos por dependencia (amod, nmod en genitivo, conj), frecuencia ≥ {a.min}"
          if mode == "dep" else
          f"# Pares de lemas en la misma oración, ventana {a.ventana}, frecuencia ≥ {a.min}"),
         "# concuerdan: cuántas apariciones concuerdan además en caso y número (solo sust+adj);"
         if mode == "dep" else "#",
         "#   pocas → probable error del análisis sintáctico" if mode == "dep" else "#",
         f"# estado: pendiente | aceptada | rechazada", ""]
    for (l1, l2), e in cands:
        y += [f"{l1}_{l2}:", f"  lemas: [{l1}, {l2}]", f"  tipo: {e['kind']}",
              f"  forma: {e['surface'].most_common(1)[0][0].replace(' … ', ' ')}",
              f"  apariciones: {e['n']}", f"  asociacion_g2: {e['g2']:.1f}",
              *([f"  concuerdan: {e['agree']}"] if mode == "dep" and e["kind"] == "sust+adj" else []),
              f"  orden: {dict(e['order'])}",
              f"  ejemplos: [{', '.join(loc(A) for A, B, ch in e['ex'])}]",
              f"  estado: pendiente", ""]
    write_once(lex / "expresiones_candidatas.yaml", "\n".join(y))

    # informe HTML
    def kwic(A, B, ch):
        lo = min(A["i"], B["i"]); hi = max(A["i"], B["i"])
        if hi - lo > 12:
            pa = [t for t in ch if lo - 3 <= t["i"] <= lo + 3]
            pb = [t for t in ch if hi - 3 <= t["i"] <= hi + 3]
            mk = lambda ts: " ".join(f'<b>{html.escape(t["f"])}</b>' if t["i"] in (A["i"], B["i"]) else html.escape(t["f"]) for t in ts)
            return mk(pa) + " <span class=m>[…]</span> " + mk(pb)
        span = [t for t in ch if lo - 4 <= t["i"] <= hi + 4]
        return " ".join(f'<b>{html.escape(t["f"])}</b>' if t["i"] in (A["i"], B["i"]) else html.escape(t["f"]) for t in span)
    def facs(t):
        return ("disp63_facs.html#" + html.escape(
            f'{d.get("colPrefix","pg_63_")}{t["pg"]}_{t["c"]}%3A{t["ln"]}%3A{t["d"]}%3A{t.get("o",0)}'))
    rows_e = "".join(
        f'<tr><td><i>{html.escape(e["surface"].most_common(1)[0][0])}</i><br><span class="m">{l1} + {l2}</span></td>'
        f'<td class="n">{e["n"]}</td><td class="n">{e["g2"]:.0f}</td><td class="m">{e["kind"]}<br>'
        + (f'concuerdan {e["agree"]}/{e["n"]}<br>' if mode == "dep" and e["kind"] == "sust+adj" else "")
        + ", ".join(f"{k} {v}" for k, v in e["order"].items()) + '</td><td>'
        + "<br>".join(f'<a href="{facs(A)}" target="onate_facs">{loc(A)}</a> · {kwic(A, B, ch)}' for A, B, ch in e["ex"][:3])
        + "</td></tr>" for (l1, l2), e in cands)
    rows_t = "".join(
        f'<tr><td><i>{html.escape(l)}</i></td><td class="m">{p}</td><td class="n">{e["n"]}</td>'
        f'<td>{html.escape(", ".join(f for f, _ in e["forms"].most_common(6)))}</td></tr>' for (l, p), e in terms)
    page = f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Candidatos · léxico</title>
<style>
body {{ margin: 0; background: #f4f6f4; color: #1c2321; font: 15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }}
.wrap {{ max-width: 1100px; margin: 0 auto; padding: 24px 20px 60px; }}
h1 {{ font: italic 500 34px Georgia, serif; margin: 0 0 4px; }} h2 {{ font-size: 13px; letter-spacing: .06em; text-transform: uppercase; color: #5b6763; margin: 28px 0 8px; }}
p {{ color: #5b6763; max-width: 75ch; }} .box {{ background: #fff; border: 1px solid #d5dcd8; border-radius: 8px; overflow-x: auto; }}
table {{ border-collapse: collapse; width: 100%; font-size: 14px; }} th {{ text-align: left; font-size: 11.5px; text-transform: uppercase; letter-spacing: .05em; color: #5b6763; padding: 8px 10px; border-bottom: 1px solid #d5dcd8; }}
td {{ padding: 7px 10px; border-top: 1px solid #e3e8e5; vertical-align: top; }} td i {{ font: italic 16px Georgia, serif; }}
.n {{ font-variant-numeric: tabular-nums; text-align: right; }} .m {{ font: 12px ui-monospace, Menlo, monospace; color: #5b6763; }}
a {{ color: #1d6b64; font: 12px ui-monospace, Menlo, monospace; }} b {{ background: #fdeee0; font-weight: 500; }}
</style></head><body><div class="wrap">
<h1>Candidatos para el léxico</h1>
<p>{len(cands)} expresiones multipalabra y {len(terms)} términos propuestos a partir de {d.get("source","el índice")}
({"pares unidos por dependencia sintáctica: amod, nmod en genitivo y sus coordinados" if mode == "dep" else f"pares a distancia ≤ {a.ventana}"}).
Las decisiones se toman en <code>lexico/expresiones_candidatas.yaml</code> y <code>lexico/terminos_candidatos.yaml</code>.
Cada ejemplo enlaza a su lugar en el facsímil.</p>
<h2>Expresiones multipalabra</h2>
<div class="box"><table><thead><tr><th>Expresión</th><th>Apar.</th><th>G²</th><th>Tipo y orden</th><th>Ejemplos</th></tr></thead><tbody>{rows_e}</tbody></table></div>
<h2>Términos frecuentes (sustantivos y adjetivos)</h2>
<div class="box"><table><thead><tr><th>Lema</th><th>POS</th><th>Apar.</th><th>Formas</th></tr></thead><tbody>{rows_t}</tbody></table></div>
</div></body></html>"""
    out = root / "html/disp63/candidatos.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    print(f"  → {out}", file=sys.stderr)
    print(f"✓ {len(cands)} expresiones (≥{a.min}), {len(terms)} términos, {n_chunks} oraciones" + (" (dependencias)" if mode == "dep" else " aprox. (ventana)"), file=sys.stderr)


if __name__ == "__main__":
    main()
