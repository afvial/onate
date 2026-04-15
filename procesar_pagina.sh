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
[[ $# -lt 1 ]] && fail "Uso: $0 <página> <columna> [opciones]\n       $0 all [opciones]"

# Modo all: procesar todas las columnas disponibles en orden
if [[ "$1" == "all" ]]; then
    shift
    OPTS="$*"
    # Descubrir columnas disponibles en orden: lista de "página columna" pairs
    COLS=()
    while IFS= read -r f; do
        b=$(basename "$f" .xml)          # pg_63_35_der
        p=$(echo "$b" | cut -d_ -f3)    # 35
        c=$(echo "$b" | cut -d_ -f4)    # der
        COLS+=("$p" "$c")
    done < <(ls "${TRANSKRIBUS_DIR}"/pg_63_*.xml 2>/dev/null | sort)
    [[ ${#COLS[@]} -eq 0 ]] && fail "No se encontraron PAGE XML en ${TRANSKRIBUS_DIR}"
    echo
    echo -e "${BOLD}═══════════════════════════════════════════════════${NC}"
    echo -e "${BOLD} Pipeline completo: ${#COLS[@]} columnas${NC}"
    echo -e "${BOLD}═══════════════════════════════════════════════════${NC}"
    i=0
    while [[ $i -lt ${#COLS[@]} ]]; do
        p="${COLS[$i]}"; c="${COLS[$((i+1))]}"
        echo
        bash "$0" "$p" "$c" --only page2tei $OPTS
        bash "$0" "$p" "$c" --only enrich $OPTS
        i=$(( i + 2 ))
    done
    # Solo el último ensamblado y HTML
    echo
    info "Ensamblado y HTML finales"
    bash "$0" "${COLS[$(( ${#COLS[@]} - 2 ))]}" "${COLS[$(( ${#COLS[@]} - 1 ))]}" --only assemble
    bash "$0" "${COLS[$(( ${#COLS[@]} - 2 ))]}" "${COLS[$(( ${#COLS[@]} - 1 ))]}" --only sentences
    bash "$0" "${COLS[$(( ${#COLS[@]} - 2 ))]}" "${COLS[$(( ${#COLS[@]} - 1 ))]}" --only validate
    bash "$0" "${COLS[$(( ${#COLS[@]} - 2 ))]}" "${COLS[$(( ${#COLS[@]} - 1 ))]}" --only html
    echo
    echo -e "${BOLD}${GREEN}✓ Pipeline completo terminado${NC}"
    exit 0
fi

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
# Los reclamos tipográficos (catchwords) se detectan automáticamente con
# --strip-catchword en onate_page2tei.py. El texto detectado se guarda en
# un archivo temporal (.catchword_PAGE_COL) para usarlo como --join-left
# en la siguiente columna.

run_page2tei() {
    info "Paso 1 — PAGE XML → TEI diplomático"
    [[ -f "$PAGE_XML" ]] || fail "No existe: $PAGE_XML"

    # Leer el catchword guardado por la columna anterior (si existe)
    JOIN_ARG=""
    if [[ "$COL" == "der" ]]; then
        CATCHWORD_FILE=".catchword_${PAGE}_izq"
    else
        PREV_PAGE=$(( PAGE - 1 ))
        CATCHWORD_FILE=".catchword_${PREV_PAGE}_der"
    fi
    if [[ -f "$CATCHWORD_FILE" ]]; then
        FRAGMENT=$(cat "$CATCHWORD_FILE")
        if [[ -n "$FRAGMENT" ]]; then
            JOIN_ARG="--join-left $FRAGMENT"
            info "join-left: '${FRAGMENT}' (de ${CATCHWORD_FILE})"
        fi
    fi

    # Ejecutar page2tei con --strip-catchword; capturar el reclamo en stdout
    CATCHWORD=$(python3 "${SCRIPTS_DIR}/onate_page2tei.py" \
        "$PAGE_XML" --out-xml "$SRC_XML" --page "$PAGE" \
        --strip-catchword ${JOIN_ARG} ${VERBOSE})

    # Guardar el reclamo detectado para la siguiente columna
    SAVE_FILE=".catchword_${PAGE}_${COL}"
    printf '%s' "$CATCHWORD" > "$SAVE_FILE"
    if [[ -n "$CATCHWORD" ]]; then
        info "Reclamo detectado: '${CATCHWORD}' → guardado en ${SAVE_FILE}"
    fi

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



# ── PASO 3.5: Límites de <s> entre columnas ──────────────────────────────────
run_sentences() {
    info "Paso 3.5 — Límites de <s> entre columnas"
    [[ -f "$COMPLETO" ]] || fail "No existe: $COMPLETO"
    python3 "${SCRIPTS_DIR}/onate_sentences.py" "$COMPLETO"
    ok "Límites de oración → ${COMPLETO}"
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
        run_sentences
        run_validate
        run_html
        ;;
    page2tei)  run_page2tei ;;
    enrich)    run_enrich ;;
    assemble)  run_assemble ;;
    sentences) run_sentences ;;
    validate)  run_validate ;;
    html)      run_html ;;
    *) fail "Paso desconocido: $ONLY (page2tei|enrich|assemble|sentences|validate|html)" ;;
esac

echo
echo -e "${BOLD}${GREEN}✓ Pipeline completado${NC}"
echo
