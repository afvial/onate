<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:tei="http://www.tei-c.org/ns/1.0"
  exclude-result-prefixes="tei">

  <xsl:strip-space elements="tei:s tei:item tei:hi tei:list tei:div tei:p tei:note"/>

  <xsl:output method="html" encoding="UTF-8" indent="yes"/>

  <!-- ============================================================ -->
  <!-- RAÍZ                                                         -->
  <!-- ============================================================ -->
  <xsl:template match="/">
    <html lang="la">
      <head>
        <meta charset="UTF-8"/>
        <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
        <title>Oñate · De contractibus · Disp. 63</title>
        <style>
          body {
            font-family: "Palatino Linotype", Palatino, Georgia, serif;
            font-size: 0.93rem;
            line-height: var(--lh);
            font-family: 'EB Garamond', Georgia, serif;
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
            font-variant: small-caps;
          }

          /* Cuadrícula de líneas — igual que el original impreso */
          :root { --lh: 1.55rem; }   /* altura de línea base */

          body {
            font-size: 0.93rem;
            line-height: var(--lh);
            font-family: 'EB Garamond', Georgia, serif;
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
            width: 25em;
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
            font-variant: small-caps;
            letter-spacing: 0.05em;
          }

          p.tei-p {
            margin: 0;
            text-indent: 1.2em;
            line-height: var(--lh);
          }
          p.tei-p-first {
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
          span.tei-w:hover { border-bottom: 1px dotted #7a9abf; }

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
            margin-left: -0.22em;  /* cancela el espacio previo */
          }
          span.tei-hi-italic { font-style: italic; }
          span.tei-q    { font-style: italic; }
          span.tei-bibl { font-style: italic; }

          /* Citas de autoridad */
          span.tei-cit {
            border-bottom: 1px dotted #c09050;
            cursor: default;
          }
          span.tei-cit:hover {
            background: #fdf5e6;
            border-radius: 2px;
          }
          /* Autor dentro de cita */
          span.tei-author {
            font-style: italic;
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
            font-size: 1rem;
            text-align: center;
            margin: 1.5rem 0 0.2rem 0;
            text-indent: 0;
            letter-spacing: 0.04em;
            white-space: normal;
          }
          p.tei-subhead {
            font-size: 0.9rem;
            font-variant: small-caps;
            text-align: center;
            margin: 0.2rem 0 0.6rem 0;
            text-indent: 0;
            letter-spacing: 0.1em;
            white-space: normal;
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
          }
          span.tei-item-indent { display: inline-block; width: 1.8em; }
          span.tei-item-cont   { display: inline-block; width: 1.8em; }
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
            font-variant: small-caps;
            letter-spacing: 0.08em;
          }

          .stats {
            font-size: 0.78rem;
            color: #999;
            text-align: right;
            margin-bottom: 0.5rem;
          }
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

        <!-- Una sección por página, dos columnas por sección -->
        <xsl:for-each select="//tei:div[@type='page'][
            not(@n = preceding::tei:div[@type='page']/@n)]">
          <xsl:variable name="page_n" select="@n"/>

          <!-- Cabecera de página (fw del div izquierdo) -->
          <xsl:apply-templates select="//tei:div[@type='page'][@n=$page_n][1]/tei:fw[@place='top-left']"/>

          <!-- Separador de página -->
          <div class="page-sep">
            <span class="page-sep-label">Página <xsl:value-of select="$page_n"/></span>
          </div>

          <!-- Dos columnas -->
          <div class="columns">
            <xsl:for-each select="//tei:div[@type='page'][@n=$page_n]">
              <div class="col">
                <div class="col-label">
                  <xsl:choose>
                    <xsl:when test="position()=1">Col. izq.</xsl:when>
                    <xsl:otherwise>Col. der.</xsl:otherwise>
                  </xsl:choose>
                </div>
                <xsl:apply-templates select="tei:p | tei:note | tei:head | tei:div[@type='summarium']"/>
              </div>
            </xsl:for-each>
          </div>
        </xsl:for-each>

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
      </body>
    </html>
  </xsl:template>

  <!-- fw top-left: construye el header completo -->
  <xsl:template match="tei:fw[@place='top-left']">
    <div class="page-header">
      <span><xsl:value-of select="."/></span>
      <span><xsl:value-of select="following-sibling::tei:fw[@place='top-center'][1]"/></span>
      <span><xsl:value-of select="following-sibling::tei:fw[@place='top-right'][1]"/></span>
    </div>
  </xsl:template>
  <xsl:template match="tei:fw"/>
  <xsl:template match="tei:cb"/>

  <!-- PÁRRAFO: el primero de cada columna no lleva sangría
       (continúa texto de la página/columna anterior) -->
  <xsl:template match="tei:p">
    <xsl:choose>
      <xsl:when test="not(preceding-sibling::tei:p)">
        <p class="tei-p tei-p-first"><xsl:apply-templates/></p>
      </xsl:when>
      <xsl:otherwise>
        <p class="tei-p"><xsl:apply-templates/></p>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:template>

  <!-- ORACIÓN -->
  <xsl:template match="tei:s">
    <span class="tei-s"><xsl:apply-templates/></span>
    <xsl:text> </xsl:text>
  </xsl:template>

  <!-- PALABRA -->
  <xsl:template match="tei:w">
    <span class="tei-w" data-lemma="{@lemma}" data-pos="{@pos}" data-msd="{@msd}">
      <span class="tooltip">
        <table>
          <tr>
            <td class="tip-key">lemma</td>
            <td class="tip-lemma"><xsl:value-of select="@lemma"/></td>
          </tr>
          <xsl:if test="@pos != ''">
            <tr>
              <td class="tip-key">POS</td>
              <td class="tip-pos"><xsl:value-of select="@pos"/></td>
            </tr>
          </xsl:if>
          <xsl:if test="@msd != ''">
            <xsl:call-template name="format-msd">
              <xsl:with-param name="msd" select="@msd"/>
            </xsl:call-template>
          </xsl:if>
        </table>
      </span>
      <!-- part="I": añadir guión al final -->
      <xsl:apply-templates/>
      <xsl:if test="@part='I'"><xsl:text>-</xsl:text></xsl:if>
    </span>
    <xsl:if test="not(following-sibling::*[1][self::tei:pc]) and not(following-sibling::*[1][self::tei:lb]) and not(@part='I')">
      <xsl:text> </xsl:text>
    </xsl:if>
  </xsl:template>

  <!-- Formatea msd: una fila de tabla por rasgo -->
  <xsl:template name="format-msd">
    <xsl:param name="msd"/>
    <xsl:variable name="feat">
      <xsl:choose>
        <xsl:when test="contains($msd, '|')"><xsl:value-of select="substring-before($msd, '|')"/></xsl:when>
        <xsl:otherwise><xsl:value-of select="$msd"/></xsl:otherwise>
      </xsl:choose>
    </xsl:variable>
    <xsl:variable name="key">
      <xsl:choose>
        <xsl:when test="contains($feat, '=')"><xsl:value-of select="substring-before($feat, '=')"/></xsl:when>
        <xsl:otherwise><xsl:value-of select="$feat"/></xsl:otherwise>
      </xsl:choose>
    </xsl:variable>
    <xsl:variable name="val">
      <xsl:choose>
        <xsl:when test="contains($feat, '=')"><xsl:value-of select="substring-after($feat, '=')"/></xsl:when>
        <xsl:otherwise></xsl:otherwise>
      </xsl:choose>
    </xsl:variable>
    <tr>
      <td class="tip-key"><xsl:value-of select="$key"/></td>
      <td class="tip-val"><xsl:value-of select="$val"/></td>
    </tr>
    <xsl:if test="contains($msd, '|')">
      <xsl:call-template name="format-msd">
        <xsl:with-param name="msd" select="substring-after($msd, '|')"/>
      </xsl:call-template>
    </xsl:if>
  </xsl:template>

  <!-- PUNTUACIÓN: margin-left negativo absorbe el espacio previo -->
  <!-- PUNTUACIÓN: word joiner (U+2060) impide wrap entre palabra y punto.
       Si viene precedida de lb, emite primero el salto de línea. -->
  <xsl:template match="tei:pc">
    <xsl:variable name="prev" select="preceding-sibling::*[1]"/>
    <xsl:choose>
      <xsl:when test="$prev[self::tei:lb and not(@break='no') and @n]">
        <!-- lb antes del pc: el pc se encarga del salto -->
        <br/>
        <xsl:variable name="n" select="$prev/@n"/>
        <xsl:variable name="mod5" select="$n mod 5"/>
        <xsl:choose>
          <xsl:when test="$mod5 = 0">
            <span class="lb-num lb-5"><xsl:value-of select="$n"/></span>
          </xsl:when>
          <xsl:otherwise>
            <span class="lb-num"><xsl:value-of select="$n"/></span>
          </xsl:otherwise>
        </xsl:choose>
      </xsl:when>
      <xsl:otherwise>
        <!-- word joiner: impide wrap entre la palabra anterior y el punto -->
        <xsl:text>&#x2060;</xsl:text>
      </xsl:otherwise>
    </xsl:choose>
    <span class="tei-pc"><xsl:value-of select="."/></span>
    <xsl:if test="not(following-sibling::*[1][self::tei:lb])">
      <xsl:text> </xsl:text>
    </xsl:if>
  </xsl:template>

  <!-- CURSIVA -->
  <xsl:template match="tei:hi[@rend='italic']">
    <span class="tei-hi-italic"><xsl:apply-templates/></span>
  </xsl:template>

  <!-- CITA: cursiva, como en el impreso original -->
  <xsl:template match="tei:q">
    <span class="tei-q"><xsl:apply-templates/></span>
  </xsl:template>

  <!-- CITA DE AUTORIDAD -->
  <xsl:template match="tei:cit">
    <span class="tei-cit">
      <xsl:if test="@xml:id">
        <xsl:attribute name="id"><xsl:value-of select="@xml:id"/></xsl:attribute>
      </xsl:if>
      <xsl:apply-templates/></span>
  </xsl:template>

  <!-- AUTOR -->
  <xsl:template match="tei:author">
    <span class="tei-author">
      <xsl:if test="@ref">
        <xsl:attribute name="data-ref"><xsl:value-of select="@ref"/></xsl:attribute>
      </xsl:if>
      <xsl:apply-templates/></span>
  </xsl:template>

  <!-- ALCANCE BIBLIOGRÁFICO (libro, capítulo, etc.) — se muestra tal cual -->
  <xsl:template match="tei:biblScope">
    <xsl:apply-templates/>
  </xsl:template>

  <!-- REFERENCIA BIBLIOGRÁFICA inline -->
  <xsl:template match="tei:bibl | tei:ref[@type='bibl']">
    <span class="tei-bibl">
      <xsl:if test="@corresp">
        <xsl:attribute name="data-corresp"><xsl:value-of select="@corresp"/></xsl:attribute>
      </xsl:if>
      <xsl:apply-templates/></span>
  </xsl:template>

  <!-- NOTAS MARGINALES -->
  <xsl:template match="tei:note[@type='marginal']">
    <aside class="tei-note">
      <xsl:if test="tei:num">
        <span class="num"><xsl:value-of select="tei:num"/>. </span>
      </xsl:if>
      <xsl:apply-templates select="tei:hi"/>
    </aside>
  </xsl:template>
  <xsl:template match="tei:note/tei:num"/>
  <xsl:template match="tei:num"><xsl:value-of select="."/></xsl:template>
  <xsl:template match="comment()"/>


  <!-- SALTO DE LÍNEA: preserva la disposición tipográfica original.
       break="no" → guión visible + <br/> (palabra cortada entre líneas)
       @n presente → número de línea en margen izquierdo
       normal      → <br/> sin número -->
  <xsl:template match="tei:lb[@break='no']">
    <xsl:text>-</xsl:text><br/>
  </xsl:template>

  <xsl:template match="tei:lb[not(@break='no') and @n]">
    <!-- Si el siguiente hermano es pc, el pc se encarga del salto -->
    <xsl:if test="not(following-sibling::*[1][self::tei:pc])">
      <br/>
      <xsl:variable name="n" select="@n"/>
      <xsl:variable name="mod5" select="$n mod 5"/>
      <xsl:choose>
        <xsl:when test="$mod5 = 0">
          <span class="lb-num lb-5"><xsl:value-of select="$n"/></span>
        </xsl:when>
        <xsl:otherwise>
          <span class="lb-num"><xsl:value-of select="$n"/></span>
        </xsl:otherwise>
      </xsl:choose>
    </xsl:if>
  </xsl:template>

  <xsl:template match="tei:lb">
    <br/>
  </xsl:template>

  <!-- CHOICE: renderiza como una sola <span> con forma original y expansión en tooltip.
       La estructura TEI es <choice><abbr|orig><w/></abbr|orig><expan|reg/></choice>.
       El <w> lleva lemma/pos/msd; <expan>/<reg> lleva la forma completa. -->
  <xsl:template match="tei:choice">
    <xsl:variable name="w"        select="(tei:abbr|tei:orig)/tei:w"/>
    <xsl:variable name="expansion">
      <xsl:choose>
        <xsl:when test="tei:expan"><xsl:value-of select="tei:expan"/></xsl:when>
        <xsl:when test="tei:reg"  ><xsl:value-of select="tei:reg"/></xsl:when>
      </xsl:choose>
    </xsl:variable>
    <xsl:variable name="kind">
      <xsl:choose>
        <xsl:when test="tei:abbr">abbr</xsl:when>
        <xsl:otherwise>orig</xsl:otherwise>
      </xsl:choose>
    </xsl:variable>

    <span class="tei-w tei-choice-{$kind}"
          data-lemma="{$w/@lemma}" data-pos="{$w/@pos}" data-msd="{$w/@msd}">
      <span class="tooltip">
        <table>
          <tr>
            <td class="tip-key">lemma</td>
            <td class="tip-lemma"><xsl:value-of select="$w/@lemma"/></td>
          </tr>
          <xsl:if test="$w/@pos != ''">
            <tr>
              <td class="tip-key">POS</td>
              <td class="tip-pos"><xsl:value-of select="$w/@pos"/></td>
            </tr>
          </xsl:if>
          <xsl:if test="$w/@msd != ''">
            <xsl:call-template name="format-msd">
              <xsl:with-param name="msd" select="$w/@msd"/>
            </xsl:call-template>
          </xsl:if>
          <xsl:if test="$expansion != ''">
            <tr>
              <td class="tip-key"><xsl:value-of select="$kind"/></td>
              <td class="tip-expan"><xsl:value-of select="$expansion"/></td>
            </tr>
          </xsl:if>
        </table>
      </span>
      <!-- Texto original: puede contener <lb break="no"/> -->
      <xsl:apply-templates select="$w/node()"/>
    </span>
    <xsl:if test="not(following-sibling::*[1][self::tei:pc]) and not(following-sibling::*[1][self::tei:lb])">
      <xsl:text> </xsl:text>
    </xsl:if>
  </xsl:template>

  <!-- lb break="no" de continuación en item con label (soft-hyphen entre líneas):
       guión + br + número + spacer de alineación.
       Solo aplica si hay un lb precedente en el mismo item (no es el primero). -->
  <xsl:template match="tei:item[tei:label]//tei:w/tei:lb[@break='no' and @n
      and preceding::tei:lb[
        ancestor::tei:item[generate-id(.)=
          generate-id(current()/ancestor::tei:item)]]]">
    <xsl:text>-</xsl:text><br/>
    <xsl:variable name="n"    select="@n"/>
    <xsl:variable name="mod5" select="$n mod 5"/>
    <xsl:choose>
      <xsl:when test="$mod5 = 0">
        <span class="lb-num lb-5"><xsl:value-of select="$n"/></span>
      </xsl:when>
      <xsl:otherwise>
        <span class="lb-num"><xsl:value-of select="$n"/></span>
      </xsl:otherwise>
    </xsl:choose>
    <span class="tei-item-cont">&#160;</span>
  </xsl:template>

  <!-- Suprimir abbr/orig/expan/reg — gestionados por el template de choice -->
  <xsl:template match="tei:choice/tei:abbr | tei:choice/tei:orig"/>
  <xsl:template match="tei:expan | tei:reg"/>

  <!-- ENCABEZADO principal (header/heading) -->
  <xsl:template match="tei:head[not(@type)]">
    <p class="tei-head"><xsl:apply-templates/></p>
  </xsl:template>

  <!-- SUBENCABEZADO (subheading) -->
  <xsl:template match="tei:head[@type='sub']">
    <p class="tei-subhead"><xsl:apply-templates/></p>
  </xsl:template>

  <!-- Primer lb dentro de item: solo número, sin salto (el label ocupa esa línea) -->
  <xsl:template match="tei:item//tei:lb[not(@break='no') and @n
      and not(preceding::tei:lb[
        ancestor::tei:item[generate-id(.)=
          generate-id(current()/ancestor::tei:item)]])]">
    <xsl:variable name="n"    select="@n"/>
    <xsl:variable name="mod5" select="$n mod 5"/>
    <xsl:choose>
      <xsl:when test="$mod5 = 0">
        <span class="lb-num lb-5"><xsl:value-of select="$n"/></span>
      </xsl:when>
      <xsl:otherwise>
        <span class="lb-num"><xsl:value-of select="$n"/></span>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:template>

  <!-- lb de continuación en item con label: br + número + spacer de alineación -->
  <xsl:template match="tei:item[tei:label]//tei:lb[not(@break='no') and @n
      and preceding::tei:lb[
        ancestor::tei:item[generate-id(.)=
          generate-id(current()/ancestor::tei:item)]]]">
    <br/>
    <xsl:variable name="n"    select="@n"/>
    <xsl:variable name="mod5" select="$n mod 5"/>
    <xsl:choose>
      <xsl:when test="$mod5 = 0">
        <span class="lb-num lb-5"><xsl:value-of select="$n"/></span>
      </xsl:when>
      <xsl:otherwise>
        <span class="lb-num"><xsl:value-of select="$n"/></span>
      </xsl:otherwise>
    </xsl:choose>
    <span class="tei-item-cont">&#160;</span>
  </xsl:template>

  <!-- SUMMARIUM -->
  <xsl:template match="tei:div[@type='summarium']">
    <div class="tei-summarium"><xsl:apply-templates/></div>
  </xsl:template>

  <xsl:template match="tei:list">
    <ol class="tei-list"><xsl:apply-templates/></ol>
  </xsl:template>

  <xsl:template match="tei:item[not(tei:label)]">
    <li class="tei-item"><span class="tei-item-indent">&#160;&#160;&#160;</span><xsl:apply-templates/></li>
  </xsl:template>

  <xsl:template match="tei:item">
    <li class="tei-item"><xsl:apply-templates/></li>
  </xsl:template>

  <xsl:template match="tei:label">
    <span class="tei-label"><xsl:apply-templates/></span>
  </xsl:template>

</xsl:stylesheet>
