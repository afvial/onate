#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# traducir_pagina.sh
# Flujo de traducción oración por oración, independiente de procesar_pagina.sh.
# No modifica src/ ni nlp_corrections/ — solo lee el TEI ya anotado y escribe
# en translations/ y html/.
#
# Uso:
#   ./traducir_pagina.sh <página> <columna> siguiente [--n N]
#       Muestra la próxima oración sin traducir (o la oración N) con su
#       texto diplomático y la tabla lemma/pos/msd, lista para comparar
#       y traducir en la conversación.
#
#   ./traducir_pagina.sh <página> <columna> guardar <n> "<text in English>"
#       Guarda/actualiza la traducción de la oración <n>.
#
#   ./traducir_pagina.sh <página> <columna> html
#       Regenera el HTML bilingüe de esa columna (transcripción + traducción)
#       con lo que haya guardado hasta el momento.
#
#   ./traducir_pagina.sh libro
#       Regenera html/disp63/disp63_trad.html: el libro completo con todas
#       las columnas que ya tengan traducción guardada (mismo formato visual
#       que disp63_facs.html / disp63_bibl.html).
#
# Ejemplos:
#   ./traducir_pagina.sh 34 der siguiente
#   ./traducir_pagina.sh 34 der guardar 2 "El precio se dice..."
#   ./traducir_pagina.sh 34 der html
#   ./traducir_pagina.sh libro
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

SCRIPTS_DIR="scripts"
SRC_DIR="src/disp63"
TRANSLATIONS_DIR="translations/disp63"
NLP_CORR_DIR="nlp_corrections/disp63"
HTML_DIR="html/disp63"

CYAN='\033[0;36m'; RED='\033[0;31m'; NC='\033[0m'
info() { echo -e "${CYAN}→${NC} $*"; }
fail() { echo -e "${RED}✗ ERROR:${NC} $*" >&2; exit 1; }

[[ $# -lt 1 ]] && fail "Uso: $0 <página> <columna> <siguiente|guardar|html> [...]  |  $0 libro"

if [[ "$1" == "libro" ]]; then
    HTML_DIR="html/disp63"
    mkdir -p "$HTML_DIR"
    python3 "${SCRIPTS_DIR}/onate_translation_html.py" \
        --src-dir "$SRC_DIR" --trans-dir "$TRANSLATIONS_DIR" \
        --corr-dir "$NLP_CORR_DIR" --out "${HTML_DIR}/disp63_trad.html"
    exit 0
fi

[[ $# -lt 3 ]] && fail "Uso: $0 <página> <columna> <siguiente|guardar|html> [...]"

PAGE="$1"; COL="$2"; CMD="$3"; shift 3

STEM="pg_63_${PAGE}_${COL}"
SRC_XML="${SRC_DIR}/${STEM}.xml"
TRANS_JSON="${TRANSLATIONS_DIR}/${STEM}.json"
NLP_CORR_JSON="${NLP_CORR_DIR}/${STEM}.json"
HTML_OUT="${HTML_DIR}/${STEM}_bilingue.html"

[[ -f "$SRC_XML" ]] || fail "No existe: $SRC_XML (ejecuta primero procesar_pagina.sh ${PAGE} ${COL})"

case "$CMD" in
    siguiente)
        python3 "${SCRIPTS_DIR}/onate_next_sentence.py" "$SRC_XML" "$TRANS_JSON" "$@"
        ;;
    guardar)
        [[ $# -lt 2 ]] && fail "Uso: $0 ${PAGE} ${COL} guardar <n> \"<text in English>\""
        N="$1"; ES="$2"
        python3 "${SCRIPTS_DIR}/onate_save_translation.py" "$TRANS_JSON" "$N" "$ES"
        ;;
    html)
        mkdir -p "$HTML_DIR"
        CORR_ARG=""
        [[ -f "$NLP_CORR_JSON" ]] && CORR_ARG="--corrections $NLP_CORR_JSON"
        [[ -f "$TRANS_JSON" ]] || fail "Aún no hay traducciones guardadas: $TRANS_JSON"
        python3 "${SCRIPTS_DIR}/onate_bilingual_html.py" "$SRC_XML" "$TRANS_JSON" $CORR_ARG --out "$HTML_OUT"
        info "HTML bilingüe → ${HTML_OUT}"
        ;;
    *)
        fail "Comando desconocido: ${CMD} (siguiente|guardar|html)"
        ;;
esac
