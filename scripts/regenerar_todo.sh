#!/usr/bin/env bash
# Regenera todo el corpus: páginas en orden (sin search/rdf), y después
# índice, RDF, sospechosas y revisión una sola vez.
set -u
cd "$(dirname "$0")/.."
LOG="log/regenerar_$(date +%Y%m%d_%H%M).log"
mkdir -p log
{
  echo "=== Inicio: $(date)"
  unset SKIP
  for f in $(ls staging/disp63/pg_*.xml | sort -V); do
    b=$(basename "$f" .xml); p=$(echo "$b" | cut -d_ -f3); c=$(echo "$b" | cut -d_ -f4)
    if [ -f "src/disp63/$b.xml" ]; then
      echo "=== $b  ($(date +%H:%M))"
      ./procesar_pagina.sh "$p" "$c" --skip search,rdf
    fi
  done
  last=$(ls src/disp63/pg_*.xml | sort -V | tail -1 | xargs basename | sed 's/\.xml$//')
  p=$(echo "$last" | cut -d_ -f3); c=$(echo "$last" | cut -d_ -f4)
  echo "=== Índice y RDF  ($(date +%H:%M))"
  ./procesar_pagina.sh "$p" "$c" --only search
  ./procesar_pagina.sh "$p" "$c" --only rdf
  python3 scripts/onate_sospechosas.py html/disp63/search_index.js --lila lila/pendientes.tsv
  python3 scripts/onate_revision.py
  echo "=== Fin: $(date)"
} 2>&1 | tee "$LOG"
echo "Registro: $LOG"
