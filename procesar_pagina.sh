#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# procesar_pagina.sh
# Pipeline completo: PAGE XML → TEI diplomático → enriquecimiento bibl →
#                    copia a bibl/ → xinclude → validación → HTML
#
# Uso:
#   ./procesar_pagina.sh <página> <columna> [opciones]
#
# Argumentos obligatorios:
#   <página>   número de página, p.ej. 37
#   <columna>  izq | der
#
# Opciones:
#   --force-bibl   Reconstruir <bibl> aunque ya existan
#   --verbose      Mostrar detalle de tokens y abreviaturas
#   --only PASO    Ejecutar solo un paso:
#                  page2tei | enrich | assemble | validate | html
#
# Ejemplos:
#   ./procesar_pagina.sh 37 izq
#   ./procesar_pagina.sh 37 der --force-bibl
#   ./procesar_pagina.sh 37 izq --only enrich
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

# ── Configuración ─────────────────────────────────────────────────────────────
SCRIPTS_DIR="scripts"
TRANSKRIBUS_DIR="transkribus/disp63"
SRC_DIR="src/disp63"
BIBL_DIR="bibl/disp63"
BIBL_MASTER="bibl/disp63/disp63_bibl.xml"
COMPLETO="output/disp63_bibl_completo.xml"
HTML_OUT="html/disp63/disp63_bibl.html"
XSLT="xslt/onate_tei2html_bibl.xsl"

# ── Colores ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

ok()   { echo -e "${GREEN}✓${NC} $*"; }
info() { echo -e "${CYAN}→${NC} $*"; }
warn() { echo -e "${YELLOW}⚠${NC} $*"; }
fail() { echo -e "${RED}✗ ERROR:${NC} $*" >&2; exit 1; }

# ── Argumentos ────────────────────────────────────────────────────────────────
[[ $# -lt 2 ]] && fail "Uso: $0 <página> <columna> [opciones]"

PAGE="$1"; COL="$2"; shift 2

FORCE_BIBL=""; VERBOSE=""; ONLY=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --force-bibl) FORCE_BIBL="--force-bibl" ;;
        --verbose)    VERBOSE="--verbose" ;;
        --only)       shift; ONLY="$1" ;;
        *) fail "Opción desconocida: $1" ;;
    esac
    shift
done

# ── Nombres de archivo ────────────────────────────────────────────────────────
STEM="pg_63_${PAGE}_${COL}"
PAGE_XML="${TRANSKRIBUS_DIR}/${STEM}.xml"
SRC_XML="${SRC_DIR}/${STEM}.xml"
BIBL_XML="${BIBL_DIR}/${STEM}_bibl.xml"

mkdir -p "$SRC_DIR" "$BIBL_DIR" "output" "html/disp63"

echo
echo -e "${BOLD}═══════════════════════════════════════════════════${NC}"
echo -e "${BOLD} Pipeline: página ${PAGE} columna ${COL}${NC}"
echo -e "${BOLD}═══════════════════════════════════════════════════${NC}"

# ── PASO 1: PAGE XML → TEI diplomático ───────────────────────────────────────
run_page2tei() {
    info "Paso 1 — PAGE XML → TEI diplomático"
    [[ -f "$PAGE_XML" ]] || fail "No existe: $PAGE_XML"
    python3 "${SCRIPTS_DIR}/onate_page2tei.py" \
        "$PAGE_XML" --out-xml "$SRC_XML" --page "$PAGE" ${VERBOSE}
    ok "TEI diplomático → ${SRC_XML}"
}

# ── PASO 2: Enriquecimiento bibliográfico ─────────────────────────────────────
run_enrich() {
    info "Paso 2 — Enriquecimiento bibliográfico"
    [[ -f "$SRC_XML" ]] || fail "No existe: $SRC_XML"
    python3 "${SCRIPTS_DIR}/bibl_enricher.py" \
        "$SRC_XML" "$BIBL_XML" ${FORCE_BIBL}
    ok "TEI enriquecido → ${BIBL_XML}"
}

# ── PASO 3: Ensamblado XInclude ───────────────────────────────────────────────
run_assemble() {
    info "Paso 3 — Ensamblado XInclude"
    [[ -f "$BIBL_MASTER" ]] || fail "No existe archivo maestro: $BIBL_MASTER"
    [[ -f "$BIBL_XML" ]]    || fail "No existe: $BIBL_XML"
    xmllint --xinclude "$BIBL_MASTER" --output "$COMPLETO"
    ok "Ensamblado → ${COMPLETO}"
}

# ── PASO 4: Validación ────────────────────────────────────────────────────────
run_validate() {
    info "Paso 4 — Validación XML"
    [[ -f "$COMPLETO" ]] || fail "No existe: $COMPLETO"
    if xmllint --noout "$COMPLETO" 2>/dev/null; then
        ok "XML bien formado"
    else
        fail "XML mal formado en ${COMPLETO}"
    fi
    DUPES=$(grep -o 'xml:id="[^"]*"' "$COMPLETO" | sort | uniq -d | wc -l)
    if [[ "$DUPES" -gt 0 ]]; then
        warn "${DUPES} xml:id duplicado(s):"
        grep -o 'xml:id="[^"]*"' "$COMPLETO" | sort | uniq -d | head -5
    else
        ok "Sin xml:id duplicados"
    fi
}

# ── PASO 5: HTML ──────────────────────────────────────────────────────────────
run_html() {
    info "Paso 5 — Transformación a HTML"
    [[ -f "$XSLT" ]]     || { warn "XSLT no encontrado: ${XSLT}"; return; }
    [[ -f "$COMPLETO" ]] || fail "No existe: $COMPLETO"
    xsltproc "$XSLT" "$COMPLETO" > "$HTML_OUT"
    ok "HTML → ${HTML_OUT}"
}

# ── Ejecutar ──────────────────────────────────────────────────────────────────
case "$ONLY" in
    "")
        run_page2tei
        run_enrich
        run_assemble
        run_validate
        run_html
        ;;
    page2tei)  run_page2tei ;;
    enrich)    run_enrich ;;
    assemble)  run_assemble ;;
    validate)  run_validate ;;
    html)      run_html ;;
    *) fail "Paso desconocido: $ONLY (page2tei|enrich|assemble|validate|html)" ;;
esac

echo
echo -e "${BOLD}${GREEN}✓ Pipeline completado${NC}"
echo
