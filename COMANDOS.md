# Comandos frecuentes — Oñate, *De contractibus*

## 0. Preparar la terminal

Al abrir una terminal nueva:

```bash
cd ~/Documents/onate
source venv/bin/activate        # el indicador debe mostrar (venv)
unset SKIP                      # por si quedó activa de otra sesión
P=48; C=izq                     # página y columna (izq o der)
```

Todos los comandos usan `$P` y `$C`. Para pasar a la otra columna basta con `C=der`.
Orden de lectura: `izq → der` dentro de cada página.

---

## 1. Ciclo de revisión de una columna

### 1.1 Página nueva (solo la primera vez)

```bash
ls transkribus/disp63/pg_63_${P}_*.xml           # PAGE XML exportados de Transkribus
# Añadir los XInclude en bibl/disp63/disp63_bibl.xml (tras los de la página anterior):
#   <xi:include href="pg_63_${P}_izq_bibl.xml"/>
#   <xi:include href="pg_63_${P}_der_bibl.xml"/>
./procesar_pagina.sh $P izq --only normalize     # genera el staging (NO sobre uno ya editado)
./procesar_pagina.sh $P der --only normalize
python3 scripts/onate_fix_line_ids.py $P         # líneas añadidas a mano en Transkribus (l, l_1…)
```

### 1.2 Comprobar la numeración de las líneas

Las líneas deben ir de `tr_1_tl_1` en adelante, sin huecos. Si no, las coordenadas
del facsímil salen desplazadas.

```bash
python3 scripts/onate_renumerar.py $P $C --comprobar
python3 scripts/onate_renumerar.py $P $C          # renumera PAGE XML y staging a la vez
```

### 1.3 Procesar una primera vez

Aunque la columna tenga errores: el informe previo se apoya en el análisis de LatinCy.

```bash
./procesar_pagina.sh $P $C --skip search,rdf
```

### 1.4 Informe previo

```bash
python3 scripts/onate_precheck.py $P $C            # ver la lista
python3 scripts/onate_precheck.py $P $C --anadir   # añadirla al archivo de correcciones
```

Detecta: cortes de línea sin marcar, lecturas dudosas (con propuestas según las
confusiones típicas de Transkribus: n/u, c/e, f/ſ, r/t, C/[, J/]…), palabras que
parecen abreviadas en el impreso (caja estrecha para su texto), abreviaturas no
registradas y lemas problemáticos. Todas las filas salen comentadas (`#`).
Es una guía para mirar el facsímil, no una lista para aplicar a ciegas.

### 1.5 Archivo de correcciones

`correcciones/disp63/pg_63_P_C.tsv`, separado por tabuladores:

```
linea       original      nuevo                 page   nota
tr_1_tl_8   anticij ata   anticipata                   leído «anticij ata»
tr_1_tl_4   @Corrad.      @{Corrad.|Conrad.}           errata del impresor
#tr_1_tl_13 con¬          cō¬                          ¿macrón? comprobar
```

- Cada fila sustituye `original` por `nuevo` en esa línea del staging (primera aparición).
- **Filas con `#`**: dudosas, no se aplican. Tras mirar el facsímil:
  de acuerdo → quitar el `#`; otra lectura → quitar el `#` y cambiar `nuevo`;
  nada que corregir → borrar la fila.
- **Columna `page`**: vacía = el script decide (el PAGE XML solo cambia si cambia la
  lectura, no las marcas); `si` = cambiar siempre el PAGE XML; `no` = solo el staging.
- Añadir una fila sin abrir el archivo:
  `printf 'tr_1_tl_25\tvel minuunt\tvel minuunt.\t\tpunto final\n' >> correcciones/disp63/pg_63_${P}_${C}.tsv`

### 1.6 Aplicar las correcciones

```bash
python3 scripts/onate_aplicar.py $P $C --dry-run     # ver qué haría
python3 scripts/onate_aplicar.py $P $C --procesar    # aplicar y procesar
```

Las filas ya aplicadas salen como `· ya estaba aplicado`. Si alguna falla, no se escribe nada.
Si un cambio altera el número de palabras (`potestántelligi` → `potest intelligi`),
avisa `⚠ revisar cajas`: hay que dividir o unir las cajas del PAGE XML a mano.

### 1.7 Lemas y LiLa

| Problema | Dónde se corrige |
|---|---|
| Lema o categoría erróneos en todo el corpus (*Quarta* → *quartus*) | `MANUAL_LEMMA` en `scripts/onate_nlp.py` |
| Lema o morfología de una aparición concreta | `nlp_corrections/disp63/pg_63_P_C.json` |
| Elegir entre varias entradas de LiLa | `lila/excepciones.tsv` |
| Autor o lugar sin enlace en LiLa | `lila/excepciones.tsv` con `-` (y `lugares.tsv` para lugares) |

Ver los candidatos de LiLa (con su flexión y su familia de palabras):

```bash
python3 scripts/lila_candidatos.py uolo tempus paro
```

Criterio práctico: elegir el candidato con la flexión de la forma del texto
(ablativo en *‑u* → 4.ª decl.; genitivo en *‑oris* → 3.ª) y cuya familia corresponda
al sentido (*uolo* «querer»: *beneuolus*; no «volar»: *auolo*).

Formato de `lila/excepciones.tsv`:

```
lema        upos  ref           nota
tempus      NOUN  lila:127522   «tiempo»; no 127796 (sien)
duo         *     lila:100246   numeral (LatinCy: DET)
Molina      PROPN -             autor: enlazado vía listPerson
```

`ref`: `lila:N` (lema), `lilah:N` (hipolema) o `-` (no enlazar). `upos` `*` = cualquier categoría.

Sintaxis de `nlp_corrections`:

```
"palabra":    "lemma=…,pos=…,Case=…"   → todas las apariciones de la página
"palabra#N":  "Case=…"                 → solo la N-ésima (orden de lectura)
```

### 1.8 Comprobar y cerrar

```bash
python3 scripts/onate_staging_merge.py staging/disp63/pg_63_${P}_${C}.xml \
    transkribus/disp63/pg_63_${P}_${C}.xml --dry-run   # debe decir «Sin cambios de texto»
./procesar_pagina.sh $P $C --only search
python3 scripts/onate_sospechosas.py html/disp63/search_index.js --lila lila/pendientes.tsv
python3 scripts/onate_revision.py
firefox "file://$PWD/html/disp63/revision.html#pg_63_${P}_${C}"
```

Después, el commit (sección 7).

---

## 2. Marcas del staging

| Marca | Uso | Ejemplo |
|---|---|---|
| `¶` | inicio de párrafo (al comienzo de la línea) | `¶//Qvomodocumq; res…` |
| `//` | inicio de una oración nueva | `pretium. //Secundò` |
| `¬` | palabra partida con guion impreso | `pre¬` / `tium` |
| `~` | palabra partida sin guion | `mer~` / `cis` |
| `-\|` | guion impreso entre dos palabras distintas | `præ-\|` / `omnibus` |
| `##` | encabezado de sección | `##SECTIO III.` |
| `#` | subencabezado | `#Quæ augeant…` |
| `>>>` | sumario: inicio de una entrada numerada | `>>>70 Quæ ſint…` |
| `>>` | sumario: línea de continuación | `>>tum augent…` |
| `@…@` | cita bibliográfica | `@Molin. disp. 348.@` |
| `^` | cita discontinua: une dos citas separadas por texto | `@Aug.@ ^ retulimus @lib. 8.@` |
| `*…*` | cursiva (por fuera de las `@`) | `*@Nau. lib. 3.@*` |
| `{sic\|corr}` | errata del impresor (forma impresa \| corrección) | `{inconſnltus\|inconsultus}` |
| `{sic\|}` | error probable sin corrección | |
| `{_}` / `{_N}` | hueco en blanco significativo del impreso | `dist. {_3}` |
| `[-palabra]` | s redonda en medio de palabra (excepción a la regla) | `[-iust.]iust.` |
| `[+palabra]` | forzar la s larga | |
| `[=forma]` | forma diplomática exacta (evita ligaduras automáticas) | `[=poeta]poeta` |
| `%lg\|…%` | palabra en otra lengua | |

Notas:
- El `¬` va fuera de las llaves cuando el error cruza el salto de línea.
- La cita discontinua (`^`) solo funciona dentro de una misma columna.
- En el XML, `&` se escribe `&amp;`.

---

## 3. Criterios editoriales

**Citas.** Solo se marca con `@` lo que remite a una obra concreta (autor y obra, ley,
Glossa…). Fuera de `@`: menciones genéricas (*DD.*, *communiter Doctores*, *fere omnes
citati*) y conectores (*supra cit.*, *ibi tenet*, *qui bene monent*). Los datos de las
citas se transcriben como están impresos; las discrepancias se anotan en
`notas/citas_discrepancias.tsv`.

**Lecturas y erratas.** La letra poco clara se transcribe como la lectura evidente.
Solo se marca errata (`{sic|corr}`) lo que se ve claramente mal en el impreso.
Un error de Transkribus se corrige directamente, sin llaves.

**S larga.** El pipeline aplica una regla de posición (comprobada en un 98,5 %):
ſ a principio y en medio de palabra (también ante *f* y ante el punto de una
abreviatura: *verſ.*), s redonda a final de palabra, S mayúscula sin cambio.
Ya no hace falta añadir raíces. Solo hay que marcar con `[-palabra]` las s redondas
en medio de palabra que se vean en el facsímil. Excepciones fijas en `LONG_S`
(`scripts/onate_tokens.py`), p. ej. *expreſsè*.

**Macrones y tildes.** Se transcriben como están impresos (*pretiū*, *cōmercio*, *expēſas*)
y el pipeline los expande: ante *p/b/m* → *m*; ante otra consonante → *n*; a final de
palabra → *m*. Cuando el macrón vale *n* donde la regla daría *m*, se usa `ô`
(`nô` = *non*). Solo el facsímil muestra los macrones: Transkribus los desarrolla.

**PAGE XML o solo staging.** Al PAGE XML van los cambios de lectura (letras, palabras,
puntuación, acentos). Las marcas editoriales (macrones, ſ, citas, cortes, erratas,
párrafos) van solo al staging. `onate_aplicar.py` lo decide así automáticamente.

**Grafías de época** (*prætium*, *precium*, *Peruiani*…): se conservan y se regularizan
con `ORIG_REG` en `onate_tokens.py`.

---

## 4. El pipeline

```bash
./procesar_pagina.sh $P $C                        # completo
./procesar_pagina.sh $P $C --skip search,rdf      # sin índice ni RDF (más rápido al editar)
./procesar_pagina.sh $P $C --only PASO            # un solo paso
```

| Paso | Nº | Cuándo |
|---|---|---|
| `normalize` | 0 | solo la primera vez (genera el staging; nunca lo sobrescribe) |
| `page2tei` | 1 | cambió el staging o `onate_tokens.py` |
| `nlp` | 1.5 | tras `page2tei` |
| `nlp_corrections` | 1.6 | correcciones manuales de la página |
| `lila` | 1.7 | enlace con LiLa (incluye lugares) |
| `enrich` | 2 | catálogo bibliográfico (`bibl_enricher.py`, `tei_header.xml`) |
| `assemble` | 3 | une todas las páginas |
| `sentences` | 3.5 | oraciones y palabras partidas entre columnas |
| `validate` | 4 | XML bien formado, xml:id duplicados |
| `coords` | 4.5 | coordenadas del facsímil |
| `html` | 5 | cambió el XSLT/CSS o `generate_facs_xsl.py` |
| `search` | 6 | índice de la concordancia y de la revisión (documento entero) |
| `rdf` | 7 | análisis por oración (`oraciones.js`, `rdf/`) |

`--skip` admite nombres o números (`--skip 6,7`). Para toda una sesión:
`export SKIP="search rdf"`, y al terminar `unset SKIP`.
**`--only` tiene prioridad sobre `SKIP`**: el paso pedido se ejecuta siempre.
Los pasos 3 a 7 trabajan sobre el documento entero: da igual qué `$P $C` se usen.

Ver las transiciones de oración de la página:

```bash
./procesar_pagina.sh $P $C --only sentences | grep p$P
```

### Regenerar todo el corpus

Necesario cuando cambian `onate_tokens.py`, `onate_nlp.py`, `excepciones.tsv`
o las plantillas, para que el cambio llegue a todas las páginas (~25 min):

```bash
unset SKIP
systemd-inhibit --what=sleep:idle:handle-lid-switch --who="onate" --why="Regeneración" \
  ./scripts/regenerar_todo.sh
grep -iE 'error|traceback' $(ls -t log/regenerar_*.log | head -1)   # no debe mostrar nada
```

Regenerar, guardar y suspender el ordenador al terminar:

```bash
unset SKIP
systemd-inhibit --what=sleep:idle:handle-lid-switch --who="onate" --why="Regeneración" \
  ./scripts/regenerar_todo.sh && git add -A && git commit -m "Corpus regenerado" && git push
systemctl suspend
```

### Reexportar desde Transkribus sin perder el staging

```bash
python3 scripts/onate_staging_merge.py staging/disp63/pg_63_${P}_${C}.xml \
    transkribus/disp63/pg_63_${P}_${C}.xml --dry-run       # ver qué cambia
python3 scripts/onate_staging_merge.py staging/disp63/pg_63_${P}_${C}.xml \
    transkribus/disp63/pg_63_${P}_${C}.xml                 # aplicar
./procesar_pagina.sh $P $C
```

Las líneas con macrón no se aplican automáticamente: revisarlas a mano.

---

## 5. Ver la edición

```bash
firefox html/disp63/disp63_facs.html      # texto + facsímil
firefox html/disp63/concordancia.html     # buscador
firefox html/disp63/revision.html         # lo que queda por revisar
```

Recargar siempre sin caché (Ctrl+Shift+R). Con servidor: `python3 -m http.server 8000`
→ `http://localhost:8000/html/disp63/disp63_facs.html`.

Búsquedas por secuencia en la concordancia:

| Consulta | Encuentra |
|---|---|
| `[lema=pretium] [pos=NOUN & morf=Case=Gen]` | *pretium* + genitivo |
| `[pos=ADJ] [lema=pretium]` | adjetivo + *pretium* |
| `[morf=VerbForm=Ger] []` | gerundio + cualquier palabra |
| `[forma=vend*]` | formas que empiezan por *vend* |

---

## 6. Problemas frecuentes

| Síntoma | Causa y solución |
|---|---|
| La revisión muestra cosas ya corregidas | índice sin actualizar: `ls -l html/disp63/search_index.js`; `unset SKIP` y `--only search` |
| «Paso omitido» con `--only` | versión antigua del script; `unset SKIP` |
| Las cajas del facsímil no corresponden a la palabra | numeración de líneas con huecos: `onate_renumerar.py` |
| No aparece el recuadro al pasar el ratón | faltan coordenadas: `python3 scripts/onate_coords.py --from-json coords/disp63/*.json` |
| `No module named 'lxml'` | terminal sin `(venv)`: `source venv/bin/activate` |
| Archivo `pg_63__.xml` | `P` y `C` vacías: definirlas |
| Un cambio en un archivo «desaparece» | Emacs guardó un buffer antiguo: `M-x revert-buffer`; `global-auto-revert-mode` activado |
| Una palabra sale mal en LiLa en una página y bien en otra | la página no se ha regenerado desde el cambio |
| Un `sed` cambió otras páginas | usar `onate_aplicar.py` (limitado a una línea) o comprobar antes con `grep -l` |

Seguir un cambio por toda la cadena:

```bash
F="hominum, vnde sumitur"
for f in staging/disp63/pg_63_${P}_${C}.xml src/disp63/pg_63_${P}_${C}.xml \
         bibl/disp63/pg_63_${P}_${C}_bibl.xml output/disp63_bibl_completo.xml html/disp63/disp63_bibl.html; do
  echo "$(grep -c "$F" $f)  $f"; done
```

Otras comprobaciones:

```bash
tail -4 staging/disp63/pg_63_${P}_der.xml; head -4 staging/disp63/pg_63_$((P+1))_izq.xml   # cambio de página
grep '<line' staging/disp63/pg_63_${P}_*.xml | grep -v 'tr_1_tl_'     # ids raros
grep -n '">SECTIO' staging/disp63/*.xml                                # encabezados sin ##
for f in .state/catchword_*; do [ -s "$f" ] && echo "$f: $(cat "$f")"; done   # reclamos
```

Formas revisadas que están bien y no deben volver a salir como sospechosas:
`lexico/formas_correctas.txt` (una por línea).

---

## 7. Git

Dos commits por columna: primero la revisión y los scripts, después lo regenerado.

```bash
git add staging/disp63/pg_63_${P}_${C}.xml transkribus/disp63/pg_63_${P}_${C}.xml \
        correcciones/disp63/pg_63_${P}_${C}.tsv nlp_corrections/ scripts/ lila/excepciones.tsv
git commit -m "pg_63_${P}_${C}: revisión"
git add src/ bibl/ coords/ lila/ output/ html/ rdf/ revision/
git commit -m "pg_63_${P}_${C} regenerada"
git push
git status                       # debe decir «working tree clean»
```

Antes de cada commit, comprobar con `git status` que no entra un archivo de otra página.

```bash
git --no-pager log -1 --stat     # último commit
git config core.pager cat        # sin paginador en este repo (una vez)
```

Salir de Emacs sin guardar el mensaje de commit: `C-x C-c`, responder `n`.
