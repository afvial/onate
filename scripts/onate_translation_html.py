#!/usr/bin/env python3
"""
onate_translation_html.py — Genera html/disp63/disp63_trad.html: recorre
todas las columnas de src/disp63/ que ya tengan traducción guardada en
translations/disp63/ y arma un único documento "libro" con el mismo
lenguaje visual que disp63_facs.html / disp63_bibl.html:
  - page-sep con el número de página
  - columns > col-wrap > col (izquierda = Transcripción, derecha = Traducción)
  - span.tei-w con tooltip en <table> (lemma/pos/msd)
  - span.tei-choice-abbr / tei-choice-orig
  - span.tei-s por oración (resalta al pasar el cursor, igual que en el facsímil)

No requiere argumentos: infiere page/col de los nombres de archivo
pg_63_<page>_<col>.xml en src/disp63/.

Uso:
    python3 onate_translation_html.py [--src-dir src/disp63]
                                       [--trans-dir translations/disp63]
                                       [--corr-dir nlp_corrections/disp63]
                                       [--out html/disp63/disp63_trad.html]
"""
import argparse
import glob
import html
import json
import os
import re
from lxml import etree

NS = {"tei": "http://www.tei-c.org/ns/1.0"}
COL_ORDER = {"unica": 0, "izq": 1, "der": 2}
COL_LABEL = {"unica": "única", "izq": "izquierda", "der": "derecha"}


def local(tag):
    return tag.split("}")[-1] if "}" in tag else tag


def diplomatic_text(el):
    """Texto simple, reconstruyendo palabras partidas entre líneas (sin
    guion ni salto): prefiere <orig> sobre <reg> y <abbr> sobre <expan>."""
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
            tokens.append({"kind": "punct", "text": child.text or ""})
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
            tokens.append({"kind": "word", "text": text, "meta": meta, "choice_kind": kind})
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
                rows.append(f'<tr><td class="tip-key">{html.escape(k)}</td><td class="tip-val">{html.escape(v)}</td></tr>')
    if meta.get("_corrected"):
        rows.append(f'<tr><td class="tip-key">corregido</td><td class="tip-expan">{html.escape(meta.get("_spec",""))}</td></tr>')
    return "<table>" + "".join(rows) + "</table>"


def render_sentence_html(tokens):
    pieces = []
    for i, tok in enumerate(tokens):
        if tok["kind"] == "punct":
            pieces.append(html.escape(tok["text"]))
            continue
        text = html.escape(tok["text"])
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
        prefix = "" if i == 0 else " "
        pieces.append(f'{prefix}<span {span_attrs}>{tooltip}{text}</span>')
    return "".join(pieces)


CSS = """
  body { font-family: "Palatino Linotype", Palatino, "Book Antiqua", Georgia, serif;
         font-size: 0.93rem; line-height: 1.7; letter-spacing: 0.01em;
         max-width: 1100px; margin: 2rem auto; padding: 0 1.5rem;
         color: #222; background: #fafaf7; }
  h1 { font-size: 1.4rem; text-align: center; margin-bottom: 0.2rem; }
  h2 { font-size: 1.05rem; text-align: center; color: #555; font-weight: normal; margin-top: 0; }
  .stats { text-align: center; font-size: 0.8rem; color: #777; margin: 0.3rem 0; }

  .page-sep { border-top: 1px solid #aaa; border-bottom: 1px solid #aaa;
              padding: 0.2rem 0; margin: 2rem 0 1rem 0; text-align: center; }
  .page-sep-label { font-size: 0.82rem; color: #555; letter-spacing: 0.04em; }

  .columns { display: flex; flex-direction: row; gap: 2.5rem; margin-top: 0.5rem;
             align-items: start; }
  .col-wrap { display: contents; }
  .col { flex: 1 1 0; min-width: 0; }
  .col:first-child { border-right: 1px solid #d0c8b8; padding-right: 1.8rem; }
  .col-label { font-size: 0.72rem; color: #aaa; text-align: center;
               margin-bottom: 0.8rem; letter-spacing: 0.05em; text-transform: uppercase; }

  .tei-p { display: block; margin: 0 0 0.9rem 0; text-indent: 1.2em; line-height: 1.9; }
  .tei-p-first { text-indent: 0; }
  p.translation { margin: 0 0 0.9rem 0; line-height: 1.9; }

  .tei-s { display: inline; }
  .tei-s.s-hover-active { background-color: #e8f0fb; border-radius: 2px; }

  span.tei-w { display: inline; cursor: default; border-bottom: 1px dotted transparent;
               transition: border-color 0.15s; position: relative; }
  span.tei-w:hover { background-color: #fdeee0; border-radius: 2px; border-bottom: 1px dotted #7a9abf; }
  span.tei-w[data-pos="VERB"]  { color: #1a4a8a; }
  span.tei-w[data-pos="AUX"]   { color: #1a4a8a; }
  span.tei-w[data-pos="NOUN"]  { color: #222; }
  span.tei-w[data-pos="ADJ"]   { color: #3a6a3a; }
  span.tei-w[data-pos="ADV"]   { color: #7a4a00; }
  span.tei-w[data-pos="ADP"]   { color: #666; }
  span.tei-w[data-pos="CCONJ"] { color: #888; }
  span.tei-w[data-pos="SCONJ"] { color: #888; }
  span.tei-w[data-pos="PRON"]  { color: #7a2a7a; }
  span.tei-w[data-pos="DET"]   { color: #7a2a7a; }
  span.tei-w[data-pos="X"]     { color: #aaa; }

  span.tei-choice-abbr { border-bottom: 1px dotted #8a6a2a; }
  span.tei-choice-orig { border-bottom: 1px dotted #999; }
  span.tei-corrected   { border-bottom: 1px dashed #b5432f; }
  span.tei-pc { margin-left: 0; }

  .tooltip { display: none; position: absolute; bottom: 2.2em; left: 0;
             background: #2a2a2a; color: #fff; font-size: 0.68rem; font-family: monospace;
             padding: 0.3em 0.6em; border-radius: 4px; white-space: nowrap;
             width: max-content; z-index: 10; pointer-events: none;
             box-shadow: 0 2px 6px rgba(0,0,0,0.4); }
  span.tei-w:hover .tooltip { display: block; }
  .tooltip table { border-collapse: collapse; line-height: 1.6; font-size: 0.65rem; }
  .tooltip td { padding: 0 0.4em 0 0; vertical-align: top; }
  .tooltip .tip-key   { color: #888; }
  .tooltip .tip-lemma { color: #7ec8e3; font-weight: bold; }
  .tooltip .tip-pos   { color: #f0c060; }
  .tooltip .tip-val   { color: #aaddaa; }
  .tip-expan { color: #f0a060; }


  .pending-note { font-size: 0.78rem; color: #999; font-style: italic; margin-top: 0.6rem; }
"""

HTML_TEMPLATE = """<html lang="es">
<head>
<meta charset="UTF-8">
<title>Oñate · De contractibus · Disp. 63 · Traducción</title>
<style>{css}</style>
</head>
<body>
<h1>Pedro de Oñate · <em>De contractibus</em></h1>
<h2>Disputatio LXIII · Sectio I · Traducción</h2>
<div class="stats">{n_cols} columna(s) · {n_sent_done} de {n_sent_total} oraciones traducidas</div>
{body}
<script>
document.addEventListener('DOMContentLoaded', function () {{
  document.querySelectorAll('.tei-s[data-sid]').forEach(function (el) {{
    el.addEventListener('mouseenter', function () {{
      var sid = el.getAttribute('data-sid');
      document.querySelectorAll('.tei-s[data-sid="' + sid + '"]').forEach(function (m) {{
        m.classList.add('s-hover-active');
      }});
    }});
    el.addEventListener('mouseleave', function () {{
      var sid = el.getAttribute('data-sid');
      document.querySelectorAll('.tei-s[data-sid="' + sid + '"]').forEach(function (m) {{
        m.classList.remove('s-hover-active');
      }});
    }});
  }});
}});
</script>
</body>
</html>
"""

PAGE_BLOCK = """<div class="page-sep"><span class="page-sep-label">Página {page} (col. {col_label})</span></div>
<div class="columns"><div class="col-wrap">
<div class="col">
<div class="col-label">Transcripción</div>
{latin_body}
</div>
<div class="col">
<div class="col-label">Traducción</div>
{trans_body}
</div>
</div></div>"""


def parse_stem(path):
    m = re.match(r"pg_63_(\d+)_(\w+)\.xml$", os.path.basename(path))
    if not m:
        return None
    return int(m.group(1)), m.group(2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src-dir", default="src/disp63")
    ap.add_argument("--trans-dir", default="translations/disp63")
    ap.add_argument("--corr-dir", default="nlp_corrections/disp63")
    ap.add_argument("--out", default="html/disp63/disp63_trad.html")
    args = ap.parse_args()

    candidates = []
    for xml_path in glob.glob(os.path.join(args.src_dir, "pg_63_*.xml")):
        parsed = parse_stem(xml_path)
        if not parsed:
            continue
        page, col = parsed
        stem = f"pg_63_{page}_{col}"
        trans_path = os.path.join(args.trans_dir, f"{stem}.json")
        if not os.path.exists(trans_path):
            continue
        candidates.append((page, COL_ORDER.get(col, 9), col, xml_path, trans_path, stem))
    candidates.sort()

    blocks = []
    n_sent_done = 0
    n_sent_total = 0

    for page, _, col, xml_path, trans_path, stem in candidates:
        tree = etree.parse(xml_path)
        root = tree.getroot()
        sentences = root.findall(".//tei:s", NS)

        with open(trans_path, encoding="utf-8") as f:
            translations = {s["n"]: s["es"] for s in json.load(f)["sentences"]}

        corr_path = os.path.join(args.corr_dir, f"{stem}.json")
        corrections = {}
        if os.path.exists(corr_path):
            with open(corr_path, encoding="utf-8") as f:
                corrections = json.load(f)

        n_sent_total += len(sentences)

        # Agrupar oraciones por su <p> padre: sin salto de línea entre
        # oraciones de un mismo párrafo, solo entre párrafos distintos.
        paragraphs = []  # lista de (p_element, [s_elements])
        for s_el in sentences:
            p_el = s_el.getparent()
            if paragraphs and paragraphs[-1][0] is p_el:
                paragraphs[-1][1].append(s_el)
            else:
                paragraphs.append((p_el, [s_el]))

        latin_paras, trans_paras = [], []
        n_pending = 0
        global_idx = 0
        for para_i, (p_el, s_list) in enumerate(paragraphs):
            latin_run, trans_run = [], []
            for s_el in s_list:
                global_idx += 1
                if global_idx not in translations:
                    n_pending += 1
                    continue
                sid = f"{stem}-{global_idx}"
                tokens = tokenize_sentence(s_el, corrections)
                latin_run.append(f'<span class="tei-s" data-sid="{sid}">' + render_sentence_html(tokens) + "</span>")
                trans_run.append(f'<span class="tei-s" data-sid="{sid}">' + html.escape(translations[global_idx]) + "</span>")
            if not latin_run:
                continue
            p_class = "tei-p tei-p-first" if para_i == 0 else "tei-p"
            latin_paras.append(f'<span class="{p_class}">' + " ".join(latin_run) + "</span>")
            trans_paras.append('<p class="translation">' + " ".join(trans_run) + "</p>")

        latin_body = "".join(latin_paras)
        trans_body = "\n".join(trans_paras)
        n_sent_done += (len(sentences) - n_pending)
        if n_pending:
            trans_body += f'\n<p class="pending-note">({n_pending} oración(es) de esta columna aún sin traducir)</p>'

        blocks.append(PAGE_BLOCK.format(
            page=page, col_label=COL_LABEL.get(col, col),
            latin_body=latin_body, trans_body=trans_body,
        ))

    out_html = HTML_TEMPLATE.format(
        css=CSS, n_cols=len(candidates),
        n_sent_done=n_sent_done, n_sent_total=n_sent_total,
        body="\n".join(blocks) if blocks else "<p style='text-align:center;color:#999'>Aún no hay traducciones guardadas.</p>",
    )

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(out_html)
    print(f"OK: {len(candidates)} columna(s), {n_sent_done}/{n_sent_total} oraciones -> {args.out}")


if __name__ == "__main__":
    main()
