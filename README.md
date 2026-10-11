# Onate - De contractibus - Digital Diplomatic Edition

A digital edition of Pedro de Onate SJ, De contractibus (Rome, 1646-1654),
Tractatus XXI: De emptione et venditione, Disputatio LXIII.

## Overview

This project produces a TEI XML diplomatic edition from Transkribus HTR output,
with morphological annotation, lemma linking to LiLa, bibliographic enrichment,
sentence segmentation, an HTML review interface with an interactive facsimile
viewer, and a searchable concordance (form, lemma, POS, morphology) whose results
link to the exact word in the facsimile. The pipeline is entirely command-line
driven and version-controlled with Git.

**Editor:** Andres Vial
**Source:** De contractibus, Tomus III, Francesco Cavalli, Rome, 1646-1654
**Licence:** CC BY 4.0

---

## Toolchain

| Tool | Role |
|---|---|
| Transkribus | HTR transcription -> PAGE XML |
| Python 3 + lxml | Pipeline scripts |
| LatinCy (la_core_web_lg) | Morphological annotation (POS, lemma, MSD) |
| Tesseract (pytesseract) | Per-word coordinate extraction for facsimile hover |
| Emacs + nxml-mode | Manual staging review and TEI editing |
| xsltproc | TEI -> HTML transformation |
| Git | Version control |

---

## Repository Structure

```
onate/
  transkribus/disp63/     PAGE XML exports from Transkribus (one file per column)
  staging/disp63/         Normalised staging files (one file per column, manually reviewed)
  src/disp63/             TEI diplomatic layer + morphological annotation
  bibl/disp63/            TEI bibliographic layer
    disp63_bibl.xml       XInclude master file
  nlp_corrections/disp63/ Per-file manual overrides of lemma/pos/msd (see below)
  translations/disp63/    Sentence-level translations, keyed by sentence number
  senses/disp63/          Word-sense anchoring to LiLa: Linking Latin (see below)
  output/                 Assembled XML
  coords/disp63/          Per-word bounding boxes (Tesseract, aligned to Transkribus),
                          as .json and as .js (loadable from file://, see below)
  facsimiles/disp63/      Page images used by the interactive facsimile viewer
  html/disp63/            HTML interfaces (see below), concordancia.html and its
                          search index (search_index.js)
  lila/                   LiLa linking reports (pendientes.tsv) and editorial
                          decisions (excepciones.tsv)
  xslt/                   XSLT stylesheets
  scripts/                Python pipeline scripts
  doc/                    Project documentation and historical reference files
  .state/                 Pipeline-internal state (catchwords between columns); safe to delete
  COMANDOS.md             Frequently used commands (Spanish), page number as $P
  bibl_catalog.json       Authority catalogue for bibliographic citations
  tei_header.xml          TEI header, works catalogue (listBibl) and person registry (particDesc)
```

---

## Pipeline

Each page of the source is normally a two-column folio. Columns are processed
in reading order (left before right) and identified as pg_63_NN_izq (left)
and pg_63_NN_der (right). Some pages (typically at the start of a
disputation) are single-column and use a different suffix, e.g.
pg_63_33_unica -- the pipeline detects the column count automatically and
adjusts both the catchword-joining logic and the HTML layout accordingly.

The pipeline has two phases. The first -- normalisation -- produces a staging
file that is reviewed and edited manually before the automated steps run. The
second phase is fully automated and driven by procesar_pagina.sh.

```
transkribus/disp63/pg_63_NN_col.xml      Transkribus PAGE XML export
        |
        v  onate_normalize.py
staging/disp63/pg_63_NN_col.xml          Normalised staging file
        |
        |  <- manual review (staging markers, sic/corr, s-larga overrides...)
        |
        v  Step 1 -- onate_page2tei.py
src/disp63/pg_63_NN_col.xml              TEI diplomatic transcript
        |
        v  Step 1.5 -- onate_nlp.py
src/disp63/pg_63_NN_col.xml              + morphological annotation (POS, lemma, MSD)
        |
        v  Step 1.6 -- onate_nlp_corrections.py (optional)
src/disp63/pg_63_NN_col.xml              + manual lemma/pos/msd corrections, if any
        |
        v  Step 1.7 -- onate_lila.py
src/disp63/pg_63_NN_col.xml              + @lemmaRef (LiLa Lemma Bank)
        |
        v  Step 2 -- bibl_enricher.py
bibl/disp63/pg_63_NN_col_bibl.xml        TEI + bibliographic markup
        |
        v  Step 3 -- xmllint --xinclude
output/disp63_bibl_completo.xml          Full assembled XML
        |
        v  Step 3.5 -- onate_sentences.py
output/disp63_bibl_completo.xml          + sentence spans across column/page boundaries
        |
        v  Step 4 -- validation
        |
        v  Step 4.5 -- onate_coords.py (Tesseract, aligned to Transkribus)
coords/disp63/pg_63_NN_col.json + .js
        |
        v  Step 5 -- generate_facs_xsl.py + xsltproc
html/disp63/*.html                       HTML review interfaces
        |
        v  Step 6 -- onate_search_index.py
html/disp63/search_index.js              Concordance index (whole document)
```

### Normalisation

```bash
python3 scripts/onate_normalize.py transkribus/disp63/pg_63_NN_col.xml \
    --out staging/disp63/pg_63_NN_col.xml
```

This cleans up Unicode artefacts from the HTR output and reports suspected
unhyphenated word breaks for manual review. The resulting staging file is then
edited before the pipeline runs.

If the underlying Transkribus PAGE XML is later corrected (re-exported after
fixing a Word-segmentation error, for instance), use onate_staging_merge.py
to bring those changes into an already-edited staging file without discarding
manual annotations:

```bash
python3 scripts/onate_staging_merge.py \
    staging/disp63/pg_63_NN_col.xml \
    transkribus/disp63/pg_63_NN_col.xml \
    --dry-run   # preview changes before applying
```
#### Lines added by hand in Transkribus

A TextLine drawn by hand in the Transkribus editor (typically the last line of
a column, which the layout analysis missed) is exported with a non-standard
id (`l`, `l_1`, ...) instead of `tr_1_tl_N`. Rename it in both the PAGE XML and
the staging file before processing:

```bash
python3 scripts/onate_fix_line_ids.py 52          # both columns of page 52
python3 scripts/onate_fix_line_ids.py 52 der --dry-run
```

#### Staging markers

| Marker | Meaning | TEI output |
|---|---|---|
| `¬` | Word continues on next line (original hyphen present) | `<lb break="no"/>` |
| `~` | Word continues on next line (hyphen missing - compositor error) | `<lb break="no" rend="no-hyphen"/>` |
| `{sic|corr}` | Typographic error with correction | `<choice><sic>...</sic><corr>...</corr></choice>` |
| `{sic|}` | Error with no correction | `<sic>...</sic>` |
| `//` | Sentence boundary | `</s><s>` |
| `##` / `#` | Heading level 1 / 2 (section headings: `##SECTIO III.`) | `<head>` |
| `@ref@` | Bibliographic reference | `<bibl>` candidate |
| `[-palabra]palabra` | Suppress automatic long-s for this occurrence | plain `<w>`, no `<choice>` |
| `[+palabra]palabra` | Force automatic long-s for this occurrence | `<choice><orig>/<reg></choice>` |
| `[=formaDiplomatica]palabraNormalizada` | Force an exact diplomatic form, bypassing the automatic rules | `<choice><orig>forma</orig><reg>normal</reg></choice>` |

### Running the automated pipeline

```bash
# Single column, all steps
./procesar_pagina.sh 37 izq

# Left column only (no assembly -- right column not yet available)
./procesar_pagina.sh 39 izq --only page2tei
./procesar_pagina.sh 39 izq --only nlp
./procesar_pagina.sh 39 izq --only enrich

# Right column -- runs all steps including assembly
./procesar_pagina.sh 39 der

# Reprocess every column found under transkribus/disp63/, in reading order
./procesar_pagina.sh all
```

#### Individual steps

```bash
./procesar_pagina.sh 37 izq --only page2tei
./procesar_pagina.sh 37 izq --only nlp
./procesar_pagina.sh 37 izq --only nlp_corrections
./procesar_pagina.sh 37 izq --only enrich
./procesar_pagina.sh 37 der --only assemble
./procesar_pagina.sh 37 der --only sentences
./procesar_pagina.sh 37 der --only validate
./procesar_pagina.sh 37 izq --only lila
./procesar_pagina.sh 37 der --only coords
./procesar_pagina.sh 37 der --only html
./procesar_pagina.sh 37 der --only search    # rebuilds the concordance index
```

`normalize` (Step 0) is never run by the full pipeline: call it explicitly,
once, to create the staging file of a new column
(`./procesar_pagina.sh 37 izq --only normalize`). It refuses to overwrite an
existing staging file.

When a new page is processed, the left column is run before the right one
exists, so its assembly step fails on the missing XInclude and the run stops
before Step 4.5. Run the left column a second time once the right one is done,
so that its coordinates are generated too.

#### Options

```
--force-bibl    Rebuild <bibl> elements even if already present
--verbose       Show token and abbreviation detail during page2tei
```

---

## Scripts

### `scripts/onate_normalize.py`
Cleans Transkribus PAGE XML output and writes a staging file ready for manual
review. Detects suspected unhyphenated word breaks and reports them as warnings.

### `scripts/onate_staging_merge.py`
Merges a re-exported Transkribus PAGE XML into an already-edited staging file,
preserving manual annotations (long-s overrides, sic/corr, structural marks).
Run with --dry-run first to preview the diff.

### `scripts/onate_tokens.py`
Lexical tables and tokenizer. Contains:
- `LONG_S` -- dictionary mapping normalized forms to diplomatic forms with long-s
- `LONG_S_ROOTS` -- root-based (substring) rules for long-s conversion, covering
  whole word families without enumerating every inflected form
- `ABBREV_WITH_DOT` / `ABBREV_WITH_SEMICOLON` / `ABBREV_EXPAN` /
  `ABBREV_SEMICOLON_EXPAN` -- recognised abbreviations and their expansions
- `ORIG_REG` -- manual orthographic variants (v/u, ae/ae, etc.)
- `AUTHOR_FULL_NAMES` / `AUTHOR_ABBREVS` -- author name recognition for
  bibliographic grouping
- `apply_long_s_to_split()` -- reconstructs the diplomatic form for a word split
  across a line break
- `parse_long_s_overrides()` -- parses the [-word] / [+word] / [=form] staging notation
- `classify_tag()` -- determines whether a token is `<abbr>` or `<orig>`
- `extract_lines()` -- parses the staging file and extracts text lines with metadata

### `scripts/onate_tei.py`
TEI tree builder. Contains:
- `add_w()` -- generates `<w>`, `<choice><orig>/<reg>`, `<choice><abbr>/<expan>`,
  or nested `<choice>` for abbreviations with a long-s variant
- `add_w_lb()` -- generates words split by line break with diplomatic form reconstruction
- `emit_token()` -- dispatches tokens to the appropriate builder function
- `lines_to_tei()` -- converts a list of lines into a <div type="page"> element,
  recording the source column name (izq/der/unica/...) as @col

### `scripts/onate_page2tei.py`
Main entry point for TEI generation. Orchestrates extraction, tokenization, and
TEI tree building for a single column. Handles catchword detection
(--strip-catchword) and cross-column word joining (--join-left). A short last
line is treated as a catchword only if it does not end in punctuation: a line
such as `re.` that completes `vende¬` and closes a sentence is kept as text.

### `scripts/onate_fix_line_ids.py`
Renames hand-added Transkribus TextLines (`l`, `l_1`, ...) to the `tr_1_tl_N`
pattern in the PAGE XML and the staging file at once, numbering on from the
highest existing line. Changes nothing if an id does not occur exactly once in
the staging file.

### `scripts/onate_lila.py`
Links each `<w>` to the LiLa Lemma Bank through `@lemmaRef` (`lila:N` for
lemmas, `lilah:N` for hypolemmas), using a local index
(`cache/lila_index.json`, built once with `onate_lila_index.py`). Unmatched or
ambiguous (lemma, POS) pairs are reported in `lila/pendientes.tsv`; editorial
decisions go in `lila/excepciones.tsv` and apply corpus-wide.

### `scripts/onate_nlp.py`
Morphological annotation. Runs LatinCy (la_core_web_lg) over the `<w>`
elements in the TEI file and adds @lemma, @pos, and @msd attributes in
place. `MANUAL_LEMMA` holds corpus-wide overrides for words LatinCy
consistently mislabels -- currently seeded from AUTHOR_FULL_NAMES (citation
authors always appear in the nominative as the subject of the citing verb) plus
a handful of individually confirmed entries. Use this dictionary only for
words whose grammatical role is essentially invariant wherever they occur; for
words whose case/gender/number genuinely varies by sentence, use
nlp_corrections/ instead (see below).

### `scripts/onate_nlp_report.py`
Read-only diagnostic tool. Prints each sentence of a src/*.xml file
alongside the current lemma/pos/msd of every word, for manual review against
the source text -- the starting point for deciding what to add to
nlp_corrections/.

```bash
python3 scripts/onate_nlp_report.py src/disp63/pg_63_41_izq.xml --min-sent 1 --max-sent 5
```

### `scripts/onate_nlp_corrections.py`
Applies manual lemma/pos/msd corrections on top of an already-annotated
src/*.xml, reading a JSON file scoped to that specific page/column:
nlp_corrections/disp63/pg_63_NN_col.json. Format:

```json
{
  "palabra": "Feature=Val,Feature2=Val2,...",
  "vulgare": "lemma=vulgaris,pos=ADJ,Case=Acc,Gender=Neut,Number=Sing"
}
```

The keys `lemma` and `pos` are reserved and override those fields directly;
any other key is treated as a morphological feature and merged into `@msd`.
If pos is overridden, the old @msd is discarded entirely rather than
merged, since a wrong POS's features don't carry over to the correct one.
Corrections are matched by the normalized (`<reg>`/`<expan>`) form of the word and
applied consistently to every copy inside a `<choice>` (diplomatic and
normalized alike), and the corrected word is flagged `@manual="1"` so the HTML
tooltip can indicate it was reviewed by hand.

This mechanism -- rather than the staging file -- is the right place for
morphological corrections: the staging file's purpose is typographic and
textual fidelity, not linguistic analysis.

### `scripts/onate_bibl.py`
Bibliographic token grouping. Detects sequences of author + work + locator
tokens in the staging file and groups them into `<bibl>` candidates for the
enrichment step. Also implements join_split_words().

### `scripts/bibl_enricher.py`
Bibliographic enrichment. Adds @corresp, <author ref>, `<biblScope>`, and
wraps `<bibl>` elements in <cit xml:id>. Matches against the authority list
in tei_header.xml.

### `scripts/onate_sentences.py`
Cross-column and cross-page sentence segmentation. After assembly, analyses
each pair of consecutive columns and:
- Detects sentences that continue across a column/page boundary
- Adds @part, @xml:id, @next/@prev to the boundary `<s>` elements
- Reconstructs words split at the boundary as `<choice><orig>/<reg>`,
  re-running LatinCy on the reconstructed word for a coherent lemma/pos/msd
- Links both halves with a shared `@wpair` id for synchronized hover highlighting

A word counts as split across columns only if its `<lb break="no"/>` is the
last thing inside the `<w>`. A word completed on the next line of the same
column (`vende<lb break="no"/>re`) is not.

### `scripts/onate_coords.py`
Extracts line and word coordinates from the PAGE XML (word boxes from
Tesseract, aligned to the Transkribus text) into `coords/disp63/pg_63_NN_col.json`,
and writes the same data as `.js` (`window.ONATE_COORDS[...]`). The viewer loads
the `.js` with a `<script>` tag, so the facsimile highlighting works when the
HTML is opened straight from disk. To create the `.js` files for existing JSON
without rerunning Tesseract:

```bash
python3 scripts/onate_coords.py --from-json coords/disp63/*.json
```

### `scripts/onate_search_index.py`
Builds the concordance index from the assembled document
(`output/disp63_bibl_completo.xml`): one entry per word or punctuation mark,
with normalized form, diplomatic form, lemma, POS, MSD, page, column, line, and
the occurrence number of that form within its line. Words split across columns
count once. Written as `html/disp63/search_index.js` (Step 6).

### `scripts/generate_facs_xsl.py`
Generates xslt/onate_tei2html_facs.xsl from the base stylesheet via
<xsl:import>, so template-level changes to the base propagate automatically.
JavaScript is NOT inherited via xsl:import -- only XSLT templates are -- so
any JS changes must be made in both places.

The viewer script also handles links from the concordance: a URL such as
`disp63_facs.html#pg_63_48_izq:2:pretium:0` (column : line : diplomatic form :
occurrence in the line) scrolls to that word, highlights it as on hover, and
draws its box on the facsimile; if the word is not found, the whole line is
marked.

---

## TEI Encoding Decisions

### Orthographic variants (long-s, ae, v/u)
Diplomatic forms are encoded in `<orig>`, normalized forms in `<reg>`:
```xml
<choice>
  <orig><w>disputatio [s larga]</w></orig>
  <reg><w>disputatio</w></reg>
</choice>
```

### Abbreviations
```xml
<choice>
  <abbr><w>cap.</w></abbr>
  <expan><w>capitulo</w></expan>
</choice>
```

### Printer's errors (sic/corr)
Used when the printed original itself is wrong. If the corrected form also
has its own long-s variant, it is nested the same way as abbreviations:
```xml
<choice>
  <sic><w>dignosendum</w></sic>
  <corr>
    <choice>
      <orig><w>dignoscendum [s larga]</w></orig>
      <reg><w>dignoscendum</w></reg>
    </choice>
  </corr>
</choice>
```

### Words split at column/page boundaries
Handled entirely by onate_sentences.py on the fully assembled document,
not by the page2tei/catchword-joining step (which only sees one column at a time):
```xml
<s xml:id="s_2_I" part="I" next="#s_2_F">
  <choice wpair="wp_1"><orig><w>con<lb break="no"/></w></orig>
            <reg><w>consuetudine</w></reg></choice>
</s>
```

---

## Translation & Sense Linking

A separate, optional layer on top of the diplomatic edition: sentence-by-sentence
translation, plus word-sense anchoring to [LiLa: Linking Latin](https://lila-erc.eu/)
for individual terms worth tracking across the corpus. Neither layer touches
src/ or bibl/ -- both are additive and read the already-annotated TEI.

### `translations/disp63/pg_63_NN_col.json`

```json
{
  "sentences": [
    {"n": 1, "es": "Antes de que abordemos la división del precio..."}
  ]
}
```

One entry per sentence, keyed by the same sentence number (`n`) as `<s>`
order in the source column.

### `senses/disp63/pg_63_NN_col.json`

Anchors a specific occurrence of a Latin word to a LexicalConcept in LiLa's
Latin WordNet, and records where that same concept surfaces in the
translation:

```json
{
  "sentence": 1,
  "text": "pretium",
  "occurrence": 1,
  "lemma": "pretium",
  "gloss_en": "price",
  "match_text": "precio",
  "match_occurrence": 2,
  "lila_uri": "https://lila-erc.eu/data/lexicalResources/LatinWordNet/id/LexicalConcept/05171334-n",
  "lila_def": "value measured by what must be given or done or undergone to obtain something",
  "note": "Broad (non-monetary) sense -- what Oñate is defining here."
}
```

- `text` / `occurrence`: identifies the Latin token (occurrence disambiguates
  repeated surface forms within the sentence, 1-indexed).
- `match_text` / `match_occurrence`: same, for the translated sentence --
  the word/phrase that gets highlighted and cross-linked to the Latin token.
- `lila_uri`: found by hand at <https://lila-erc.eu/query/> (a JS app, not
  fetchable programmatically) -- search the lemma, open the LexicalConcept
  matching the intended sense, copy its URI. `null` while still pending.
- `lila_def`: the `skos:definition` shown on that LexicalConcept's own page
  (copy verbatim) -- distinct from `note`, which is editorial commentary.
- `gloss_en`: an English gloss used as the search anchor in LiLa (which
  documents its Latin WordNet in English regardless of the edition's target
  language) -- not necessarily identical to `match_text`.

**Coverage caveat:** LiLa's Latin WordNet ID space is its own -- offsets do
*not* generally coincide with Princeton WordNet's (confirmed empirically:
the same concept can carry two different offsets in each system, and some
Latin lemmas, e.g. *propendeo*, have no Latin WordNet entry at all, only
Lewis & Short). Treat `lila_uri` as the only externally verifiable anchor;
don't infer a Princeton/NLTK offset from it or vice versa.

### `scripts/onate_inject_translation.py`

Generates `html/disp63/disp63_trad.html`. Unlike an early, now-abandoned
approach (`onate_translation_html.py`, kept only as a fallback) that
re-derived transcription markup from the raw TEI, this script extracts the
already-rendered `<span class="tei-s">` elements straight out of an existing
XSLT output (`disp63_facs.html` or `disp63_bibl.html`) and injects the
translation column next to it -- inheriting typography, `sic/corr`
handling, abbreviation rendering, everything, with nothing reimplemented.
It also un-diplomatizes line layout for the translation view specifically
(rejoins hyphenated words, drops `<br>`/line numbers) so the transcription
reads as running prose rather than mirroring the original page breaks.

```bash
python3 scripts/onate_inject_translation.py html/disp63/disp63_facs.html \
    --out html/disp63/disp63_trad.html
```

### `traducir_pagina.sh`

Orchestrates the interactive translation workflow, independent of
`procesar_pagina.sh` (translation is a human-in-the-loop task, not a
deterministic pipeline step):

```bash
./traducir_pagina.sh 34 der siguiente        # next untranslated sentence + lemma/pos/msd table
./traducir_pagina.sh 34 der siguiente --n 5  # a specific sentence instead
./traducir_pagina.sh 34 der guardar 3 "..."  # save/update a translation
./traducir_pagina.sh 34 der html             # regenerate that column's working HTML
./traducir_pagina.sh libro                   # regenerate disp63_trad.html (all columns)
```

Helper scripts: `onate_next_sentence.py` (prints the pending sentence),
`onate_save_translation.py` (writes to translations/), `onate_sense_report.py`
(concordance across all senses/*.json, grouped by lemma, cross-referenced
with each sentence's translation -- `output/disp63_sense_concordance.md`).

---

## HTML Review Interfaces

Four HTML views are generated from the same assembled XML, plus the
concordance:

- `disp63_facs.html` -- the primary interface: two-column text with an
  interactive facsimile panel, syncing word-level highlighting on hover.
- `disp63_bibl.html` -- text only, with bibliographic annotation inline.
- `disp63_simple.html` -- a lighter text-only rendering.
- `disp63_trad.html` -- bilingual view (transcription | translation), built
  by `onate_inject_translation.py` from an already-generated interface
  above. Word-level cross-highlighting on hover, and a synset/LiLa tooltip
  on translated words that have a `senses/` entry.
- `concordancia.html` -- KWIC concordance over `search_index.js`. Simple
  search by form, lemma or morphological features (with `*`/`?` wildcards and
  a POS filter), or token sequences such as
  `[lema=pretium] [pos=NOUN & morf=Case=Gen]`. Comparisons ignore case and
  accents and treat s/ſ, ae/æ, u/v and i/j as equal. Shows lemma/form
  frequencies; each result links to the word in `disp63_facs.html`, and
  links already opened change colour.

Common features:
- Morphological colour-coding by POS tag
- Tooltips on hover showing lemma, POS, morphological features; manually-
  corrected words are flagged
- Ctrl + hover on a citation word shows the full citation instead of lemma/pos
- Sentence/word-pair highlighting across column and facsimile boundaries
- Line numbers matching the PAGE XML source
- Single-column pages render text above/below the facsimile
- Concordancia / Traducción buttons in the header (fixed top-right in the
  facsimile view)

---

## Setup

```bash
git clone https://github.com/afvial/onate.git
cd onate
python3 -m venv venv
source venv/bin/activate
pip install lxml spacy pytesseract
python3 -m spacy download la_core_web_lg

sudo apt install libxml2-utils xsltproc tesseract-ocr
```

### Viewing the HTML output without the full toolchain

The HTML files can be opened directly from disk: word coordinates and the
concordance index are loaded as `.js` files, which browsers allow from
`file://` (unlike `fetch()` of JSON).

```bash
firefox html/disp63/disp63_facs.html
firefox html/disp63/concordancia.html
```

If the facsimile box does not appear on hover, the `.js` coordinates are
missing (the browser console says so); create them with
`python3 scripts/onate_coords.py --from-json coords/disp63/*.json`.
Serving the project over HTTP also works:

```bash
python3 -m http.server 8000
# then open http://localhost:8000/html/disp63/disp63_facs.html
```

---

## Related Projects

- Scholastic Commentaries and Texts Archive (scta.info)
- LombardPress Schema (github.com/lombardpress/lombardpress-schema)
- e-editiones (e-editiones.ch)
