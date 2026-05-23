#!/usr/bin/env python3
"""
generate_facs_xsl.py — Genera xslt/onate_tei2html_facs.xsl a partir del base.

El nuevo XSLT usa <xsl:import> para heredar todos los templates de contenido
del base (tei:w, tei:s, tei:lb, tei:choice, tei:bibl, etc.) y solo sobreescribe
el template raíz, que añade:
  - panel facsímil por columna
  - data-col-id construido como p{@n}_{izq|der} en cada .col
  - botón de toggle [facs]
  - CSS adicional
  - script JS del visor

Uso:
    python3 scripts/generate_facs_xsl.py          # usa rutas por defecto
    python3 scripts/generate_facs_xsl.py xslt/onate_tei2html_bibl.xsl xslt/onate_tei2html_facs.xsl

Si el CSS del base cambia, vuelve a ejecutar el script para resincronizar.

Rutas de runtime esperadas por el HTML generado (relativas al HTML):
    coords/disp63/<col-id>.json
    facsimiles/disp63/<col-id>.png
Ajusta COORDS_BASE, FACS_BASE y FACS_EXT en el bloque JS_CODE si difieren.
"""

import re
import sys
from pathlib import Path

# ── Rutas por defecto ─────────────────────────────────────────────────────────
BASE_XSL = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("xslt/onate_tei2html_bibl.xsl")
OUT_XSL  = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("xslt/onate_tei2html_facs.xsl")

# ── CSS adicional del facsímil ────────────────────────────────────────────────
FACS_CSS = """
          /* Texto: comportamiento base (hover oración y palabra desde CSS base) */

          /* Layout */
          .columns { display: block; }
          .col-wrap {
            display: flex;
            flex-direction: row;
            align-items: flex-start;
            margin-bottom: 2rem;
          }

          /* Panel facsímil */
          .facs-panel {
            display: block;
            width: 400px;
            min-width: 400px;
            border-left: 1px solid #d0c8b8;
            margin-left: 0.75rem;
            background: #f5f0e8;
          }
          .facs-scroll { position: relative; width: 400px; }
          .facs-img   { display: block; width: 100%; }
          .facs-canvas {
            position: absolute;
            top: 0; left: 0;
            width: 100%;
            pointer-events: none;
          }

          /* lb-num de break=no: en DOM pero invisible */
          .lb-num.lb-break { visibility: hidden; }"""

# ── JavaScript del visor ──────────────────────────────────────────────────────
JS_CODE = r"""(function () {
  var COORDS_BASE  = '../../coords/disp63/';
  var FACS_BASE    = '../../facsimiles/disp63/';
  var FACS_EXT     = '.png';
  var EXTRA_OFFSET = 44;
  var cache = {};

  function initAllPanels() {
    alignPanels();
    document.querySelectorAll('.facs-panel[data-col-id]').forEach(function (p) {
      initPanel(p, p.dataset.colId);
    });
    wireColumns();
  }

  function alignPanels() {
    document.querySelectorAll('.col-wrap').forEach(function (wrap) {
      var label = wrap.querySelector('.col-label');
      var panel = wrap.querySelector('.facs-panel');
      if (label && panel)
        panel.style.paddingTop =
          (label.getBoundingClientRect().height + EXTRA_OFFSET) + 'px';
    });
  }

  /* data-lb en words y pc */
  function buildLineMap(col) {
    var lbs = Array.from(col.querySelectorAll('.lb-num'));
    col.querySelectorAll('.tei-w, .tei-pc').forEach(function (el) {
      var n = null;
      for (var i = 0; i < lbs.length; i++)
        if (lbs[i].compareDocumentPosition(el) & 4)
          n = parseInt(lbs[i].textContent.trim(), 10);
      if (n !== null) el.dataset.lb = String(n);
    });
  }

  /* Línea del par en palabras cortadas:
     Caso A: lb-break DENTRO del word (un solo span)
     Caso B: lb-break como hermano del word (dos spans) */
  function getBrokenPartnerLine(wEl) {
    /* Caso A */
    var inner = wEl.querySelector('.lb-break');
    if (inner) return parseInt(inner.textContent.trim(), 10);
    /* Caso B: lb-break como siguiente hermano */
    var el = wEl.nextSibling;
    while (el && (el.nodeType === 3 ||
                  (el.nodeType === 1 && el.tagName === 'BR')))
      el = el.nextSibling;
    if (el && el.nodeType === 1 &&
        el.classList && el.classList.contains('lb-break'))
      return parseInt(el.textContent.trim(), 10);
    /* Caso B inverso: este word es la Parte F */
    el = wEl.previousSibling;
    while (el && (el.nodeType === 3 && el.textContent.trim() === ''))
      el = el.previousSibling;
    if (el && el.nodeType === 1 &&
        el.classList && el.classList.contains('lb-break'))
      return parseInt(wEl.dataset.lb, 10); /* usar su propia línea como "principal" */
    return null;
  }

  function initPanel(panel, colId) {
    if (panel.dataset.ready) return;
    panel.dataset.ready = '1';
    var img = panel.querySelector('.facs-img');
    img.src = FACS_BASE + colId + FACS_EXT;
    img.onload = function () { syncCanvas(panel); };
    if (img.complete && img.naturalWidth) syncCanvas(panel);
    if (cache.hasOwnProperty(colId)) return;
    cache[colId] = null;
    fetch(COORDS_BASE + colId + '.json')
      .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
      .then(function (d) { cache[colId] = d; })
      .catch(function (e) { cache[colId] = false;
                            console.warn('onate-facs:', colId, e.message); });
  }

  function syncCanvas(panel) {
    var img = panel.querySelector('.facs-img');
    var canvas = panel.querySelector('.facs-canvas');
    canvas.width  = img.naturalWidth  || img.offsetWidth;
    canvas.height = img.naturalHeight || img.offsetHeight;
    canvas.style.height = Math.round(
      (img.naturalHeight || img.offsetHeight) *
      (img.offsetWidth / (img.naturalWidth || img.offsetWidth || 1))) + 'px';
  }

  /* Normalizar texto para matching: minúsculas, ſ→s, sin puntuación */
  function norm(t) {
    return (t || '').toLowerCase()
      .replace(/ſ/g, 's')   /* long-s */
      .replace(/[.,;:!?&\-()[\]{}'"]/g, '')
      .trim();
  }

  /* Extraer solo el texto visible de la palabra (sin .tooltip ni .lb-break) */
  function wordText(wEl) {
    if (!wEl) return '';
    var clone = wEl.cloneNode(true);
    var tip = clone.querySelector('.tooltip');
    if (tip) tip.remove();
    clone.querySelectorAll('.lb-num, .lb-break').forEach(function (s) { s.remove(); });
    return clone.textContent.replace(/\s+/g, ' ').trim();
  }

  /* Normalización avanzada: ſ→s, ae/oe, sin puntuación */
  function normAdv(t) {
    return (t || '').toLowerCase()
      .replace(/ſ/g, 's')        /* long-s */
      .replace(/æ/g, 'ae')       /* æ */
      .replace(/œ/g, 'oe')       /* œ */
      .replace(/[.,;:!?&()\[\]{}\-]/g, '')
      .replace(/\s+/g, '')
      .trim();
  }

  /* Score de similitud textual (0 = igual, Infinity = sin relación) */
  function textScore(a, b) {
    if (!a || !b) return Infinity;
    if (a === b) return 0;
    if (a.startsWith(b)) return a.length - b.length;
    if (b.startsWith(a)) return b.length - a.length + 0.5;
    /* Prefijo común largo */
    var common = 0;
    while (common < a.length && common < b.length && a[common] === b[common])
      common++;
    if (common >= Math.min(a.length, b.length) * 0.7)
      return Math.abs(a.length - b.length) + (Math.min(a.length,b.length) - common);
    return Infinity;
  }

  /* Solo saltar la primera palabra cuando la línea empieza con continuación
     de palabra cortada (flag broken_start puesto por onate_coords.py desde ¬).
     Con coords de Transkribus no se necesita heurística. */
  function countLeadingSkip(line) {
    return line.broken_start ? 1 : 0;
  }

  /* Encontrar la mejor palabra de Tesseract para un tei-w */
  function findTessWord(line, wordEl, allToks) {
    if (!line || !line.words || !line.words.length) return null;
    var b = line.bbox;
    var lws = allToks.filter(function (el) {
      return el.classList.contains('tei-w'); });

    /* Saltar continuaciones al inicio de línea */
    var skip  = countLeadingSkip(line);
    var twords = line.words.slice(skip);
    if (!twords.length) return line.words[0];

    /* Intento 1: match por texto normalizado */
    var teiNorm = normAdv(wordEl ? wordText(wordEl) : '');
    if (teiNorm.length > 1) {
      var best = null, bestScore = Infinity;
      twords.forEach(function (tw) {
        var s = textScore(teiNorm, normAdv(tw.text));
        if (s < bestScore) { bestScore = s; best = tw; }
      });
      if (bestScore <= 3) return best;
    }

    /* Intento 2: X proporcional sobre twords (sin continuaciones) */
    var charsBefore = 0;
    if (wordEl && allToks.length) {
      for (var ci = 0; ci < allToks.length; ci++) {
        if (allToks[ci] === wordEl) break;
        charsBefore += allToks[ci].textContent.trim().length + 1;
      }
    }
    var wordChars  = wordEl ? wordText(wordEl).length : 3;
    var totalChars = allToks.reduce(function (s, el) {
      return s + wordText(el).length + 1; }, 0) || 1;
    var propX = b.x + ((charsBefore + wordChars * 0.5) / totalChars) * b.w;
    var nearest = null, nearDist = Infinity;
    twords.forEach(function (tw) {
      var d = Math.abs(tw.bbox.x + tw.bbox.w * 0.5 - propX);
      if (d < nearDist) { nearDist = d; nearest = tw; }
    });
    return nearest || twords[0];
  }

  /* Dibujar rectángulo ámbar de palabra en el canvas */
  function drawWordRect(ctx, data, lineN, wordEl, col, alpha) {
    var line = data.lines[String(lineN)];
    if (!line) return;
    var allToks = col ? Array.from(
      col.querySelectorAll('.tei-w[data-lb="' + lineN + '"],' +
                           '.tei-pc[data-lb="' + lineN + '"]')) : [];
    var best = findTessWord(line, wordEl, allToks);
    if (!best) return;
    var wb = best.bbox;
    ctx.fillStyle   = 'rgba(186,117,23,' + (alpha || 0.38) + ')';
    ctx.fillRect  (wb.x-2, wb.y-2, wb.w+4, wb.h+4);
    ctx.strokeStyle = '#BA7517';
    ctx.lineWidth   = alpha < 0.3 ? 1.5 : 2;
    ctx.strokeRect(wb.x-2, wb.y-2, wb.w+4, wb.h+4);
  }

  function drawOnCanvas(colId, lineN, wordEl, col, partnerLineN) {
    var data = cache[colId];
    if (!data || !data.lines || !lineN) return;
    document.querySelectorAll('.facs-panel[data-col-id="' + colId + '"]')
      .forEach(function (panel) {
        var canvas = panel.querySelector('.facs-canvas');
        var ctx    = canvas.getContext('2d');
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        /* Palabra principal */
        drawWordRect(ctx, data, lineN, wordEl, col, 0.38);
        /* Segunda mitad de palabra cortada: directamente words[0]
           (la continuación es siempre la primera palabra de esa línea;
           no pasar por findTessWord/countLeadingSkip que la saltaría) */
        if (partnerLineN && partnerLineN !== lineN) {
          var pl = data.lines[String(partnerLineN)];
          if (pl && pl.words && pl.words.length) {
            var pw = pl.words[0].bbox;
            ctx.fillStyle   = 'rgba(186,117,23,0.22)';
            ctx.fillRect  (pw.x-2, pw.y-2, pw.w+4, pw.h+4);
            ctx.strokeStyle = '#BA7517';
            ctx.lineWidth   = 1.5;
            ctx.strokeRect(pw.x-2, pw.y-2, pw.w+4, pw.h+4);
          }
        }
      });
  }

  function clearCanvas(colId) {
    document.querySelectorAll(
      '.facs-panel[data-col-id="' + colId + '"] .facs-canvas')
      .forEach(function (c) {
        c.getContext('2d').clearRect(0, 0, c.width, c.height); });
  }

  function wireColumns() {
    document.querySelectorAll('.col[data-col-id]').forEach(function (col) {
      var colId = col.dataset.colId;
      buildLineMap(col);

      col.querySelectorAll('.tei-w').forEach(function (wEl) {
        wEl.addEventListener('mouseenter', function () {
          var lineN       = parseInt(wEl.dataset.lb, 10) || null;
          var partnerLine = getBrokenPartnerLine(wEl);
          drawOnCanvas(colId, lineN, wEl, col, partnerLine);
        });
        wEl.addEventListener('mouseleave', function (e) {
          var to = e.relatedTarget;
          if (to && to.classList && to.classList.contains('tei-w')) return;
          clearCanvas(colId);
        });
      });

      col.addEventListener('mouseleave', function () { clearCanvas(colId); });
    });
  }

  if (document.readyState === 'loading')
    document.addEventListener('DOMContentLoaded', initAllPanels);
  else
    initAllPanels();
})();"""


# ─────────────────────────────────────────────────────────────────────────────
def extract_css(src: str) -> str:
    """Extrae el contenido del bloque <style>…</style> del XSLT base."""
    m = re.search(r"<style>(.*?)</style>", src, re.DOTALL)
    if not m:
        raise ValueError("No se encontró bloque <style> en el XSLT base")
    return m.group(1)


def extract_body_header(src: str) -> str:
    """Extrae el bloque entre <body> y el for-each de páginas (h1, h2, stats)."""
    m = re.search(r"(<body>.*?)(<!-- Una sección)", src, re.DOTALL)
    if not m:
        raise ValueError("No se encontró la cabecera del body en el XSLT base")
    return m.group(1)


def extract_legend(src: str) -> str:
    """Extrae el bloque de la leyenda POS."""
    m = re.search(r"(<!-- Leyenda POS -->.*?</div>)", src, re.DOTALL)
    if not m:
        raise ValueError("No se encontró el bloque de leyenda POS")
    return m.group(1)


def extract_ns_decls(src: str) -> str:
    """Extrae las declaraciones de namespace del elemento xsl:stylesheet."""
    m = re.search(r"(<xsl:stylesheet[^>]+>)", src, re.DOTALL)
    if not m:
        raise ValueError("No se encontró xsl:stylesheet en el base")
    return m.group(1)


def build_facs_xsl(base_src: str, base_path: Path) -> str:
    """Construye el contenido completo del XSLT de facsímil."""

    base_css    = extract_css(base_src)
    body_header = extract_body_header(base_src)
    legend      = extract_legend(base_src)
    ns_decls    = extract_ns_decls(base_src)

    # Ruta relativa desde el nuevo XSLT al base (mismo directorio → solo nombre)
    import_href = base_path.name  # e.g. "onate_tei2html_bibl.xsl"

    # Bloque de columnas modificado (col-wrap + facs-panel)
    columns_block = """\
        <!-- Una sección por página, dos columnas + panel facsímil por sección -->
        <xsl:for-each select="//tei:div[@type='page'][
            not(@n = preceding::tei:div[@type='page']/@n)]">
          <xsl:variable name="page_n" select="@n"/>

          <!-- Cabecera de página -->
          <xsl:apply-templates select="//tei:div[@type='page'][@n=$page_n][1]/tei:fw[@place='top-left']"/>

          <!-- Separador de página -->
          <div class="page-sep">
            <span class="page-sep-label">Página <xsl:value-of select="$page_n"/></span>
          </div>

          <!-- Dos columnas con panel facsímil -->
          <div class="columns">
            <xsl:for-each select="//tei:div[@type='page'][@n=$page_n]">
              <!-- col-id = nombre del fichero fuente sin extensión:
                   pg_63_39_izq, pg_63_39_der, pg_63_40_izq …
                   Coincide directamente con PAGE XML, coords JSON e imagen. -->
              <xsl:variable name="col_side">
                <xsl:choose>
                  <xsl:when test="position()=1">izq</xsl:when>
                  <xsl:otherwise>der</xsl:otherwise>
                </xsl:choose>
              </xsl:variable>
              <xsl:variable name="col_id">
                <xsl:value-of select="concat('pg_63_', $page_n, '_', $col_side)"/>
              </xsl:variable>
              <div class="col-wrap">
                <div class="col" data-col-id="{$col_id}">
                  <div class="col-label">
                    <xsl:choose>
                      <xsl:when test="position()=1">Col. izq.</xsl:when>
                      <xsl:otherwise>Col. der.</xsl:otherwise>
                    </xsl:choose>
                  </div>
                  <xsl:apply-templates select="tei:p | tei:note | tei:head | tei:div[@type='summarium']"/>
                </div>
                <div class="facs-panel" data-col-id="{$col_id}">
                  <div class="facs-scroll">
                    <img class="facs-img" alt="facsímil"/>
                    <canvas class="facs-canvas"></canvas>
                  </div>
                </div>
              </div>
            </xsl:for-each>
          </div>
        </xsl:for-each>"""

    # Construir el XSLT completo
    xsl = f"""\
<?xml version="1.0" encoding="UTF-8"?>
<!--
  onate_tei2html_facs.xsl — Visor de facsímil por columna.

  GENERADO AUTOMÁTICAMENTE por scripts/generate_facs_xsl.py.
  No editar a mano: regenerar si cambia el XSLT base.

  Hereda mediante <xsl:import> todos los templates de contenido del base
  (tei:w, tei:s, tei:lb, tei:choice, tei:bibl, tei:cit, etc.).
  Solo sobreescribe el template raíz para añadir:
    · data-col-id="p{{N}}_{{izq|der}}" en cada columna (ej: p35_izq, p35_der)
    · .col-wrap + .facs-panel por columna
    · botón [facs] de toggle
    · CSS del visor facsímil
    · script JS (lazy load de coords + canvas highlight)

  Vínculo texto ↔ imagen:
    data-col-id → coords/disp63/p<N>_<lado>.json → lines["N"].bbox
    lb n="N"    → .lb-num hover                → canvas highlight
-->
{ns_decls}

  <!-- Importar base: hereda TODOS los templates de contenido -->
  <xsl:import href="{import_href}"/>

  <xsl:output method="html" encoding="UTF-8" indent="yes"/>
  <xsl:param name="show-tooltips" select="true()"/>

  <!-- ================================================================== -->
  <!-- TEMPLATE RAÍZ — sobreescribe el del base                           -->
  <!-- Hereda automáticamente: tei:w, tei:s, tei:lb, tei:choice,         -->
  <!--   tei:bibl, tei:cit, tei:pc, tei:head, tei:hi, tei:note, etc.    -->
  <!-- ================================================================== -->
  <xsl:template match="/">
    <html lang="la">
      <head>
        <meta charset="UTF-8"/>
        <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
        <title>Oñate · De contractibus · Disp. 63 · Facsímil</title>
        <style>{base_css}{FACS_CSS}
        </style>
      </head>
      {body_header}
        <div class="stats">
          Palabras: <xsl:value-of select="count(//tei:w)"/> &#183;
          Oraciones: <xsl:value-of select="count(//tei:s)"/> &#183;
          Párrafos: <xsl:value-of select="count(//tei:p)"/>
        </div>

{columns_block}

        <!-- Leyenda POS -->
        {legend}

        <!-- Visor facsímil: script -->
        <script>
//<![CDATA[
{JS_CODE}
//]]>
        </script>
      </body>
    </html>
  </xsl:template>

  <!-- ================================================================== -->
  <!-- OVERRIDE tei:lb[@break='no']                                       -->
  <!-- El base solo genera guión + <br/> sin lb-num. Aquí añadimos un    -->
  <!-- lb-num invisible para que buildLineMap detecte el cambio de línea. -->
  <!-- ================================================================== -->
  <xsl:template match="tei:lb[@break='no']">
    <xsl:text>-</xsl:text><br/>
    <xsl:if test="@n">
      <xsl:variable name="n"    select="@n"/>
      <xsl:variable name="mod5" select="$n mod 5"/>
      <xsl:choose>
        <xsl:when test="$mod5 = 0">
          <span class="lb-num lb-5 lb-break"><xsl:value-of select="$n"/></span>
        </xsl:when>
        <xsl:otherwise>
          <span class="lb-num lb-break"><xsl:value-of select="$n"/></span>
        </xsl:otherwise>
      </xsl:choose>
    </xsl:if>
  </xsl:template>

</xsl:stylesheet>"""

    return xsl


# ─────────────────────────────────────────────────────────────────────────────
def main():
    if not BASE_XSL.exists():
        sys.exit(f"ERROR: no se encuentra {BASE_XSL}")

    print(f"Leyendo base: {BASE_XSL}")
    base_src = BASE_XSL.read_text(encoding="utf-8")

    facs_xsl = build_facs_xsl(base_src, BASE_XSL)

    OUT_XSL.parent.mkdir(parents=True, exist_ok=True)
    OUT_XSL.write_text(facs_xsl, encoding="utf-8")

    # Verificar que es XML válido
    try:
        from lxml import etree
        etree.fromstring(facs_xsl.encode())
        valid = "✓ XML válido"
    except Exception as e:
        valid = f"⚠ XML inválido: {e}"

    print(f"  → {OUT_XSL}")
    print(f"  {valid}")
    print()
    print("Añadir a procesar_pagina.sh:")
    print("  run_html_facs() {")
    print("    xsltproc xslt/onate_tei2html_facs.xsl output/disp63_bibl_completo.xml \\")
    print("             > html/disp63/disp63_facs.html")
    print("    echo '✓ HTML facsímil → html/disp63/disp63_facs.html'")
    print("  }")


if __name__ == "__main__":
    main()
