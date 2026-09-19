#!/usr/bin/env python3
"""
onate_bilingual_html.py — HTML bilingüe (transcripción | traducción) para una
columna de página, a partir del TEI ya anotado por onate_nlp.py (+ corregido
opcionalmente por onate_nlp_corrections.py).

Reutiliza el mismo lenguaje de clases que onate_tei2html.xsl:
  - span.tei-w con data-lemma / data-pos / data-msd
  - tooltip como <table> (tip-key / tip-lemma / tip-pos / tip-feat / tip-expan)
  - span.tei-choice-abbr (abreviatura) / span.tei-choice-orig (grafía original)
  - colores por POS y leyenda

Uso:
    python3 onate_bilingual_html.py <src_xml> <translations_json> \
        [--corrections <nlp_corrections_json>] --out <html_out>

<translations_json>:
    {"sentences": [{"n": 1, "es": "..."}, ...]}

<nlp_corrections_json>  (mismo formato que usa onate_nlp_corrections.py):
    {"palabra": "Case=Acc"}                     -> fusiona ese campo en el msd
    {"palabra": "lemma=x,pos=Y,Case=Acc,..."}    -> sobreescritura completa
    Se usa aquí solo para *marcar visualmente* qué palabras fueron corregidas
    (el XML de entrada ya debería traer los valores corregidos si pasó por
    onate_nlp_corrections.py; este script es idempotente si se le vuelve a
    aplicar la misma corrección).
"""
import argparse
import json
import html
from lxml import etree

NS = {"tei": "http://www.tei-c.org/ns/1.0"}


def local(tag):
    return tag.split("}")[-1] if "}" in tag else tag


def diplomatic_text(el):
    tag = local(el.tag)
    if tag == "lb":
        return ""
    if tag == "choice":
        chosen = None
        for pref in ("orig", "abbr"):
            for child in el:
                if local(child.tag) == pref:
                    chosen = child
                    break
            if chosen is not None:
                break
        if chosen is None and len(el):
            chosen = el[0]
        return diplomatic_text(chosen) if chosen is not None else ""
    parts = []
    if tag in ("w", "pc"):
        parts.append(el.text or "")
    for child in el:
        if local(child.tag) == "lb":
            parts.append(child.tail or "")
        else:
            parts.append(diplomatic_text(child))
    return "".join(parts).strip()


def find_meta_w(el):
    tag = local(el.tag)
    if tag == "w":
        return el if el.get("lemma") else None
    for pref in ("expan", "reg", "abbr", "orig"):
        for child in el.iter():
            if local(child.tag) == pref:
                for w in child.iter():
                    if local(w.tag) == "w" and w.get("lemma"):
                        return w
    return None


def choice_kind(el):
    if local(el.tag) != "choice":
        return None
    for child in el:
        if local(child.tag) == "abbr":
            return "abbr"
    return "orig"


def parse_correction_spec(spec, existing_meta):
    kv = {}
    for part in spec.split(","):
        part = part.strip()
        if "=" in part:
            k, v = part.split("=", 1)
            kv[k.strip()] = v.strip()

    full_override = "lemma" in kv or "pos" in kv
    existing_meta = existing_meta or {}

    if full_override:
        lemma = kv.pop("lemma", existing_meta.get("lemma"))
        pos = kv.pop("pos", existing_meta.get("pos"))
        msd = "|".join(f"{k}={v}" for k, v in sorted(kv.items()))
    else:
        msd_fields = {}
        if existing_meta.get("msd"):
            for field in existing_meta["msd"].split("|"):
                if "=" in field:
                    fk, fv = field.split("=", 1)
                    msd_fields[fk] = fv
        msd_fields.update(kv)
        lemma = existing_meta.get("lemma")
        pos = existing_meta.get("pos")
        msd = "|".join(f"{k}={v}" for k, v in sorted(msd_fields.items()))

    return {"lemma": lemma, "pos": pos, "msd": msd, "_corrected": True, "_spec": spec}


def tokenize_sentence(s_el, corrections):
    tokens = []
    for child in s_el:
        tag = local(child.tag)
        if tag == "lb":
            continue
        if tag == "pc":
            tokens.append({"text": child.text or "", "punct": True})
            continue
        if tag in ("w", "choice"):
            text = diplomatic_text(child)
            meta_el = find_meta_w(child)
            meta = None
            if meta_el is not None:
                meta = {"lemma": meta_el.get("lemma"), "pos": meta_el.get("pos"), "msd": meta_el.get("msd")}
            if corrections and text in corrections:
                meta = parse_correction_spec(corrections[text], meta)
            kind = choice_kind(child) if tag == "choice" else None
            tokens.append({"text": text, "punct": False, "meta": meta, "choice_kind": kind})
    return tokens


def render_tooltip_table(meta):
    rows = []
    lemma = meta.get("lemma") or ""
    rows.append(f'<tr><td class="tip-key">lemma</td><td class="tip-lemma">{html.escape(lemma)}</td></tr>')
    if meta.get("pos"):
        rows.append(f'<tr><td class="tip-key">POS</td><td class="tip-pos">{html.escape(meta["pos"])}</td></tr>')
    if meta.get("msd"):
        for field in meta["msd"].split("|"):
            if "=" in field:
                k, v = field.split("=", 1)
                rows.append(f'<tr><td class="tip-key">{html.escape(k)}</td><td class="tip-feat">{html.escape(v)}</td></tr>')
    if meta.get("_corrected"):
        rows.append(f'<tr><td class="tip-key">corregido</td><td class="tip-expan">{html.escape(meta.get("_spec",""))}</td></tr>')
    return "<table>" + "".join(rows) + "</table>"


def render_sentence_html(tokens):
    pieces = []
    for i, tok in enumerate(tokens):
        text = html.escape(tok["text"])
        if tok["punct"]:
            pieces.append(text)
            continue
        prefix = "" if i == 0 else " "
        classes = ["tei-w"]
        if tok.get("choice_kind"):
            classes.append(f'tei-choice-{tok["choice_kind"]}')
        if tok["meta"] and tok["meta"].get("_corrected"):
            classes.append("tei-corrected")
        meta = tok["meta"] or {}
        span_attrs = (
            f'class="{" ".join(classes)}" '
            f'data-lemma="{html.escape(meta.get("lemma") or "")}" '
            f'data-pos="{html.escape(meta.get("pos") or "")}" '
            f'data-msd="{html.escape(meta.get("msd") or "")}"'
        )
        tooltip = f'<span class="tooltip">{render_tooltip_table(meta)}</span>' if meta else ""
        pieces.append(f'{prefix}<span {span_attrs}>{tooltip}{text}</span>')
    return "".join(pieces)


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>Oñate · De contractibus · Disp. LXIII · Pag. {page_num}</title>
<style>
  body {{ font-family: Georgia, "Times New Roman", serif; background: #faf8f2; color: #1a1a1a;
         max-width: 76rem; margin: 0 auto; padding: 2rem 1.5rem 4rem; }}
  h1 {{ font-size: 1.3rem; margin-bottom: 0.1rem; }}
  h2 {{ font-size: 1rem; color: #555; font-weight: normal; margin-top: 0; }}

  .bilingual {{ display: grid; grid-template-columns: 1fr 1px 1fr; gap: 0 2rem; margin-top: 2rem; }}
  .col-sep {{ background: #ccc; }}
  .col-head {{ font-size: 0.72rem; letter-spacing: 0.08em; text-transform: uppercase;
               color: #8a6a2a; margin-bottom: 1rem; }}

  .sentence {{ padding: 1.1rem 0; border-bottom: 1px dashed #ccc; }}
  .sentence:first-child {{ padding-top: 0; }}
  .s-num {{ font-size: 0.68rem; color: #999; margin-bottom: 0.35rem; }}

  p.latin {{ line-height: 2.1; font-size: 1.08rem; }}
  p.translation {{ line-height: 1.9; font-size: 1.02rem; }}

  span.tei-w {{
    display: inline; position: relative; cursor: default;
    border-bottom: 1px dotted transparent; transition: border-color 0.15s;
  }}
  span.tei-w:hover {{ border-bottom: 1px dotted #7a9abf; }}
  span.tei-w[data-pos="VERB"]  {{ color: #1a4a8a; }}
  span.tei-w[data-pos="NOUN"]  {{ color: #222; }}
  span.tei-w[data-pos="ADJ"]   {{ color: #3a6a3a; }}
  span.tei-w[data-pos="ADV"]   {{ color: #7a4a00; }}
  span.tei-w[data-pos="ADP"]   {{ color: #666; }}
  span.tei-w[data-pos="CCONJ"] {{ color: #888; }}
  span.tei-w[data-pos="SCONJ"] {{ color: #888; }}
  span.tei-w[data-pos="PRON"]  {{ color: #7a2a7a; }}
  span.tei-w[data-pos="DET"]   {{ color: #7a2a7a; }}
  span.tei-w[data-pos="AUX"]   {{ color: #1a4a8a; }}
  span.tei-w[data-pos="PART"]  {{ color: #888; }}

  span.tei-choice-abbr {{ border-bottom: 1px dotted #8a6a2a; }}
  span.tei-choice-orig {{ border-bottom: 1px dotted #999; }}
  span.tei-corrected {{ border-bottom: 1px dashed #b5432f; }}
  span.tei-hi-italic {{ font-style: italic; }}

  span.tei-w .tooltip {{
    display: none; position: absolute; bottom: 1.6em; left: 0;
    background: #2a2a2a; color: #fff; font-size: 0.68rem;
    font-family: "SF Mono", Menlo, Consolas, monospace;
    padding: 0.3em 0.6em; border-radius: 4px; white-space: nowrap;
    z-index: 10; pointer-events: none; line-height: 1.6;
    box-shadow: 0 2px 6px rgba(0,0,0,0.4);
  }}
  span.tei-w:hover .tooltip {{ display: block; }}
  .tooltip table {{ border-collapse: collapse; }}
  .tooltip td {{ padding: 0 0.4em 0 0; vertical-align: top; }}
  .tooltip .tip-key   {{ color: #888; font-size: 0.63rem; }}
  .tooltip .tip-lemma {{ color: #7ec8e3; font-weight: bold; }}
  .tooltip .tip-pos   {{ color: #f0c060; }}
  .tooltip .tip-feat  {{ color: #aaddaa; }}
  .tooltip .tip-expan {{ color: #f0a060; }}

  .legend {{ margin-top: 2.5rem; padding: 0.8rem 1rem; background: #f0f0e8; border-radius: 4px; font-size: 0.82rem; }}
  .legend h3 {{ margin: 0 0 0.4rem 0; font-size: 0.9rem; }}
  .legend span {{ margin-right: 1rem; }}
  .stats {{ font-size: 0.8rem; color: #777; text-align: right; margin-top: 0.5rem; }}
  .pending {{ margin-top: 2rem; padding-top: 1rem; border-top: 1px dashed #ccc; font-size: 0.85rem; color: #777; }}
  .pending ul {{ margin: 0.5rem 0 0; padding-left: 1.2rem; }}

  @media (max-width: 640px) {{
    .bilingual {{ grid-template-columns: 1fr; gap: 1.5rem 0; }}
    .col-sep {{ display: none; }}
  }}
</style>
</head>
<body>
  <h1>Pedro de Oñate · <em>De contractibus</em></h1>
  <h2>Disputatio LXIII · Sectio I · Pág. {page_num} (columna {col})</h2>

  <div class="bilingual">
    <div><div class="col-head">Transcripción</div></div>
    <div class="col-sep"></div>
    <div><div class="col-head">Traducción</div></div>
  </div>

{rows}

{pending}

  <div class="legend">
    <h3>POS</h3>
    <span style="color:#1a4a8a">VERB/AUX</span>
    <span style="color:#222">NOUN</span>
    <span style="color:#3a6a3a">ADJ</span>
    <span style="color:#7a4a00">ADV</span>
    <span style="color:#666">ADP</span>
    <span style="color:#888">CCONJ/SCONJ/PART</span>
    <span style="color:#7a2a7a">PRON/DET</span>
  </div>
  <div class="stats">{n_done} de {n_total} oraciones traducidas</div>
</body>
</html>
"""

ROW_TEMPLATE = """  <div class="bilingual sentence">
    <div>
      <div class="s-num">§{n}</div>
      <p class="latin">{latin_html}</p>
    </div>
    <div class="col-sep"></div>
    <div>
      <div class="s-num">&nbsp;</div>
      <p class="translation">{es}</p>
    </div>
  </div>"""


def main():
    ap = argparse.ArgumentParser(description="Genera HTML bilingüe (transcripción + traducción) para una columna.")
    ap.add_argument("src_xml", help="TEI anotado por onate_nlp.py (y opcionalmente onate_nlp_corrections.py)")
    ap.add_argument("translations_json", help='{"sentences":[{"n":1,"es":"..."}]}')
    ap.add_argument("--corrections", default=None, help="nlp_corrections/disp63/<stem>.json (opcional, solo para marcar visualmente)")
    ap.add_argument("--out", required=True, help="Ruta del HTML de salida")
    args = ap.parse_args()

    tree = etree.parse(args.src_xml)
    root = tree.getroot()
    sentences = root.findall(".//tei:s", NS)
    page_num = root.get("n", "?")
    col = {"izq": "izquierda", "der": "derecha"}.get(root.get("col"), root.get("col", "?"))

    with open(args.translations_json, encoding="utf-8") as f:
        trans_data = json.load(f)
    translations = {s["n"]: s["es"] for s in trans_data["sentences"]}

    corrections = {}
    if args.corrections:
        with open(args.corrections, encoding="utf-8") as f:
            corrections = json.load(f)

    rows = []
    pending = []
    for idx, s_el in enumerate(sentences, start=1):
        if idx not in translations:
            preview = " ".join("".join(s_el.itertext()).split())[:70]
            pending.append((idx, preview))
            continue
        tokens = tokenize_sentence(s_el, corrections)
        latin_html = render_sentence_html(tokens)
        rows.append(ROW_TEMPLATE.format(n=idx, latin_html=latin_html, es=html.escape(translations[idx])))

    pending_html = ""
    if pending:
        items = "\n".join(f"      <li>§{n}: {html.escape(p)}…</li>" for n, p in pending)
        pending_html = f'  <div class="pending">Oraciones aún sin traducir ({len(pending)} de {len(sentences)}):\n    <ul>\n{items}\n    </ul>\n  </div>'

    out = HTML_TEMPLATE.format(
        page_num=page_num, col=col, rows="\n".join(rows), pending=pending_html,
        n_done=len(rows), n_total=len(sentences),
    )
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(out)
    print(f"OK: {len(rows)} de {len(sentences)} oraciones -> {args.out}")


if __name__ == "__main__":
    main()
