# Comandos frecuentes — Oñate, *De contractibus*

Antes de copiar los comandos, define la página con la que trabajas:

```bash
P=52          # número de página (cámbialo cada vez)
```

Todos los comandos usan `$P`, así que se pueden pegar tal cual en la misma terminal.
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

# 6. Procesar (izq da error de XInclude porque der aún no existe: es normal)
./procesar_pagina.sh $P izq
./procesar_pagina.sh $P der
./procesar_pagina.sh $P izq          # otra vez, para generar las coords de izq

# 7. Comprobar que están las dos coords
ls coords/disp63/pg_63_${P}_*.json
```

Qué revisar en la salida:
- `--strip-catchword: «…» se conserva.` en ambas columnas (si dice *Reclamo detectado*, comprobar que lo sea de verdad).
- La tabla del Paso 3.5: transiciones `continues` / `new` / `uncertain`.

---

## 2. Reprocesar después de editar el staging

```bash
./procesar_pagina.sh $P izq                 # pipeline completo (lo más seguro)
```

Pasos sueltos con `--only`:

| Paso | Cuándo |
|---|---|
| `normalize` | solo la primera vez (genera el staging) |
| `page2tei` | cambió el staging o `onate_tokens.py` (s larga, abreviaturas) |
| `nlp` | tras `page2tei` |
| `enrich` | catálogo bibliográfico (`bibl_enricher.py`, `tei_header.xml`) |
| `assemble` | une todas las páginas por XInclude |
| `sentences` | límites de `<s>` entre columnas (Paso 3.5) |
| `validate` | XML bien formado, xml:id duplicados |
| `coords` | coordenadas para el facsímil |
| `html` | solo cambió el XSLT/CSS |

```bash
./procesar_pagina.sh $P izq --only sentences | grep p$P     # ver transiciones de la página
```

---

## 3. Reexportar desde Transkribus sin perder el staging

```bash
python3 scripts/onate_staging_merge.py \
    staging/disp63/pg_63_${P}_izq.xml \
    transkribus/disp63/pg_63_${P}_izq.xml \
    --dry-run                                 # primero ver qué cambia

python3 scripts/onate_staging_merge.py \
    staging/disp63/pg_63_${P}_izq.xml \
    transkribus/disp63/pg_63_${P}_izq.xml       # aplicar

./procesar_pagina.sh $P izq
```

Las líneas con macrón no se aplican automáticamente: revisarlas a mano.

---

## 4. Marcas del staging

| Marca | Uso |
|---|---|
| `¬` | palabra partida con guion al final de línea |
| `~` | palabra partida sin guion |
| `//` | límite de oración |
| `{sic\|corr}` | error del original con corrección (`{cnnsue\|consue}¬`) |
| `{sic\|}` | error probable sin corrección |

El `¬` va fuera de las llaves cuando el error cruza el salto de línea.

---

## 5. Diagnóstico: dónde se pierde un cambio

```bash
# Seguir una frase única por toda la cadena
F="hominum, vnde sumitur"
grep -c "$F" staging/disp63/pg_63_${P}_der.xml
grep -c "$F" src/disp63/pg_63_${P}_der.xml
grep -c "$F" bibl/disp63/pg_63_${P}_der_bibl.xml
grep -c "$F" output/disp63_bibl_completo.xml
grep -c "$F" html/disp63/disp63_bibl.html

# Final de una columna / inicio de la siguiente
tail -4 staging/disp63/pg_63_${P}_der.xml
head -4 staging/disp63/pg_63_$((P+1))_izq.xml

# Ids raros en el staging (líneas añadidas a mano)
grep '<line' staging/disp63/pg_63_${P}_*.xml | grep -v 'tr_1_tl_'

# Reclamos guardados (deberían estar vacíos salvo reclamo real)
for f in .state/catchword_*; do [ -s "$f" ] && echo "$f: $(cat "$f")"; done
```

Si el HTML no cambia: recargar sin caché (Ctrl+Shift+R).

---

## 6. LiLa

```bash
python3 scripts/onate_lila.py src/disp63/pg_63_${P}_izq.xml
less lila/pendientes.tsv          # pares (lema, POS) por revisar
# Decisiones editoriales: lila/excepciones.tsv
```

---

## 7. Git

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
        bibl/disp63/pg_63_${P}_*_bibl.xml coords/disp63/pg_63_${P}_*.json
```

Salir de Emacs sin guardar el mensaje de commit: `C-x C-c`, responder `n`.
