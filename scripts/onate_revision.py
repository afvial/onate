#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
onate_revision.py
─────────────────
Panel de revisión por página-columna: lo que falta por corregir, en un solo
HTML, para ir trabajando columna a columna.

Uso:
    python3 scripts/onate_revision.py
    (opciones: --index html/disp63/search_index.js --pendientes lila/pendientes.tsv
               --sospechosas revision/sospechosas.tsv --out html/disp63/revision.html)

Reúne:
  · Lectura (HTR): las palabras sospechosas de revision/sospechosas.tsv
    (genéralo antes con onate_sospechosas.py).
  · LiLa: los lemas de lila/pendientes.tsv que aparecen en la columna:
      ambiguo        LiLa tiene varios lemas con esa forma → elegir uno
      pos_distinta   la categoría de LatinCy no coincide con la de LiLa
                     (o el lema está mal: corregirlo en nlp_corrections)
      no_encontrado  LiLa no tiene el lema (errata, nombre propio, abreviatura…)
      pos_alternativo  enlazado con otra categoría (solo informativo, oculto)
    Cada propuesta trae la línea lista para copiar a lila/excepciones.tsv.

Cada aparición enlaza a su línea en el facsímil. Lo que marques como
«revisado» se recuerda en este navegador.
"""
import re
import json
import html
import argparse
import datetime
import collections
from pathlib import Path


def load_index(path):
    p = Path(path)
    if not p.exists():
        return {}, []
    s = p.read_text(encoding="utf-8")
    s = s[s.index("{"): s.rstrip().rstrip(";").rindex("}") + 1]
    d = json.loads(s)
    F = d["fields"]
    return d, [dict(zip(F, r), i=i) for i, r in enumerate(d["tokens"])]


def parse_locs(s):
    """'pg_63_35_der l.11,34; pg_63_36_izq l.15' → {'pg_63_35_der': ['11','34'], …}"""
    out = collections.OrderedDict()
    for part in (s or "").split(";"):
        m = re.match(r"\s*(\S+)\s+l\.(.*)$", part)
        if m:
            out[m.group(1)] = [x.strip() for x in m.group(2).split(",") if x.strip()]
    return out


def parse_cands(s):
    """'lila:76484 noun; lila:122962 noun (variante)' → [{'ref','info'}]"""
    out = []
    for part in (s or "").split(";"):
        part = part.strip()
        if part:
            ref, _, info = part.partition(" ")
            out.append({"ref": ref, "info": info.strip()})
    return out


def main():
    ap = argparse.ArgumentParser(description="Panel de revisión por página-columna")
    ap.add_argument("--index", default="html/disp63/search_index.js")
    ap.add_argument("--pendientes", default="lila/pendientes.tsv")
    ap.add_argument("--sospechosas", default="revision/sospechosas.tsv")
    ap.add_argument("--out", default="html/disp63/revision.html")
    a = ap.parse_args()

    meta, toks = load_index(a.index)
    pref = meta.get("colPrefix", "pg_63_")
    # (columna, línea, lema) → primera palabra con ese lema, para el enlace y el contexto
    where = {}
    by_col = collections.defaultdict(list)
    for t in toks:
        col = f'{pref}{t["pg"]}_{t["c"]}'
        by_col[col].append(t)
        where.setdefault((col, str(t["ln"]), t["l"]), t)
    pos_in_col = {}
    for col, lst in by_col.items():
        for k, t in enumerate(lst):
            pos_in_col[t["i"]] = (col, k)

    def context(t, k=4):
        col, j = pos_in_col[t["i"]]
        lst = by_col[col]
        span = lst[max(0, j - k): j + k + 1]
        txt = " ".join(("[[" + x["d"] + "]]") if x["i"] == t["i"] else x["d"] for x in span)
        return re.sub(r" ([.,;:?!)])", r"\1", txt)

    cols = collections.OrderedDict()
    for col in sorted(by_col, key=lambda c: (int(re.sub(r"\D", "", c.split("_")[2]) or 0), c)):
        cols[col] = {"htr": [], "lila": []}

    # ── lectura (HTR) ────────────────────────────────────────────────────────
    n_sosp = 0
    sp = Path(a.sospechosas)
    if sp.exists():
        for line in sp.read_text(encoding="utf-8").splitlines()[1:]:
            c = line.split("\t")
            if len(c) < 6:
                continue
            col, ln, forma, sug, motivo, prio = c[:6]
            ctx = ""
            for t in by_col.get(col, []):
                if str(t["ln"]) == ln and t["d"] == forma:
                    ctx = context(t); break
            cols.setdefault(col, {"htr": [], "lila": []})["htr"].append(
                dict(ln=ln, f=forma, s=sug, m=motivo, p=prio, ctx=ctx))
            n_sosp += 1

    # ── LiLa ─────────────────────────────────────────────────────────────────
    n_lila = collections.Counter()
    pp = Path(a.pendientes)
    if pp.exists():
        for line in pp.read_text(encoding="utf-8").splitlines()[1:]:
            c = line.split("\t")
            if len(c) < 7:
                continue
            estado, lema, upos, asignado, cands, n, ubic = c[:7]
            locs = parse_locs(ubic)
            n_lila[estado] += 1
            for col, lines in locs.items():
                occ = []
                for ln in lines:
                    t = where.get((col, ln, lema))
                    occ.append(dict(ln=ln, f=t["d"] if t else "", o=t.get("o", 0) if t else 0,
                                    ctx=context(t) if t else ""))
                cols.setdefault(col, {"htr": [], "lila": []})["lila"].append(
                    dict(e=estado, l=lema, u=upos, a=asignado, c=parse_cands(cands),
                         n=int(n or 0), ncols=len(locs), occ=occ))

    data = dict(prefix=pref, cols=cols,
                generated=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                src=dict(index=meta.get("generated", ""), sosp=sp.exists(), lila=pp.exists()))
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(PAGE.replace("/*DATA*/", json.dumps(data, ensure_ascii=False, separators=(",", ":"))),
                   encoding="utf-8")
    print(f"✓ {len(cols)} columnas · {n_sosp} sospechosas · LiLa: "
          + ", ".join(f"{k} {v}" for k, v in n_lila.most_common()))
    print(f"  → {out}")


PAGE = r"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Revisión por columna</title>
<style>
:root { --bg:#f4f6f4; --surface:#fff; --fg:#1c2321; --muted:#5b6763; --rule:#d5dcd8; --hi:#fdeee0;
  --a:#b4532a; --b:#8a6a1e; --c:#5b6763; --link:#1d6b64; --ok:#2f7d4f; --ok-bg:#e6f2ea; --chip:#eef1ef; }
@media (prefers-color-scheme: dark) { :root { --bg:#131816; --surface:#1a201e; --fg:#e3e8e5; --muted:#98a59f;
  --rule:#2f3835; --hi:#4a3423; --a:#e58b62; --b:#d6b25e; --c:#98a59f; --link:#6cc3b8; --ok:#7fc79a; --ok-bg:#1f3327; --chip:#232b28; } }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--fg); font:15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
.wrap { max-width:1150px; margin:0 auto; padding:24px 20px 60px; }
h1 { font:italic 500 32px Georgia, serif; margin:0; }
.sub { color:var(--muted); font-size:13px; margin:4px 0 18px; }
h2 { font:600 13px system-ui; letter-spacing:.06em; text-transform:uppercase; color:var(--muted); margin:26px 0 8px; }
h2 span { text-transform:none; letter-spacing:0; font-weight:400; }
.grid { display:flex; flex-wrap:wrap; gap:6px; }
.cb { border:1px solid var(--rule); background:var(--surface); color:var(--fg); border-radius:7px; padding:6px 9px; cursor:pointer;
  font:13px ui-monospace, Menlo, monospace; display:flex; flex-direction:column; gap:2px; min-width:92px; text-align:left; }
.cb b { font-weight:600; } .cb small { color:var(--muted); font-size:11px; }
.cb.on { outline:2px solid var(--link); outline-offset:-1px; }
.cb.done { background:var(--ok-bg); border-color:var(--ok); }
.bar { position:sticky; top:0; z-index:2; background:var(--bg); padding:10px 0; border-bottom:1px solid var(--rule);
  display:flex; gap:10px 16px; flex-wrap:wrap; align-items:center; }
.bar h3 { margin:0; font:italic 500 22px Georgia, serif; }
.bar label { font-size:13.5px; color:var(--muted); }
.bar a { color:var(--link); font-size:13.5px; }
.box { background:var(--surface); border:1px solid var(--rule); border-radius:8px; overflow-x:auto; }
table { border-collapse:collapse; width:100%; font-size:14px; }
th { text-align:left; font-size:11.5px; text-transform:uppercase; letter-spacing:.05em; color:var(--muted); padding:8px 10px; border-bottom:1px solid var(--rule); white-space:nowrap; }
td { padding:7px 10px; border-top:1px solid var(--rule); vertical-align:top; }
td i { font:italic 16px Georgia, serif; }
tr.pA td:first-child { box-shadow:inset 3px 0 var(--a); } tr.pB td:first-child { box-shadow:inset 3px 0 var(--b); } tr.pC td:first-child { box-shadow:inset 3px 0 var(--c); }
tr.seen { opacity:.45; }
.m { font:12px ui-monospace, Menlo, monospace; color:var(--muted); }
.n { text-align:right; font-variant-numeric:tabular-nums; }
.ctx { font-size:13.5px; color:var(--muted); } .ctx b { color:var(--fg); background:var(--hi); font-weight:500; }
a { color:var(--link); }
.est { display:inline-block; font:11px ui-monospace, Menlo, monospace; padding:1px 6px; border-radius:4px; background:var(--chip); white-space:nowrap; }
.cand { display:flex; flex-wrap:wrap; gap:6px; margin-top:4px; }
.copy { font:12px ui-monospace, Menlo, monospace; border:1px solid var(--rule); background:var(--chip); color:var(--fg); border-radius:5px; padding:3px 7px; cursor:pointer; }
.copy:hover { border-color:var(--link); } .copy.ok { border-color:var(--ok); color:var(--ok); }
.help { font-size:13px; color:var(--muted); margin:6px 0 10px; max-width:85ch; }
.empty { padding:14px; color:var(--muted); font-size:14px; }
.occ { display:block; margin:2px 0; }
input[type=checkbox] { accent-color:var(--link); }
</style></head><body><div class="wrap">
<h1>Revisión por columna</h1>
<div class="sub" id="sub"></div>

<h2>Columnas <span>· pendientes de lectura (HTR) y de LiLa; en verde, las que no tienen nada pendiente</span></h2>
<div class="grid" id="grid"></div>

<div class="bar">
  <h3 id="ctitle">—</h3>
  <label><input type="checkbox" id="alt"> mostrar «pos_alternativo»</label>
  <label><input type="checkbox" id="hideSeen"> ocultar lo revisado</label>
  <a id="facs" target="onate_facs" href="#">abrir en el facsímil ↗</a>
</div>

<h2>Lectura (HTR) <span id="nh"></span></h2>
<div class="help">Erratas probables del reconocimiento. Corregir en Transkribus (o en el staging), merge y reprocesar.
Las formas correctas van a <code>lexico/formas_correctas.txt</code>.</div>
<div class="box" id="htr"></div>

<h2>LiLa <span id="nl"></span></h2>
<div class="help">Lemas sin enlace. Un lema ambiguo o de categoría distinta se resuelve una sola vez para todo el texto:
copia la línea propuesta en <code>lila/excepciones.tsv</code> y reprocesa. Si es una errata, corrígela en el texto y desaparecerá de aquí.</div>
<div class="box" id="lila"></div>
</div>

<script>
const D = /*DATA*/;
const $ = id => document.getElementById(id);
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const ctx = s => esc(s).replace(/\[\[(.*?)\]\]/g, "<b>$1</b>");
const EST = { ambiguo: "elegir lema", pos_distinta: "categoría distinta", no_encontrado: "no está en LiLa", pos_alternativo: "enlazado (otra categoría)" };
const ORDER = { ambiguo: 0, pos_distinta: 1, no_encontrado: 2, pos_alternativo: 3 };
const store = { get(k) { try { return JSON.parse(localStorage.getItem("onate_rev") || "{}")[k]; } catch (e) { return undefined; } },
  set(k, v) { try { const o = JSON.parse(localStorage.getItem("onate_rev") || "{}"); if (v) o[k] = v; else delete o[k]; localStorage.setItem("onate_rev", JSON.stringify(o)); } catch (e) {} } };
const COLS = Object.keys(D.cols);
let cur = (decodeURIComponent(location.hash.slice(1)) in D.cols) ? decodeURIComponent(location.hash.slice(1)) : (store.get("_col") in D.cols ? store.get("_col") : COLS[0]);

$("sub").textContent = `Generado ${D.generated} · índice ${D.src.index || "—"}` +
  (D.src.sosp ? "" : " · sin revision/sospechosas.tsv (ejecuta onate_sospechosas.py)") +
  (D.src.lila ? "" : " · sin lila/pendientes.tsv");

const facs = (col, ln, f, o) => "disp63_facs.html#" + encodeURIComponent(f ? `${col}:${ln}:${f}:${o || 0}` : `${col}:${ln}`);
const label = col => col.replace(D.prefix, "p. ").replace(/_(izq|der|unica|c\d)$/, " · $1");
const counts = col => { const c = D.cols[col];
  return { h: c.htr.length, l: c.lila.filter(x => x.e !== "pos_alternativo").length }; };

function grid() {
  $("grid").innerHTML = COLS.map(col => { const k = counts(col);
    return `<button type="button" class="cb${col === cur ? " on" : ""}${k.h + k.l === 0 ? " done" : ""}" data-col="${col}">
      <b>${esc(label(col))}</b><small>HTR ${k.h} · LiLa ${k.l}</small></button>`; }).join("");
}
function copyText(btn, txt) {
  const done = () => { btn.classList.add("ok"); const t = btn.textContent; btn.textContent = "copiado ✓"; setTimeout(() => { btn.textContent = t; btn.classList.remove("ok"); }, 1300); };
  if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(txt).then(done, () => fallback());
  else fallback();
  function fallback() { const ta = document.createElement("textarea"); ta.value = txt; document.body.appendChild(ta); ta.select();
    try { document.execCommand("copy"); done(); } catch (e) { prompt("Copia esta línea:", txt); } ta.remove(); }
}
function seenBox(key) { return `<input type="checkbox" class="seen" data-k="${esc(key)}" ${store.get(key) ? "checked" : ""} title="revisado">`; }

function render() {
  store.set("_col", cur);
  history.replaceState(null, "", "#" + cur);
  grid();
  const c = D.cols[cur], hide = $("hideSeen").checked;
  $("ctitle").textContent = label(cur);
  $("facs").href = facs(cur, 1);

  const H = c.htr.filter(x => !(hide && store.get(`h|${cur}|${x.ln}|${x.f}`)));
  $("nh").textContent = `· ${c.htr.length}`;
  $("htr").innerHTML = H.length ? `<table><thead><tr><th></th><th>Línea</th><th>Forma</th><th>Sugerencia</th><th>Motivo</th><th>Contexto</th><th></th></tr></thead><tbody>` +
    H.map(x => { const k = `h|${cur}|${x.ln}|${x.f}`;
      return `<tr class="p${x.p}${store.get(k) ? " seen" : ""}"><td>${seenBox(k)}</td><td class="n">${esc(x.ln)}</td><td><i>${esc(x.f)}</i></td>
        <td>${esc(x.s) || "—"}</td><td class="m">${esc(x.m)}</td><td class="ctx">${ctx(x.ctx)}</td>
        <td><a href="${facs(cur, x.ln, x.f)}" target="onate_facs">facs ↗</a></td></tr>`; }).join("") + "</tbody></table>"
    : `<div class="empty">Nada pendiente de lectura en esta columna.</div>`;

  const L = c.lila.filter(x => ($("alt").checked || x.e !== "pos_alternativo") && !(hide && store.get(`l|${x.e}|${x.l}|${x.u}`)))
    .sort((a, b) => ORDER[a.e] - ORDER[b.e] || b.n - a.n);
  $("nl").textContent = `· ${c.lila.filter(x => x.e !== "pos_alternativo").length}`;
  $("lila").innerHTML = L.length ? `<table><thead><tr><th></th><th>Lema</th><th>Estado</th><th class="n">Total</th><th>En esta columna</th><th>Resolver en excepciones.tsv</th></tr></thead><tbody>` +
    L.map(x => { const k = `l|${x.e}|${x.l}|${x.u}`;
      let props = [];
      if (x.e === "ambiguo") props = x.c.map(c => ({ t: `${x.l}\t${x.u}\t${c.ref}\t`, lab: `${c.ref} ${c.info}` }));
      else if (x.e === "pos_distinta") {
        const none = { t: `${x.l}\t${x.u}\t-\t${x.u === "PROPN" ? "nombre propio: no enlazar" : ""}`, lab: x.u === "PROPN" ? "nombre propio: no enlazar (–)" : "no enlazar (–)" };
        const link = x.c.map(c => ({ t: `${x.l}\t*\t${c.ref}\t${c.info}; LatinCy: ${x.u}`, lab: `${c.ref} ${c.info} (cualquier categoría)` }));
        props = x.u === "PROPN" ? [none, ...link] : [...link, none];
      }
      else if (x.e === "no_encontrado") props = [{ t: `${x.l}\t${x.u}\t-\t`, lab: "no enlazar (–)" }];
      const occ = x.occ.map(o => `<span class="occ"><a href="${facs(cur, o.ln, o.f, o.o)}" target="onate_facs">l. ${esc(o.ln)}</a>
        <span class="ctx">${ctx(o.ctx)}</span></span>`).join("");
      return `<tr class="${store.get(k) ? "seen" : ""}"><td>${seenBox(k)}</td>
        <td><i>${esc(x.l)}</i><br><span class="m">${esc(x.u)}${x.a ? " → " + esc(x.a) : ""}</span></td>
        <td><span class="est">${esc(EST[x.e] || x.e)}</span></td>
        <td class="n">${x.n}<br><span class="m">${x.ncols} col.</span></td>
        <td>${occ}</td>
        <td>${props.length ? `<div class="cand">${props.map(p => `<button type="button" class="copy" data-t="${esc(p.t)}" title="${esc(p.t)}">${esc(p.lab)}</button>`).join("")}</div>`
          : `<span class="m">—</span>`}${x.e === "no_encontrado" ? `<div class="m" style="margin-top:4px">si es errata: corregir el texto</div>`
          : x.e === "pos_distinta" ? `<div class="m" style="margin-top:4px">si el lema está mal (p. ej. vendi → uo): nlp_corrections</div>` : ""}</td></tr>`; }).join("") +
    "</tbody></table>" : `<div class="empty">Nada pendiente de LiLa en esta columna.</div>`;
}

document.addEventListener("click", e => {
  const b = e.target.closest(".cb"); if (b) { cur = b.dataset.col; render(); scrollTo({ top: $("ctitle").offsetTop - 10 }); return; }
  const cp = e.target.closest(".copy"); if (cp) { copyText(cp, cp.dataset.t); return; }
});
document.addEventListener("change", e => {
  if (e.target.matches(".seen")) { store.set(e.target.dataset.k, e.target.checked); e.target.closest("tr").classList.toggle("seen", e.target.checked); if ($("hideSeen").checked) render(); }
  if (e.target.id === "alt" || e.target.id === "hideSeen") render();
});
document.addEventListener("keydown", e => {
  if (e.target.matches("input, textarea")) return;
  const i = COLS.indexOf(cur);
  if (e.key === "ArrowRight" && i < COLS.length - 1) { cur = COLS[i + 1]; render(); }
  if (e.key === "ArrowLeft" && i > 0) { cur = COLS[i - 1]; render(); }
});
window.addEventListener("hashchange", () => { const h = decodeURIComponent(location.hash.slice(1)); if (h in D.cols && h !== cur) { cur = h; render(); } });
render();
</script></body></html>
"""

if __name__ == "__main__":
    main()
