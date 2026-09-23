#!/usr/bin/env python3
"""
onate_inject_translation.py — Extrae la transcripción YA renderizada por
el pipeline XSLT (disp63_facs.html o disp63_bibl.html) y la combina con
la traducción guardada en translations/disp63/, generando disp63_trad.html.

A diferencia de onate_translation_html.py, este script NO reimplementa el
renderizado del latín desde el TEI: reutiliza tal cual el HTML que ya
produjo tu XSLT (tipografía, sic/corr, abreviaturas, numeración de línea,
todo), y solo le añade al lado una columna de traducción, más el
resaltado cruzado oración-por-oración y palabra-por-palabra.

Uso:
    python3 onate_inject_translation.py <html_fuente> \
        [--trans-dir translations/disp63] [--senses-dir senses/disp63] \
        [--out html/disp63/disp63_trad.html]
"""
import argparse
import glob
import html
import json
import os
import copy
import re
from collections import defaultdict
from lxml import html as lh, etree

COL_ORDER = {"unica": 0, "izq": 1, "der": 2}
COL_LABEL = {"unica": "única", "izq": "izquierda", "der": "derecha"}


def strip_line_breaks(tei_s):
    """Quita los <br> y <span class="lb-num..."> del original diplomático,
    reuniendo las palabras partidas a mitad de línea (quitando el guion
    tipográfico que quedaría suelto en medio de la palabra)."""
    # 1) antes de tocar nada: quitar el guion que antecede a cada <br>
    for br in tei_s.iter("br"):
        prev = br.getprevious()
        parent = br.getparent()
        if prev is not None:
            if prev.tail and prev.tail.rstrip().endswith("-"):
                prev.tail = re.sub(r"-\s*$", "", prev.tail)
            elif prev.tail is None or not prev.tail.endswith(" "):
                prev.tail = (prev.tail or "") + " "
        elif parent.text and parent.text.rstrip().endswith("-"):
            parent.text = re.sub(r"-\s*$", "", parent.text)
        elif parent.text is None or not parent.text.endswith(" "):
            parent.text = (parent.text or "") + " "

    # 2) quitar los <span class="lb-num..."> conservando su tail (el resto
    # de la palabra que sigue al número de línea)
    for lbnum in tei_s.xpath('.//span[contains(concat(" ", @class, " "), " lb-num ")]'):
        parent = lbnum.getparent()
        prev = lbnum.getprevious()
        tail = lbnum.tail or ""
        if prev is not None:
            prev.tail = (prev.tail or "") + tail
        else:
            parent.text = (parent.text or "") + tail
        parent.remove(lbnum)

    # 3) quitar los <br> en sí (lxml funde su tail con el texto circundante)
    etree.strip_tags(tei_s, "br")
    return tei_s


def get_tei_w_text(tei_w):
    """Texto visible completo de un span.tei-w ya renderizado, incluyendo
    palabras partidas a mitad de línea (con <br> y <span class="lb-num">
    intercalados dentro del mismo span): reconstruye la palabra completa,
    quitando el guion tipográfico que antecede al <br>."""
    tooltip = tei_w.find('span[@class="tooltip"]')
    parts = []
    if tooltip is not None:
        if tooltip.tail:
            parts.append(tooltip.tail)
    elif tei_w.text:
        parts.append(tei_w.text)
    for child in tei_w:
        if child is tooltip:
            continue
        if child.tag == "br" and parts and parts[-1].endswith("-"):
            parts[-1] = parts[-1][:-1]
        if child.tail:
            parts.append(child.tail)
    return "".join(parts).strip()


def render_sense_tooltip(entry):
    rows = []
    if entry.get("lemma"):
        rows.append(f'<tr><td class="tip-key">latin</td><td class="tip-lemma">{html.escape(entry["lemma"])}</td></tr>')
    if entry.get("gloss_en"):
        rows.append(f'<tr><td class="tip-key">gloss</td><td class="tip-pos">{html.escape(entry["gloss_en"])}</td></tr>')
    if entry.get("lila_def"):
        rows.append(f'<tr><td class="tip-key">def</td><td class="tip-val">{html.escape(entry["lila_def"])}</td></tr>')
    if entry.get("lila_uri"):
        m = re.search(r"(\d{8}-[a-z])$", entry["lila_uri"])
        if m:
            rows.append(f'<tr><td class="tip-key">synset</td><td class="tip-feat">{html.escape(m.group(1))}</td></tr>')
        rows.append(f'<tr><td class="tip-key">lila</td><td class="tip-val"><a href="{html.escape(entry["lila_uri"])}" target="_blank" rel="noopener">↗ lila-erc.eu</a></td></tr>')
    else:
        rows.append('<tr><td class="tip-key">lila</td><td class="tip-val" style="color:#888">(lila_uri pendiente)</td></tr>')
    return '<span class="tooltip"><table>' + "".join(rows) + "</table></span>"


def render_translation_html(text, sense_entries):
    if not sense_entries:
        return html.escape(text)
    spans = []
    for entry in sense_entries:
        needle = entry.get("match_text") or entry.get("gloss_en")
        if not needle:
            continue
        occ = entry.get("match_occurrence", 1)
        matches = list(re.finditer(r"\b" + re.escape(needle) + r"\b", text, re.IGNORECASE))
        if len(matches) >= occ:
            m = matches[occ - 1]
            spans.append((m.start(), m.end(), entry))
    spans.sort()
    pieces, cursor = [], 0
    for start, end, entry in spans:
        if start < cursor:
            continue
        pieces.append(html.escape(text[cursor:start]))
        word = html.escape(text[start:end])
        pieces.append(f'<span class="sense-w" data-sense="{html.escape(entry["_link_id"])}">{render_sense_tooltip(entry)}{word}</span>')
        cursor = end
    pieces.append(html.escape(text[cursor:]))
    return "".join(pieces)


def extract_transcription_col(root, stem):
    """Devuelve el div.col (transcripción real) para este stem, ignorando
    el div.facs-panel que comparte el mismo data-col-id."""
    for c in root.xpath(f'//div[@data-col-id="{stem}"]'):
        classes = (c.get("class") or "").split()
        if "col" in classes and "facs-panel" not in classes:
            return c
    return None


def find_paragraph_ancestor(tei_s):
    node = tei_s.getparent()
    while node is not None:
        if "tei-p" in (node.get("class") or "").split():
            return node
        node = node.getparent()
    return None


EXTRA_CSS = """
  body { max-width: 76rem; margin: 2rem auto; padding: 0 1.5rem; }
  h1 { font-size: 1.3rem; text-align: center; margin-bottom: 0.1rem; }
  h2 { font-size: 1rem; text-align: center; color: #555; font-weight: normal; margin-top: 0; }
  .stats { text-align: center; font-size: 0.8rem; color: #777; margin: 0.3rem 0 1rem; }

  /* al quitar los <br> diplomáticos, la transcripción también necesita
     envolver como texto normal (heredaba nowrap, pensado para esos <br>) */
  /* .columns venía con width: fit-content (se ajusta al contenido), lo
     que impedía que flex-grow repartiera el espacio de forma pareja entre
     las dos columnas — le damos un ancho explícito */
  .columns { width: 100%; max-width: 60rem; margin-left: auto; margin-right: auto; }

  /* gap:0 para que la simetría alrededor de la línea divisoria la controlen
     solo los padding-right/padding-left de cada columna, no el flex gap */
  .columns { gap: 0; }

  .col:first-child {
    width: 50%; flex: 0 0 50%; box-sizing: border-box;
    white-space: normal;
    padding-left: 1.5rem; padding-right: 1.5rem;
  }
  .lb-num { display: none; }

  /* la col de traducción no hereda el ancho fijo/nowrap de la diplomática */
  .col.col-translation {
    width: 50%; flex: 0 0 50%; box-sizing: border-box;
    white-space: normal; padding-left: 1.5rem; padding-right: 0;
    border-right: none;
    word-break: normal; overflow-wrap: normal; hyphens: none;
  }
  p.translation { line-height: var(--lh); }
  p.translation { margin: 0 0 0.9rem 0; }
  .pending-note { font-size: 0.78rem; color: #999; font-style: italic; margin: 0 0 0.9rem 0; }

  .tei-s.s-hover-active { background-color: #e8f0fb; border-radius: 2px; }
  [data-sense].w-hover-active { background-color: #ffe9a8; border-radius: 2px; }

  span.sense-w { position: relative; cursor: default; color: #1a6e63;
                 border-bottom: 1px dotted #1a6e63; }
  span.sense-w:hover { background-color: #e6f5f2; border-radius: 2px; }
  span.sense-w .tooltip { display: none; position: absolute; bottom: 1.7em; left: 0;
                           background: #2a2a2a; color: #fff; font-size: 0.68rem;
                           font-family: "SF Mono", Menlo, Consolas, monospace;
                           padding: 0.3em 0.6em; border-radius: 4px;
                           white-space: normal; max-width: 22em; z-index: 10;
                           pointer-events: auto; box-shadow: 0 2px 6px rgba(0,0,0,0.4); }
  span.sense-w .tooltip.tip-open { display: block; }
  span.sense-w .tooltip table { border-collapse: collapse; line-height: 1.6; font-size: 0.65rem; }
  span.sense-w .tooltip td { padding: 0 0.4em 0.15em 0; vertical-align: top; }
  span.sense-w .tooltip a { color: #7ec8e3; text-decoration: underline; word-break: break-all; }
  span.sense-w .tooltip a:hover { color: #a9dcf0; }
"""

HTML_TEMPLATE = """<html lang="es">
<head>
<meta charset="UTF-8">
<title>Oñate · De contractibus · Disp. 63 · Traducción</title>
<style>{src_css}{extra_css}</style>
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
      document.querySelectorAll('.tei-s[data-sid="' + sid + '"]').forEach(function (m) {{ m.classList.add('s-hover-active'); }});
    }});
    el.addEventListener('mouseleave', function () {{
      var sid = el.getAttribute('data-sid');
      document.querySelectorAll('.tei-s[data-sid="' + sid + '"]').forEach(function (m) {{ m.classList.remove('s-hover-active'); }});
    }});
  }});
  document.querySelectorAll('[data-sense]').forEach(function (el) {{
    el.addEventListener('mouseenter', function () {{
      var sid = el.getAttribute('data-sense');
      document.querySelectorAll('[data-sense="' + sid + '"]').forEach(function (m) {{ m.classList.add('w-hover-active'); }});
    }});
    el.addEventListener('mouseleave', function () {{
      var sid = el.getAttribute('data-sense');
      document.querySelectorAll('[data-sense="' + sid + '"]').forEach(function (m) {{ m.classList.remove('w-hover-active'); }});
    }});
  }});
  document.querySelectorAll('span.sense-w').forEach(function (word) {{
    var tooltip = word.querySelector('.tooltip');
    if (!tooltip) return;
    var hideTimer = null;
    function show() {{ clearTimeout(hideTimer); tooltip.classList.add('tip-open'); }}
    function hideDelayed() {{ hideTimer = setTimeout(function () {{ tooltip.classList.remove('tip-open'); }}, 250); }}
    word.addEventListener('mouseenter', show);
    word.addEventListener('mouseleave', hideDelayed);
    tooltip.addEventListener('mouseenter', show);
    tooltip.addEventListener('mouseleave', hideDelayed);
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
<div class="col col-translation">
<div class="col-label">Traducción</div>
{trans_body}
</div>
</div></div>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source_html", help="disp63_facs.html o disp63_bibl.html ya generado por el XSLT")
    ap.add_argument("--trans-dir", default="translations/disp63")
    ap.add_argument("--senses-dir", default="senses/disp63")
    ap.add_argument("--out", default="html/disp63/disp63_trad.html")
    args = ap.parse_args()

    tree = lh.parse(args.source_html)
    root = tree.getroot()
    src_css = root.xpath("//style")[0].text or ""

    candidates = []
    for trans_path in sorted(glob.glob(os.path.join(args.trans_dir, "pg_63_*.json"))):
        stem = os.path.splitext(os.path.basename(trans_path))[0]
        m = re.match(r"pg_63_(\d+)_(\w+)$", stem)
        if not m:
            continue
        page, col = int(m.group(1)), m.group(2)
        candidates.append((page, COL_ORDER.get(col, 9), col, stem, trans_path))
    candidates.sort()

    blocks = []
    n_sent_done = n_sent_total = 0

    for page, _, col, stem, trans_path in candidates:
        with open(trans_path, encoding="utf-8") as f:
            translations = {s["n"]: s["es"] for s in json.load(f)["sentences"]}

        senses_path = os.path.join(args.senses_dir, f"{stem}.json")
        senses_by_sentence = defaultdict(list)
        if os.path.exists(senses_path):
            with open(senses_path, encoding="utf-8") as f:
                for i, entry in enumerate(json.load(f).get("senses", [])):
                    entry["_link_id"] = f"{stem}-sense-{i}"
                    senses_by_sentence[entry["sentence"]].append(entry)

        transcr_col = extract_transcription_col(root, stem)
        if transcr_col is None:
            print(f"  (no encontré la columna {stem} en {args.source_html}, se omite)")
            continue
        sentences = transcr_col.xpath('.//span[contains(concat(" ", @class, " "), " tei-s ")]')
        n_sent_total += len(sentences)

        groups = []
        for idx, tei_s in enumerate(sentences, start=1):
            p_anc = find_paragraph_ancestor(tei_s)
            if groups and groups[-1][0] is p_anc:
                groups[-1][1].append((idx, tei_s))
            else:
                groups.append([p_anc, [(idx, tei_s)]])

        latin_paras, trans_paras = [], []
        n_pending = 0
        for p_anc, items in groups:
            latin_run, trans_run = [], []
            for idx, tei_s in items:
                if idx not in translations:
                    n_pending += 1
                    continue
                sid = f"{stem}-{idx}"
                tei_s_copy = copy.deepcopy(tei_s)
                tei_s_copy.set("data-sid", sid)

                sense_entries = senses_by_sentence.get(idx, [])
                sense_by_occ = {(e["text"], e.get("occurrence", 1)): e for e in sense_entries}
                occ_counts = defaultdict(int)
                for tei_w in tei_s_copy.xpath('.//span[contains(concat(" ", @class, " "), " tei-w ")]'):
                    text = get_tei_w_text(tei_w)
                    occ_counts[text] += 1
                    entry = sense_by_occ.get((text, occ_counts[text]))
                    if entry:
                        tei_w.set("data-sense", entry["_link_id"])

                strip_line_breaks(tei_s_copy)

                latin_run.append(etree.tostring(tei_s_copy, encoding="unicode", method="html"))
                trans_run.append(
                    f'<span class="tei-s" data-sid="{sid}">'
                    + render_translation_html(translations[idx], sense_entries)
                    + "</span>"
                )
            if not latin_run:
                continue
            latin_paras.append("".join(latin_run))
            trans_paras.append('<p class="translation">' + " ".join(trans_run) + "</p>")

        n_sent_done += (len(sentences) - n_pending)
        latin_body = "".join(latin_paras)
        trans_body = "\n".join(trans_paras)
        if n_pending:
            trans_body += f'\n<p class="pending-note">({n_pending} oración(es) de esta columna aún sin traducir)</p>'

        blocks.append(PAGE_BLOCK.format(page=page, col_label=COL_LABEL.get(col, col),
                                         latin_body=latin_body, trans_body=trans_body))

    out_html = HTML_TEMPLATE.format(
        src_css=src_css, extra_css=EXTRA_CSS,
        n_cols=len(candidates), n_sent_done=n_sent_done, n_sent_total=n_sent_total,
        body="\n".join(blocks) if blocks else "<p style='text-align:center;color:#999'>Aún no hay traducciones guardadas.</p>",
    )

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(out_html)
    print(f"OK: {len(candidates)} columna(s), {n_sent_done}/{n_sent_total} oraciones -> {args.out}")


if __name__ == "__main__":
    main()
