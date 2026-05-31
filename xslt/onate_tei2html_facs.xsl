<?xml version="1.0" encoding="UTF-8"?>
<!--
  onate_tei2html_facs.xsl — Visor de facsímil por columna.

  GENERADO AUTOMÁTICAMENTE por scripts/generate_facs_xsl.py.
  No editar a mano: regenerar si cambia el XSLT base.

  Hereda mediante <xsl:import> todos los templates de contenido del base
  (tei:w, tei:s, tei:lb, tei:choice, tei:bibl, tei:cit, etc.).
  Solo sobreescribe el template raíz para añadir:
    · data-col-id="p{N}_{izq|der}" en cada columna (ej: p35_izq, p35_der)
    · .col-wrap + .facs-panel por columna
    · botón [facs] de toggle
    · CSS del visor facsímil
    · script JS (lazy load de coords + canvas highlight)

  Vínculo texto ↔ imagen:
    data-col-id → coords/disp63/p<N>_<lado>.json → lines["N"].bbox
    lb n="N"    → .lb-num hover                → canvas highlight
-->
<xsl:stylesheet version="1.0"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:tei="http://www.tei-c.org/ns/1.0"
  exclude-result-prefixes="tei">

  <!-- Importar base: hereda TODOS los templates de contenido -->
  <xsl:import href="onate_tei2html_bibl.xsl"/>

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
        <style>
          body {
            font-family: "Palatino Linotype", Palatino, "Book Antiqua", Georgia, serif;
            font-size: 0.93rem;
            line-height: var(--lh);
            letter-spacing: 0.01em;
            max-width: 1100px;
            margin: 2rem auto;
            padding: 0 1.5rem;
            color: #222;
            background: #fafaf7;
          }
          h1 { font-size: 1.4rem; text-align: center; margin-bottom: 0.2rem; }
          h2 { font-size: 1.05rem; text-align: center; color: #555;
               font-weight: normal; margin-top: 0; }

          .page-header {
            display: flex;
            justify-content: space-between;
            border-top: 1px solid #aaa;
            border-bottom: 1px solid #aaa;
            padding: 0.2rem 0;
            margin: 1.5rem 0 1rem 0;
            font-size: 0.82rem;
            color: #555;
            
          }

          /* Cuadrícula de líneas — igual que el original impreso */
          :root { --lh: 1.55rem; }   /* altura de línea base */

          body {
            font-size: 0.93rem;
            line-height: var(--lh);
            font-family: "Palatino Linotype", Palatino, "Book Antiqua", Georgia, serif;
            letter-spacing: 0.01em;
          }

          /* Layout dos columnas — ancho fijo, centrado en la ventana */
          .columns {
            display: flex;
            flex-direction: row;
            gap: 2.5rem;
            margin-top: 0.5rem;
            align-items: start;
            width: fit-content;
            margin-left: auto;
            margin-right: auto;
          }
          .col {
            width: 19em;
            flex-shrink: 0;
            flex-grow: 0;
          }
          .col {
            border-right: 1px solid #d0c8b8;
            padding-right: 1.5rem;
            padding-left: 2.5rem;   /* espacio para números de línea */
            white-space: nowrap;    /* edición diplomática: solo &lt;br/&gt; explícitos rompen línea */
            overflow-x: visible;
          }
          .col:last-child {
            border-right: none;
            padding-right: 0;
          }
          .col-label {
          font-size: 0.72rem;
          color: #aaa;
          text-align: center;
          margin-bottom: var(--lh);
          
          letter-spacing: 0.05em;
          }

          span.tei-p {
          display: block;
          margin: 0;
          text-indent: 1.2em;
          line-height: var(--lh);
          }
          span.tei-p-first {
          display: block;
          margin: 0;
          text-indent: 0;
          }

          span.tei-s { display: inline; }
          span.tei-s:hover { background-color: #e8f0fb; border-radius: 2px; }

          span.tei-w {
            display: inline;
            cursor: default;
            border-bottom: 1px dotted transparent;
            transition: border-color 0.15s;
            position: relative;
          }
          span.tei-w:hover { background-color: #fdeee0; border-radius: 2px; border-bottom: 1px dotted #7a9abf; }

          span.tei-w[data-pos="VERB"]  { color: #1a4a8a; }
          span.tei-w[data-pos="NOUN"]  { color: #222; }
          span.tei-w[data-pos="ADJ"]   { color: #3a6a3a; }
          span.tei-w[data-pos="ADV"]   { color: #7a4a00; }
          span.tei-w[data-pos="ADP"]   { color: #666; }
          span.tei-w[data-pos="CCONJ"] { color: #888; }
          span.tei-w[data-pos="PRON"]  { color: #7a2a7a; }
          span.tei-w[data-pos="X"]     { color: #aaa; }

          .tooltip {
            display: none;
            position: absolute;
            bottom: 1.6em;
            left: 0;
            background: #2a2a2a;
            color: #fff;
            font-size: 0.68rem;
            font-family: monospace;
            padding: 0.3em 0.6em;
            border-radius: 4px;
            white-space: nowrap;
            width: max-content;
            min-width: 100%;
            z-index: 10;
            pointer-events: none;
            box-shadow: 0 2px 6px rgba(0,0,0,0.4);
          }
          .tooltip table { border-collapse: collapse; line-height: 1.6; font-size: 0.65rem; }
          .tooltip td { padding: 0 0.4em 0 0; vertical-align: top; }
          .tooltip .tip-key   { color: #888; }
          .tooltip .tip-lemma { color: #7ec8e3; font-weight: bold; }
          .tooltip .tip-pos   { color: #f0c060; }
          .tooltip .tip-val   { color: #aaddaa; }
          span.tei-w:hover .tooltip { display: block; }
          span.tei-sic:hover .tooltip { display: block; }

          /* abbr: subrayado punteado marrón (forma abreviada) */
          span.tei-choice-abbr {
            border-bottom: 1px dotted #8a6a2a;
            cursor: default;
          }
          /* orig: subrayado punteado gris (grafía original) */
          span.tei-choice-orig {
            border-bottom: 1px dotted #999;
            cursor: default;
          }
          .tip-expan { color: #f0a060; }

          span.tei-pc {
            margin-left: 0.0em;  /* separación mínima */
          }
          span.tei-sic {
            display: inline;
            cursor: default;
            border-bottom: 1px dotted transparent;
            transition: border-color 0.15s;
            position: relative;
          }
          span.tei-sic:hover { background-color: #fdeee0; border-radius: 2px; border-bottom: 1px dotted #7a9abf; }
          span.tei-hi-italic { font-style: italic; padding-right: 0.15em; }
          span.tei-q    { font-style: italic; padding-right: 0.15em; }
          span.tei-bibl { margin-right: -0.05em; }

          /* Citas de autoridad */
          span.tei-cit {
            border-bottom: 1px dotted #c09050;
            cursor: default;
          }
          span.tei-cit:hover {
            background: #fdf5e6;
            border-radius: 2px;
          }
         
          /* Abreviaturas y grafías originales */
          span.tei-choice {
            position: relative;
            border-bottom: 1px dashed #b09060;
            cursor: help;
          }
          span.choice-tooltip {
            display: none;
            position: absolute;
            bottom: 1.4em;
            left: 0;
            background: #5a4010;
            color: #fff8e8;
            font-size: 0.65rem;
            font-family: monospace;
            padding: 0.2em 0.5em;
            border-radius: 3px;
            white-space: nowrap;
            z-index: 11;
            pointer-events: none;
          }
          span.tei-choice:hover .choice-tooltip { display: block; }

          aside.tei-note {
            font-size: 0.75rem;
            line-height: 1.4;
            color: #666;
            border-left: 2px solid #c8a96e;
            padding: 0.2rem 0 0.2rem 0.5rem;
            margin: 0.4rem 0;
            background: #fdf8ee;
          }
          aside.tei-note .num {
            font-weight: bold;
            color: #8a6a2a;
          }

          .legend {
            margin-top: 2rem;
            padding: 0.8rem 1rem;
            background: #f0f0e8;
            border-radius: 4px;
            font-size: 0.8rem;
          }
          .legend h3 { margin: 0 0 0.5rem 0; font-size: 0.88rem; }
          .legend span { margin-right: 1rem; white-space: nowrap; }

          /* Números de línea en el margen izquierdo */
          .lb-num {
            float: left;
            clear: left;
            width: 2rem;
            margin-left: -2.5rem;
            text-align: right;
            font-size: 0.65rem;
            font-family: monospace;
            color: #bbb;
            line-height: var(--lh);
            pointer-events: none;
            user-select: none;
          }

          /* Cada 5 líneas, número más destacado */
          .lb-num.lb-5 { color: #999; font-weight: bold; }

          /* Encabezados estructurales */
          p.tei-head {
            font-size: 1.05rem;
            font-style: italic;
            text-align: center;
            margin: 0.8rem 0 0.1rem 0;
            text-indent: 0;
            letter-spacing: 0.04em;
            white-space: normal;
            width: 100%;
          }
          p.tei-subhead {
            font-size: 1rem;
            text-align: center;
            margin: 0.2rem 0 0.6rem 0;
            text-indent: 0;
            letter-spacing: 0.05em;
            white-space: normal;
            width: 100%;
          }

          /* Summarium */
          div.tei-summarium {
            margin: 0.6rem 0 0.8rem 0;
          }
          ol.tei-list {
            list-style: none;
            padding: 0;
            margin: 0;
          }
          li.tei-item {
            margin: 0.25rem 0;
            line-height: var(--lh);
            font-style: italic;
            position: relative;
            padding-left: 2.5em;
          }
          li.tei-item .lb-num {
            float: left;
            clear: left;
            margin-left: -5rem;
            width: 2rem;
            text-align: right;
          }
          li.tei-item span.tei-label {
            font-style: normal;
            position: absolute;
            left: 0;
            width: 2.5em;
          }
          span.tei-item-body {
            display: block;
          }
          span.tei-item-indent { display: inline-block; width: 1.8em; }
          span.tei-item-cont   { display: none; }
          span.tei-label {
            margin-right: 0.35em;
          }

          /* Separador entre páginas */
          .page-sep {
            text-align: center;
            margin: 2rem 0 0.5rem 0;
            border-top: 1px solid #bbb;
            padding-top: 0.4rem;
          }
          .page-sep-label {
            font-size: 0.78rem;
            color: #888;
            
            letter-spacing: 0.08em;
          }

          .stats {
            font-size: 0.78rem;
            color: #999;
            text-align: right;
            margin-bottom: 0.5rem;
          }
        
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
          .lb-num.lb-break { visibility: hidden; }
        </style>
      </head>
      <body>
        <h1>Pedro de Oñate · <em>De contractibus</em></h1>
        <h2>Disputatio LXIII · Sectio I</h2>

        <div class="stats">
          Palabras: <xsl:value-of select="count(//tei:w)"/> ·
          Oraciones: <xsl:value-of select="count(//tei:s)"/> ·
          Párrafos: <xsl:value-of select="count(//tei:p)"/>
        </div>

        
        <div class="stats">
          Palabras: <xsl:value-of select="count(//tei:w)"/> &#183;
          Oraciones: <xsl:value-of select="count(//tei:s)"/> &#183;
          Párrafos: <xsl:value-of select="count(//tei:p)"/>
        </div>

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
        </xsl:for-each>

        <!-- Leyenda POS -->
        <!-- Leyenda POS -->
        <div class="legend">
          <h3>Colores morfológicos · pasar cursor sobre palabra para ver lemma y POS</h3>
          <span style="color:#1a4a8a">■ VERB</span>
          <span style="color:#222">■ NOUN</span>
          <span style="color:#3a6a3a">■ ADJ</span>
          <span style="color:#7a4a00">■ ADV</span>
          <span style="color:#666">■ ADP</span>
          <span style="color:#888">■ CCONJ</span>
          <span style="color:#7a2a7a">■ PRON</span>
          <span style="color:#aaa">■ X</span>
        </div>

        <!-- Visor facsímil: script -->
        <script>
//<![CDATA[
(function () {
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
    var img    = panel.querySelector('.facs-img');
    var canvas = panel.querySelector('.facs-canvas');

    function trySync() {
      if (img.naturalWidth > 0 && canvas.width <= 300)
        syncCanvas(panel);
    }

    img.addEventListener('load',  trySync);
    img.addEventListener('error', function () {
      console.warn('onate-facs: imagen no encontrada:', img.src);
    });
    img.src = FACS_BASE + colId + FACS_EXT;
    /* Varios intentos para imágenes en caché (onload no siempre dispara) */
    trySync();
    setTimeout(trySync,  50);
    setTimeout(trySync, 300);
    if (cache.hasOwnProperty(colId)) return;
    cache[colId] = null;
    fetch(COORDS_BASE + colId + '.json')
      .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
      .then(function (d) { cache[colId] = d; })
      .catch(function (e) { cache[colId] = false;
                            console.warn('onate-facs:', colId, e.message); });
  }

  /* Sincronizar canvas con la imagen: trabaja en coords de pantalla.
     Guarda los factores de escala en canvas._sx/_sy para drawWordRect. */
  function syncCanvas(panel) {
    var img    = panel.querySelector('.facs-img');
    var canvas = panel.querySelector('.facs-canvas');
    var nw     = img.naturalWidth;
    var nh     = img.naturalHeight;
    if (!nw || !nh) return;
    /* .facs-scroll tiene width fija en CSS → fiable aunque img aún no esté pintada */
    var scroll = panel.querySelector('.facs-scroll');
    var dw     = (scroll && scroll.offsetWidth > 0) ? scroll.offsetWidth
                 : (img.offsetWidth > 0 ? img.offsetWidth : 400);
    var dh     = Math.round(nh * dw / nw);
    canvas.width  = dw;
    canvas.height = dh;
    canvas.style.width  = dw + 'px';
    canvas.style.height = dh + 'px';
    canvas._sx = dw / nw;
    canvas._sy = dh / nh;
  }

  /* Normalizar texto para matching: minúsculas, ſ→s, sin puntuación */
  function norm(t) {
    return (t || '').toLowerCase()
      .replace(/ſ/g, 's')   /* long-s */
      .replace(/[.,;:!?\-()[\]{}'"]/g, '')
      .trim();
  }

  /* Extraer solo el texto visible de la palabra (sin .tooltip ni .lb-break) */
  function wordText(wEl) {
    if (!wEl) return '';
    /* Para choice/orig: usar la forma expandida para matching con coords */
    var expan = wEl.querySelector('.tip-expan');
    if (expan) {
      var expanText = expan.textContent.replace(/\s+/g, ' ').trim();
      if (expanText) return expanText;
    }
    var clone = wEl.cloneNode(true);
    var tip = clone.querySelector('.tooltip');
    if (tip) tip.remove();
    var hasBreak = clone.querySelector('.lb-break');
    clone.querySelectorAll('.lb-num, .lb-break').forEach(function (s) { s.remove(); });
    var fullText = clone.textContent.replace(/\s+/g, ' ').trim();
    if (hasBreak) {
      var dashIdx = fullText.indexOf('-');
      if (dashIdx > 0) return fullText.substring(0, dashIdx).trim();
    }
    return fullText;
  }

  /* Normalización avanzada: ſ→s, ae/oe, sin puntuación */
  function normAdv(t) {
    return (t || '').toLowerCase()
      .replace(/ſ/g, 's')        /* long-s */
      .replace(/æ/g, 'ae')       /* æ */
      .replace(/œ/g, 'oe')       /* œ */
      .replace(/&/g, 'et')          /* & → et */
      .replace(/[.,;:!?()\[\]{}\-]/g, '')
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
    /* Para palabras cortadas: la primera parte es siempre la última palabra de la línea */
    if (wordEl && wordEl.querySelector('.lb-break') && twords.length > 0) {
      return twords[twords.length - 1];
    }
    var teiNorm = normAdv(wordEl ? wordText(wordEl) : '');
    if (teiNorm.length >= 1) {
      var best = null, bestScore = Infinity;
      twords.forEach(function (tw) {
        var s = textScore(teiNorm, normAdv(tw.text));
        if (s < bestScore) { bestScore = s; best = tw; }
      });
      if (bestScore <= 4) {
        /* Si hay empate (varias palabras con el mismo score), usar posición */
        var tied = twords.filter(function(tw) {
          return textScore(teiNorm, normAdv(tw.text)) === bestScore;
        });
        if (tied.length === 1) return tied[0];
        /* Desempatar por proximidad de posición X */
        var charsBefore2 = 0;
        if (wordEl && allToks.length) {
          for (var ci2 = 0; ci2 < allToks.length; ci2++) {
            if (allToks[ci2] === wordEl) break;
            charsBefore2 += wordText(allToks[ci2]).length + 1;
          }
        }
        var wordChars2  = wordEl ? wordText(wordEl).length : 3;
        var totalChars2 = allToks.reduce(function(s, el) {
          return s + wordText(el).length + 1; }, 0) || 1;
        var b2 = line.bbox;
        var propX2 = b2.x + ((charsBefore2 + wordChars2 * 0.5) / totalChars2) * b2.w;
        var nearest2 = null, nearDist2 = Infinity;
        tied.forEach(function(tw) {
          var d = Math.abs(tw.bbox.x + tw.bbox.w * 0.5 - propX2);
          if (d < nearDist2) { nearDist2 = d; nearest2 = tw; }
        });
        return nearest2 || tied[0];
      }
      /* Fallback: buscar palabra del coords que contenga el token TEI */
      twords.forEach(function (tw) {
        var tn = normAdv(tw.text);
        var an = teiNorm;
        if (an.length >= 2 && tn.includes(an)) {
          var s = tn.length - an.length + 1;
          if (s < bestScore) { bestScore = s; best = tw; }
        }
      });
      if (bestScore < Infinity) return best;
    }

    /* Intento 2: X proporcional sobre twords (sin continuaciones) */
    var charsBefore = 0;
    if (wordEl && allToks.length) {
      for (var ci = 0; ci < allToks.length; ci++) {
        if (allToks[ci] === wordEl) break;
        charsBefore += wordText(allToks[ci]).length + 1;
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
    /* Extender bbox para incluir puntuación inmediatamente siguiente */
    var wb = {x: best.bbox.x, y: best.bbox.y, w: best.bbox.w, h: best.bbox.h};
    var bestIdx = line.words.indexOf(best);
    if (bestIdx >= 0 && bestIdx < line.words.length - 1) {
      var nextW = line.words[bestIdx + 1];
      if (normAdv(nextW.text || '').length === 0 && nextW.bbox.x <= wb.x + wb.w + 12)
        wb.w = (nextW.bbox.x + nextW.bbox.w) - wb.x;
    }
    /* Asegurar que el canvas esté sincronizado antes de dibujar */
    var canvas = ctx.canvas;
    var panel  = canvas.closest ? canvas.closest('.facs-panel') : null;
    if (panel) {
      var img = panel.querySelector('.facs-img');
      if (img && img.offsetWidth > 0 && canvas._sx === undefined) syncCanvas(panel);
    }
    var sx = canvas._sx || 1;
    var sy = canvas._sy || 1;
    ctx.fillStyle   = 'rgba(186,117,23,' + (alpha || 0.18) + ')';
    ctx.fillRect  (wb.x*sx - 2, wb.y*sy - 2, wb.w*sx + 4, wb.h*sy + 4);
    ctx.strokeStyle = '#BA7517';
    ctx.lineWidth   = alpha < 0.3 ? 1 : 1.5;
    ctx.strokeRect(wb.x*sx - 2, wb.y*sy - 2, wb.w*sx + 4, wb.h*sy + 4);
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
            var sx = canvas._sx || 1, sy = canvas._sy || 1;
            ctx.fillStyle   = 'rgba(186,117,23,0.22)';
            ctx.fillRect  (pw.x*sx-2, pw.y*sy-2, pw.w*sx+4, pw.h*sy+4);
            ctx.strokeStyle = '#BA7517';
            ctx.lineWidth   = 1.5;
            ctx.strokeRect(pw.x*sx-2, pw.y*sy-2, pw.w*sx+4, pw.h*sy+4);
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
          /* Saltar tokens cuyo texto visible normaliza a vacío (& etc.) */
          var _clone = wEl.cloneNode(true);
          var _tip = _clone.querySelector('.tooltip');
          if (_tip) _tip.remove();
          var _vis = _clone.textContent.replace(/\s+/g, ' ').trim();
          if (!normAdv(_vis)) return;
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
})();
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
  <xsl:template match="tei:lb[@break='no'][@rend='no-hyphen']" priority="2">
    <br/>
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
  <xsl:template match="tei:lb[@break='no']" priority="1">
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

</xsl:stylesheet>