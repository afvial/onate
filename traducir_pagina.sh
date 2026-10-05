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
#   ./traducir_pagina.sh <página> <columna> guardar <n> "<texto en español>"
#       Guarda/actualiza la traducción de la oración <n>.
#
#   ./traducir_pagina.sh <página> <columna> html
#       Regenera el HTML bilingüe de esa columna (transcripción + traducción)
#       con lo que haya guardado hasta el momento.
#
#   ./traducir_pagina.sh <página> <columna> sentido <n> <forma> <synset> --match "<texto>" [opciones]
#       Ancla el sentido de una palabra de la oración <n> a un synset del
#       Latin WordNet (los lista `siguiente`). Rellena lemmaRef, URI y
#       definición, y comprueba que el synset sea de ese lema.
#       Opciones: --match-occ N  --occ N  --gloss EN  --nota "..."  --force
#
#   ./traducir_pagina.sh <página> <columna> candidatos
#       Escribe candidatos/disp63/<stem>/sNN.md: un archivo por oración con
#       los sentidos posibles (Latin WordNet) de cada palabra relevante.
#
#   ./traducir_pagina.sh candidatos
#       Lo mismo para todas las columnas de src/disp63.
#
#   ./traducir_pagina.sh <página> <columna> validar
#       Revisa senses/ de la columna: añade lemmaRef, normaliza URIs y avisa
#       de synsets que no pertenecen a su lema.
#
#   ./traducir_pagina.sh libro
#       Regenera html/disp63/disp63_trad.html inyectando las traducciones
#       guardadas (y los sentidos de senses/) sobre disp63_facs.html, el HTML
#       que ya generó el XSLT: misma tipografía y espaciado.
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
SENSES_DIR="senses/disp63"
LWN_INDEX="cache/lwn_index.json"
HTML_DIR="html/disp63"

CYAN='\033[0;36m'; RED='\033[0;31m'; NC='\033[0m'
info() { echo -e "${CYAN}→${NC} $*"; }
fail() { echo -e "${RED}✗ ERROR:${NC} $*" >&2; exit 1; }

[[ $# -lt 1 ]] && fail "Uso: $0 <página> <columna> <siguiente|guardar|html> [...]  |  $0 libro"

if [[ "$1" == "candidatos" ]]; then
    python3 "${SCRIPTS_DIR}/onate_sense_candidates.py" --index "cache/lwn_index.json" "${SRC_DIR}"/pg_63_*_*.xml
    exit 0
fi

if [[ "$1" == "libro" ]]; then
    HTML_DIR="html/disp63"
    mkdir -p "$HTML_DIR"
    # Enfoque actual (commit b2bb963): inyectar la traducción sobre el HTML
    # que ya generó el XSLT, conservando su tipografía y espaciado.
    [[ -f "${HTML_DIR}/disp63_facs.html" ]] || fail "Falta ${HTML_DIR}/disp63_facs.html (ejecuta procesar_pagina.sh … --only html)"
    python3 "${SCRIPTS_DIR}/onate_inject_translation.py" "${HTML_DIR}/disp63_facs.html" \
        --trans-dir "$TRANSLATIONS_DIR" --senses-dir "senses/disp63" \
        --out "${HTML_DIR}/disp63_trad.html"
    exit 0
fi

[[ $# -lt 3 ]] && fail "Uso: $0 <página> <columna> <siguiente|guardar|html> [...]"

PAGE="$1"; COL="$2"; CMD="$3"; shift 3

STEM="pg_63_${PAGE}_${COL}"
SRC_XML="${SRC_DIR}/${STEM}.xml"
TRANS_JSON="${TRANSLATIONS_DIR}/${STEM}.json"
NLP_CORR_JSON="${NLP_CORR_DIR}/${STEM}.json"
SENSES_JSON="${SENSES_DIR}/${STEM}.json"
HTML_OUT="${HTML_DIR}/${STEM}_bilingue.html"

[[ -f "$SRC_XML" ]] || fail "No existe: $SRC_XML (ejecuta primero procesar_pagina.sh ${PAGE} ${COL})"

case "$CMD" in
    siguiente)
        python3 "${SCRIPTS_DIR}/onate_next_sentence.py" "$SRC_XML" "$TRANS_JSON" \
            --senses-json "$SENSES_JSON" --index "$LWN_INDEX" "$@"
        ;;
    sentido)
        [[ $# -lt 3 ]] && fail "Uso: $0 ${PAGE} ${COL} sentido <n> <forma> <synset> --match \"<texto>\" [...]"
        python3 "${SCRIPTS_DIR}/onate_save_sense.py" --index "$LWN_INDEX" anclar \
            "$SENSES_JSON" "$SRC_XML" "$@"
        ;;
    candidatos)
        python3 "${SCRIPTS_DIR}/onate_sense_candidates.py" --index "$LWN_INDEX" "$SRC_XML"
        ;;
    validar)
        [[ -f "$SENSES_JSON" ]] || fail "No hay sentidos anclados: $SENSES_JSON"
        python3 "${SCRIPTS_DIR}/onate_save_sense.py" --index "$LWN_INDEX" validar \
            "$SENSES_JSON" "$SRC_XML"
        ;;
    guardar)
        [[ $# -lt 2 ]] && fail "Uso: $0 ${PAGE} ${COL} guardar <n> \"<texto en español>\""
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
        fail "Comando desconocido: ${CMD} (siguiente|guardar|sentido|candidatos|validar|html)"
        ;;
esac
