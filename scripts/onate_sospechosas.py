#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
onate_sospechosas.py
────────────────────
Señala las palabras que probablemente son errores de lectura del HTR, para
revisarlas contra el facsímil en vez de leer todo el texto.

Uso:
    python3 scripts/onate_sospechosas.py html/disp63/search_index.js
    python3 scripts/onate_sospechosas.py html/disp63/search_index.js --lila lila/pendientes.tsv
    python3 scripts/onate_sospechosas.py html/disp63/search_index.js --pagina 44

Escribe:
    html/disp63/sospechosas.html    informe con contexto y enlace al facsímil
    revision/sospechosas.tsv        la misma lista, para Emacs u hoja de cálculo

Señales (de más a menos fiable):
  1. CORRECCIÓN PROBABLE  la forma es rara y se parece mucho a una
     forma frecuente del texto, con las confusiones típicas del HTR en
     tipografía antigua: u/n, c/e, l/i, ſ/f (ff/ſſ), r/t, h/b, E/F, rn/m,
     letras dobladas, una letra de más o de menos (instum → iustum,
     prerium → pretium, Leffius → Lessius, lpretia → pretia).
  2. DÍGITOS              letras y cifras mezcladas (7num, 6ap).
  3. SIN LiLa             el lema no existe en LiLa y la forma es rara, pero
     no se parece a ninguna forma frecuente (Reginalddib, Closss).

Solo se examinan las palabras raras (hasta --max-frec apariciones, 3) cuyo lema NO está en
LiLa (lila/pendientes.tsv): así no se proponen formas flexivas correctas
(legem / lege). Contrapartida: un error que produce otra palabra latina
válida (nunc por tunc) no se detecta.

Las formas que revises y estén bien se anotan, una por línea, en
lexico/formas_correctas.txt y dejan de aparecer.
"""
import re
import sys
import json
import html
import argparse
import collections
from pathlib import Path

# coste de sustituir a por b (las confusiones del HTR cuestan menos que 1)
CONF = {}
for a, b, c in [("u", "n", .4), ("c", "e", .4), ("l", "i", .4), ("f", "s", .4),
                ("r", "t", .5), ("h", "b", .5), ("e", "f", .6), ("a", "o", .6),
                ("e", "o", .6), ("i", "t", .6), ("a", "e", .7), ("n", "r", .7),
                ("m", "n", .7), ("q", "g", .6), ("d", "a", .7), ("p", "q", .7)]:
    CONF[(a, b)] = CONF[(b, a)] = c
MULTI = {("rn", "m"): .5, ("in", "m"): .6, ("ii", "u"): .5, ("ii", "n"): .5,
         ("cl", "d"): .5, ("ri", "n"): .6, ("li", "h"): .6, ("vv", "w"): .5}
MULTI.update({(b, a): c for (a, b), c in list(MULTI.items())})


def canon(s):
    """Forma para comparar: minúsculas, ſ→s, v→u, j→i, sin acentos de época."""
    s = s.lower().replace("ſ", "s").replace("v", "u").replace("j", "i")
    s = s.replace("æ", "ae").replace("œ", "oe").replace("ę", "ae")
    for a, b in (("à", "a"), ("á", "a"), ("â", "a"), ("è", "e"), ("é", "e"), ("ê", "e"),
                 ("ì", "i"), ("í", "i"), ("ò", "o"), ("ó", "o"), ("ô", "o"),
                 ("ù", "u"), ("ú", "u"), ("û", "u")):
        s = s.replace(a, b)
    return re.sub(r"[^a-z0-9]", "", s)


def dist(a, b, limit=1.6):
    """Distancia de edición ponderada con las confusiones del HTR."""
    if abs(len(a) - len(b)) > 2:
        return 9
    n, m = len(a), len(b)
    D = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        D[i][0] = D[i - 1][0] + (.5 if i > 1 and a[i - 1] == a[i - 2] else 1)
    for j in range(1, m + 1):
        D[0][j] = D[0][j - 1] + (.5 if j > 1 and b[j - 1] == b[j - 2] else 1)
    for i in range(1, n + 1):
        best = 9
        for j in range(1, m + 1):
            ca, cb = a[i - 1], b[j - 1]
            sub = 0 if ca == cb else CONF.get((ca, cb), 1)
            # letra doblada de más o de menos (Filliuccius / Filliucius) cuesta poco
            dele = .5 if i > 1 and ca == a[i - 2] else 1
            ins = .5 if j > 1 and cb == b[j - 2] else 1
            v = min(D[i - 1][j - 1] + sub, D[i - 1][j] + dele, D[i][j - 1] + ins)
            for (x, y), c in MULTI.items():
                lx, ly = len(x), len(y)
                if i >= lx and j >= ly and a[i - lx:i] == x and b[j - ly:j] == y:
                    v = min(v, D[i - lx][j - ly] + c)
            D[i][j] = v
            best = min(best, v)
        if best > limit:
            return 9
    return D[n][m]


def load_index(path):
    s = Path(path).read_text(encoding="utf-8")
    s = s[s.index("{"): s.rstrip().rstrip(";").rindex("}") + 1]
    d = json.loads(s)
    F = d["fields"]
    toks = [dict(zip(F, r), i=i) for i, r in enumerate(d["tokens"])]
    return d, toks


def load_lila(path):
    """Lemas que LiLa no tiene (estado no_encontrado en lila/pendientes.tsv)."""
    out = set()
    if not path or not Path(path).exists():
        return out
    for line in Path(path).read_text(encoding="utf-8").splitlines()[1:]:
        c = line.split("\t")
        if len(c) > 2 and c[0] == "no_encontrado":
            out.add(c[1])
    return out


ROMAN = re.compile(r"^[ivxlcdm]+$")


def main():
    ap = argparse.ArgumentParser(description="Palabras sospechosas de error de HTR")
    ap.add_argument("index", help="html/disp63/search_index.js")
    ap.add_argument("--lila", default="lila/pendientes.tsv", help="lila/pendientes.tsv (opcional)")
    ap.add_argument("--correctas", default="lexico/formas_correctas.txt",
                    help="formas revisadas que están bien (una por línea)")
    ap.add_argument("--pagina", help="solo esta página (p. ej. 44)")
    ap.add_argument("--min-frec", type=int, default=3, help="frecuencia mínima de la forma sugerida (3)")
    ap.add_argument("--max-frec", type=int, default=3,
                    help="se examinan las formas que aparecen hasta N veces (3): un error sistemático puede repetirse")
    ap.add_argument("--html", default="html/disp63/sospechosas.html")
    ap.add_argument("--tsv", default="revision/sospechosas.tsv")
    a = ap.parse_args()

    d, toks = load_index(a.index)
    no_lila = load_lila(a.lila)
    ok = set()
    if Path(a.correctas).exists():
        ok = {canon(x.split("#")[0]) for x in Path(a.correctas).read_text(encoding="utf-8").splitlines() if x.split("#")[0].strip()}

    words = [t for t in toks if t["p"] != "PUNCT" and canon(t["f"])]
    freq = collections.Counter(canon(t["f"]) for t in words)
    shown = collections.defaultdict(collections.Counter)      # canon → formas tal como aparecen
    for t in words:
        shown[canon(t["f"])][t["f"]] += 1
    _lem = collections.defaultdict(collections.Counter)
    for t in words:
        _lem[canon(t["f"])][t["l"]] += 1
    lemma_of = {w: c.most_common(1)[0][0] for w, c in _lem.items()}
    abbr = lambda t: t["d"].endswith(".")
    freq_abbr = collections.Counter(canon(t["f"]) for t in words if abbr(t))
    frequent = [w for w, n in freq.items() if n >= a.min_frec and len(w) >= 3]
    by_len = collections.defaultdict(list)
    for w in frequent:
        by_len[len(w)].append(w)

    cache = {}

    def suggest(w, is_abbr):
        key = (w, is_abbr)
        if key in cache:
            return cache[key]
        res = []
        for L in range(len(w) - 2, len(w) + 3):
            for c in by_len.get(L, ()):
                if c == w or freq[c] < 3 * freq[w]:
                    continue
                if is_abbr and not freq_abbr[c]:
                    continue
                dd = dist(w, c)
                if dd <= 1.0:
                    res.append((dd, -freq[c], c))
        res.sort()
        cache[key] = res[:3]
        return cache[key]

    found = []
    for t in words:
        if a.pagina and t["pg"] != a.pagina:
            continue
        w = canon(t["f"])
        if w in ok or t["p"] == "NUM" or w.isdigit() or ROMAN.match(w):
            continue
        reasons, sug = [], []
        if re.search(r"\d", w) and re.search(r"[a-z]", w):
            reasons.append("dígitos")
        # palabra desconocida: su lema no está en LiLa (o, sin pendientes.tsv,
        # LatinCy no le encontró lema y devolvió la propia forma)
        unknown = (t["l"] in no_lila) if no_lila else (not t["l"] or canon(t["l"]) == w)
        if unknown and freq[w] <= a.max_frec and len(w) >= 4:
            # una forma flexiva del mismo lema no es una corrección (legem / lege)
            sug = [x for x in suggest(w, abbr(t)) if lemma_of[x[2]] != t["l"]]
            if sug:
                reasons.insert(0, "corrección probable")
            elif not abbr(t):
                reasons.append("sin LiLa")
        if reasons:
            found.append((t, reasons, sug))

    # ── salidas ──────────────────────────────────────────────────────────────
    prio = lambda r: 0 if "corrección probable" in r else 1 if "dígitos" in r else 2
    order = lambda v: (int(v) if str(v).isdigit() else 9999, str(v))
    found.sort(key=lambda x: (order(x[0]["pg"]), x[0]["c"], int(x[0]["ln"]) if str(x[0]["ln"]).isdigit() else 0))
    pref = d.get("colPrefix", "pg_63_")

    def ctx(t, k=5):
        i = t["i"]
        span = [x for x in toks[max(0, i - k): i + k + 1] if (x["pg"], x["c"]) == (t["pg"], t["c"])]
        out = " ".join(f'<b>{html.escape(x["d"])}</b>' if x["i"] == i else html.escape(x["d"]) for x in span)
        return re.sub(r" ([.,;:?!)])", r"\1", out)

    def sug_txt(sug):
        return ", ".join(f'{shown[c].most_common(1)[0][0]} ({freq[c]})' for _, _, c in sug)

    tsv = Path(a.tsv); tsv.parent.mkdir(parents=True, exist_ok=True)
    with tsv.open("w", encoding="utf-8") as fh:
        fh.write("columna\tlinea\tforma\tsugerencia\tmotivo\tprioridad\n")
        for t, r, s in found:
            fh.write(f'{pref}{t["pg"]}_{t["c"]}\t{t["ln"]}\t{t["d"]}\t{sug_txt(s)}\t{"; ".join(r)}\t{"ABC"[prio(r)]}\n')

    groups = collections.OrderedDict()
    for x in found:
        groups.setdefault((x[0]["pg"], x[0]["c"]), []).append(x)
    n_by = collections.Counter(prio(r) for _, r, _ in found)
    sections = []
    for (pg, c), items in groups.items():
        rows = []
        for t, r, s in items:
            href = "disp63_facs.html#" + html.escape(f'{pref}{pg}_{c}%3A{t["ln"]}%3A{t["d"]}%3A{t.get("o", 0)}')
            p = prio(r)
            rows.append(
                f'<tr class="p{p}"><td class="n">{html.escape(str(t["ln"]))}</td>'
                f'<td><i>{html.escape(t["d"])}</i></td>'
                f'<td>{html.escape(sug_txt(s)) or "—"}</td>'
                f'<td class="m">{html.escape("; ".join(r))}</td>'
                f'<td>{ctx(t)}</td>'
                f'<td><a href="{href}" target="onate_facs">facs ↗</a></td></tr>')
        sections.append(
            f'<h2 id="{pref}{pg}_{c}">p. {html.escape(str(pg))} · {html.escape(c)} '
            f'<span>{pref}{pg}_{c} · {len(items)}</span></h2>'
            '<div class="box"><table><thead><tr><th>Línea</th><th>Forma</th><th>Sugerencia (apariciones)</th>'
            '<th>Motivo</th><th>Contexto</th><th></th></tr></thead><tbody>' + "".join(rows) + "</tbody></table></div>")
    toc = " ".join(f'<a href="#{pref}{pg}_{c}">{pg} {c} <small>{len(v)}</small></a>' for (pg, c), v in groups.items())

    page = f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Palabras sospechosas</title>
<style>
:root {{ --bg:#f4f6f4; --surface:#fff; --fg:#1c2321; --muted:#5b6763; --rule:#d5dcd8; --hi:#fdeee0; --a:#b4532a; --b:#8a6a1e; --c:#5b6763; --link:#1d6b64; --seen:#7a4d8f; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#131816; --surface:#1a201e; --fg:#e3e8e5; --muted:#98a59f; --rule:#2f3835; --hi:#4a3423; --a:#e58b62; --b:#d6b25e; --c:#98a59f; --link:#6cc3b8; --seen:#c39ad6; }} }}
body {{ margin:0; background:var(--bg); color:var(--fg); font:15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }}
.wrap {{ max-width:1150px; margin:0 auto; padding:24px 20px 60px; }}
h1 {{ font:italic 500 34px Georgia, serif; margin:0 0 4px; }}
h2 {{ font:600 15px system-ui; margin:28px 0 8px; }} h2 span {{ font:12px ui-monospace, Menlo, monospace; color:var(--muted); margin-left:8px; }}
p {{ color:var(--muted); max-width:80ch; }}
.bar {{ position:sticky; top:0; background:var(--bg); padding:10px 0; border-bottom:1px solid var(--rule); display:flex; flex-wrap:wrap; gap:6px 12px; align-items:center; z-index:2; }}
.bar label {{ font-size:14px; }} .toc a {{ font:12px ui-monospace, Menlo, monospace; color:var(--link); text-decoration:none; margin-right:8px; white-space:nowrap; }}
.box {{ background:var(--surface); border:1px solid var(--rule); border-radius:8px; overflow-x:auto; }}
table {{ border-collapse:collapse; width:100%; font-size:14px; }}
th {{ text-align:left; font-size:11.5px; text-transform:uppercase; letter-spacing:.05em; color:var(--muted); padding:8px 10px; border-bottom:1px solid var(--rule); }}
td {{ padding:7px 10px; border-top:1px solid var(--rule); vertical-align:top; }} td i {{ font:italic 16px Georgia, serif; }}
tr.p0 td:first-child {{ box-shadow:inset 3px 0 var(--a); }} tr.p1 td:first-child {{ box-shadow:inset 3px 0 var(--b); }} tr.p2 td:first-child {{ box-shadow:inset 3px 0 var(--c); }}
.n {{ font-variant-numeric:tabular-nums; text-align:right; }} .m {{ font:12px ui-monospace, Menlo, monospace; color:var(--muted); }}
b {{ background:var(--hi); font-weight:500; }} a {{ color:var(--link); }} a:visited {{ color:var(--seen); }}
.hide-b tr.p1, .hide-b tr.p2 {{ display:none; }}
</style></head><body><div class="wrap">
<h1>Palabras sospechosas</h1>
<p>{len(found)} palabras para revisar contra el facsímil: {n_by[0]} con corrección probable, {n_by[1]} con dígitos,
{n_by[2]} raras y sin lema en LiLa. Fuente: {html.escape(d.get("source", "search_index.js"))} ({html.escape(d.get("generated", ""))}).
Los errores de lectura se corrigen en Transkribus (o en el staging) y se reprocesa la página; las formas que estén bien
se anotan en <code>lexico/formas_correctas.txt</code> para que no vuelvan a aparecer.</p>
<div class="bar"><label><input type="checkbox" id="only"> solo correcciones probables</label><span class="toc">{toc}</span></div>
<div id="list">{"".join(sections) or "<p>Nada que revisar.</p>"}</div>
</div>
<script>
document.getElementById("only").onchange = e => document.getElementById("list").classList.toggle("hide-b", e.target.checked);
</script></body></html>"""
    out = Path(a.html); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    print(f"✓ {len(found)} sospechosas ({n_by[0]} corrección probable, {n_by[1]} dígitos, {n_by[2]} sin LiLa)"
          + (f" — {len(no_lila)} lemas sin LiLa leídos de {a.lila}" if no_lila else " — sin lila/pendientes.tsv"), file=sys.stderr)
    print(f"  → {out}\n  → {tsv}", file=sys.stderr)


if __name__ == "__main__":
    main()
