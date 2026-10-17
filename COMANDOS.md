# Comandos frecuentes — Oñate, *De contractibus*

Antes de copiar los comandos, define la página con la que trabajas:

```bash
P=52          # número de página (cámbialo cada vez)
C=izq         # columna: izq o der
```

Todos los comandos usan `$P` y `$C`, así que se pueden pegar tal cual en la misma terminal.
Para pasar a la otra columna basta con `C=der` (o `C=izq`).
Orden de lectura del ensamblado: `izq → der` dentro de cada página.

---

## 1. Página nueva (flujo completo)

```bash
# 1. Copiar los PAGE XML exportados de Transkribus
ls transkribus/disp63/pg_63_${P}_*.xml

# 2. Añadir los XInclude en bibl/disp63/disp63_bibl.xml (tras los de la página anterior)
#      <xi:include href="pg_63_${P}_izq_bibl.xml"/>
#      <xi:include href="pg_63_${P}_der_bibl.xml"/>

# 3. Generar el staging inicial (NO sobre una página ya editada: lo sobrescribe)
./procesar_pagina.sh $P izq --only normalize
./procesar_pagina.sh $P der --only normalize

# 4. Corregir líneas añadidas a mano en Transkribus (id="l", "l_1"…)
python3 scripts/onate_fix_line_ids.py $P

# 5. Editar los stagings: staging/disp63/pg_63_${P}_{izq,der}.xml
#    (encabezados de sección con ##: ##SECTIO III.)

# 6. Procesar (izq da error de XInclude porque der aún no existe: es normal)
./procesar_pagina.sh $P izq
./procesar_pagina.sh $P der
./procesar_pagina.sh $P izq          # otra vez, para generar las coords de izq

# 7. Comprobar que están las coords de las dos columnas (.json y .js)
ls coords/disp63/pg_63_${P}_*

# 8. Ver el resultado (se abre directamente, sin servidor)
firefox html/disp63/disp63_facs.html
```

El pipeline completo regenera también el índice de la concordancia (paso `search`).

Qué revisar en la salida:
- `--strip-catchword: «…» se conserva.` en ambas columnas (si dice *Reclamo detectado*, comprobar que lo sea de verdad).
- La tabla del Paso 3.5: transiciones `continues` / `new` / `uncertain`.

---

## 2. Reprocesar después de editar el staging

```bash
./procesar_pagina.sh $P $C                  # pipeline completo (lo más seguro)
```

Pasos sueltos con `--only`:

| Paso | Cuándo |
|---|---|
| `normalize` | solo la primera vez (genera el staging; nunca lo sobrescribe) |
| `page2tei` | cambió el staging o `onate_tokens.py` (s larga, abreviaturas) |
| `nlp` | tras `page2tei` |
| `nlp_corrections` | correcciones manuales en `nlp_corrections/disp63/` |
| `lila` | enlace de lemas con LiLa (`@lemmaRef`) |
| `enrich` | catálogo bibliográfico (`bibl_enricher.py`, `tei_header.xml`) |
| `assemble` | une todas las páginas por XInclude |
| `sentences` | límites de `<s>` entre columnas (Paso 3.5) |
| `validate` | XML bien formado, xml:id duplicados |
| `coords` | coordenadas para el facsímil (`.json` y `.js`) |
| `html` | cambió el XSLT/CSS o `generate_facs_xsl.py` |
| `search` | regenerar el índice de la concordancia (documento entero) |

```bash
./procesar_pagina.sh $P $C --only sentences | grep p$P     # ver transiciones de la página
```

---

## 3. Reexportar desde Transkribus sin perder el staging

```bash
python3 scripts/onate_staging_merge.py \
    staging/disp63/pg_63_${P}_${C}.xml \
    transkribus/disp63/pg_63_${P}_${C}.xml \
    --dry-run                                 # primero ver qué cambia

python3 scripts/onate_staging_merge.py \
    staging/disp63/pg_63_${P}_${C}.xml \
    transkribus/disp63/pg_63_${P}_${C}.xml      # aplicar

./procesar_pagina.sh $P $C
```

Las líneas con macrón no se aplican automáticamente: revisarlas a mano.

---

## 4. Marcas del staging

| Marca | Uso |
|---|---|
| `¶` | inicio de párrafo (al comienzo de la línea: `¶//Qvomodocumq; res…`) |
| `//` | límite de oración (inicio de una oración nueva) |
| `¬` | palabra partida con guion al final de línea |
| `~` | palabra partida sin guion |
| `##` | encabezado de sección (`##SECTIO III.`) |
| `#` | subencabezado |
| `>>>` | sumario: inicio de un punto numerado |
| `>>` | sumario: línea de continuación |
| `@…@` | referencia bibliográfica (apertura y cierre) |
| `*…*` | cursiva (apertura y cierre) |
| `{sic\|corr}` | error del original con corrección (`{cnnsue\|consue}¬`) |
| `{sic\|}` | error probable sin corrección |
| `ô` | macrón que vale *n* donde la regla daría *m* (`nô` = *non*) |
| `[+palabra]` / `[-palabra]` | forzar / suprimir la s larga en esa palabra |

El `¬` va fuera de las llaves cuando el error cruza el salto de línea.

---

## 5. Ver la edición y la concordancia

Los HTML se abren directamente desde el disco, sin servidor:

```bash
firefox html/disp63/disp63_facs.html      # texto + facsímil
firefox html/disp63/concordancia.html     # buscador
```

- Desde cada resultado de la concordancia se salta a la palabra en el facsímil
  (se abre siempre en la misma pestaña aparte; los enlaces ya abiertos cambian de color).
- El facsímil tiene arriba a la derecha los botones Concordancia y Traducción.

Si al pasar el ratón no aparece el recuadro en la imagen, faltan las coordenadas en `.js`:

```bash
python3 scripts/onate_coords.py --from-json coords/disp63/*.json
```

Alternativa con servidor (desde la carpeta del proyecto):

```bash
python3 -m http.server 8000
# → http://localhost:8000/html/disp63/disp63_facs.html
```

Ejemplos de búsqueda por secuencia en la concordancia:

| Consulta | Encuentra |
|---|---|
| `[lema=pretium] [pos=NOUN & morf=Case=Gen]` | *pretium* + genitivo |
| `[pos=ADJ] [lema=pretium]` | adjetivo + *pretium* |
| `[morf=VerbForm=Ger] []` | gerundio + cualquier palabra |
| `[forma=vend*]` | formas que empiezan por *vend* |

---

## 6. Diagnóstico: dónde se pierde un cambio

```bash
# Seguir una frase única por toda la cadena
F="hominum, vnde sumitur"
grep -c "$F" staging/disp63/pg_63_${P}_${C}.xml
grep -c "$F" src/disp63/pg_63_${P}_${C}.xml
grep -c "$F" bibl/disp63/pg_63_${P}_${C}_bibl.xml
grep -c "$F" output/disp63_bibl_completo.xml
grep -c "$F" html/disp63/disp63_bibl.html

# Final de una columna / inicio de la siguiente
tail -4 staging/disp63/pg_63_${P}_der.xml
head -4 staging/disp63/pg_63_$((P+1))_izq.xml

# Ids raros en el staging (líneas añadidas a mano)
grep '<line' staging/disp63/pg_63_${P}_*.xml | grep -v 'tr_1_tl_'

# Reclamos guardados (deberían estar vacíos salvo reclamo real)
for f in .state/catchword_*; do [ -s "$f" ] && echo "$f: $(cat "$f")"; done

# Encabezados de sección sin marcar con ##
grep -n '">SECTIO' staging/disp63/*.xml

# Palabras sospechosas de error de HTR (informe: html/disp63/sospechosas.html)
python3 scripts/onate_sospechosas.py html/disp63/search_index.js
python3 scripts/onate_sospechosas.py html/disp63/search_index.js --pagina $P
# formas revisadas que están bien → lexico/formas_correctas.txt (una por línea)
```

Si el HTML no cambia: recargar sin caché (Ctrl+Shift+R).

---

## 7. Revisión y LiLa

### Panel de revisión (lo que falta por corregir, por columna)

Después de corregir una página-columna:

```bash
./procesar_pagina.sh $P $C                                          # reprocesar la página
python3 scripts/onate_sospechosas.py html/disp63/search_index.js     # erratas probables del HTR
python3 scripts/onate_revision.py                                    # → html/disp63/revision.html
xdg-open "html/disp63/revision.html#pg_63_${P}_${C}"                 # abrir en esa columna
```

Solo sospechosas de la página: `python3 scripts/onate_sospechosas.py html/disp63/search_index.js --pagina $P`.
En el navegador, recargar sin caché (Ctrl+Shift+R). Erratas: corregir en Transkribus/staging,
merge y reprocesar. Formas correctas que no deben volver a salir: `lexico/formas_correctas.txt`
(una por línea).

### Resolver un lema de LiLa (ambiguo, categoría distinta, no encontrado)

1. En `revision.html`, pulsar el botón del candidato elegido: copia la línea.
2. Pegarla al final de `lila/excepciones.tsv` y completar la nota (4.ª columna).

```
# lema        upos  ref          nota
respublica    NOUN  lila:76484   res publica "república"; no 122962
conuentionalis *    lila:96429   adjetivo; LatinCy a veces lo etiqueta NOUN
Molina        PROPN -            nombre propio: no enlazar
```

`ref`: `lila:N` (lema), `lilah:N` (hipolema) o `-` (no enlazar). `upos` `*` = cualquier categoría.
Si el lema mismo está mal (p. ej. *vendi* → *uo*), se corrige en `nlp_corrections/`.

3. Regenerar. Un lema suele aparecer en muchas columnas: se reenlaza todo el texto
   (solo LiLa y bibliografía, sin volver a pasar LatinCy) y luego los productos del documento:

```bash
for f in staging/disp63/pg_63_*.xml; do
  b=$(basename $f .xml); p=$(echo $b | cut -d_ -f3); c=$(echo $b | cut -d_ -f4)
  ./procesar_pagina.sh $p $c --only lila
  ./procesar_pagina.sh $p $c --only enrich
done
./procesar_pagina.sh $P $C --only assemble
./procesar_pagina.sh $P $C --only sentences
./procesar_pagina.sh $P $C --only html        # disp63_facs.html y demás vistas
./procesar_pagina.sh $P $C --only search
python3 scripts/onate_sospechosas.py html/disp63/search_index.js
python3 scripts/onate_revision.py
```

(Los cuatro pasos `--only` del documento procesan todo el texto: da igual qué `$P $C` tengan.)

4. Comprobar y recargar las páginas sin caché (Ctrl+Shift+R):

```bash
grep -c "^ambiguo	respublica" lila/pendientes.tsv     # 0 = resuelto
```

Solo una columna: `python3 scripts/onate_lila.py src/disp63/pg_63_${P}_${C}.xml`

---

## 8. Git

```bash
git status
git --no-pager log -1 --stat      # último commit sin paginador
git config core.pager cat         # desactivar el paginador en este repo (una vez)
```

Commit de una página (si `git status` solo muestra esa página y salidas regeneradas):

```bash
git add -A
git commit -m "Add pg_63_$P (izq/der) and regenerate outputs

- transkribus/, staging/, src/, coords/, bibl/: page $P
- bibl/disp63/disp63_bibl.xml: XInclude entries for pg_63_$P
- output/, html/, lila/: regenerated"
git push
```

Si hay archivos de otra página sin terminar, no usar `-A`: añadir solo los de la página:

```bash
git add bibl/disp63/disp63_bibl.xml html/disp63/ output/disp63_bibl_completo.xml \
        lila/estado.json lila/pendientes.tsv lila/paginas/pg_63_${P}_*.tsv \
        {transkribus,staging,src}/disp63/pg_63_${P}_*.xml \
        bibl/disp63/pg_63_${P}_*_bibl.xml coords/disp63/pg_63_${P}_*.{json,js}
```

Salir de Emacs sin guardar el mensaje de commit: `C-x C-c`, responder `n`.
