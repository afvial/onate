# Onate - De contractibus - Digital Diplomatic Edition

A digital edition of Pedro de Onate SJ, De contractibus (Rome, 1646-1654),
Tractatus XXI: De emptione et venditione, Disputatio LXIII.

## Overview

This project produces a TEI XML diplomatic edition from Transkribus HTR output,
with morphological annotation, bibliographic enrichment, sentence segmentation,
and an HTML review interface with an interactive facsimile viewer. The pipeline
is entirely command-line driven and version-controlled with Git.

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
  output/                 Assembled XML
  coords/disp63/          Per-word bounding boxes (Tesseract, aligned to Transkribus)
  facsimiles/disp63/      Page images used by the interactive facsimile viewer
  html/disp63/            HTML review interfaces (three variants, see below)
  xslt/                   XSLT stylesheets
  scripts/                Python pipeline scripts
  doc/                    Project documentation and historical reference files
  .state/                 Pipeline-internal state (catchwords between columns); safe to delete
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
        v  Step 4.5 -- coordinate extraction (Tesseract, aligned to Transkribus)
coords/disp63/pg_63_NN_col.json
        |
        v  Step 5 -- xsltproc
html/disp63/*.html                       HTML review interfaces
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
#### Staging markers

| Marker | Meaning | TEI output |
|---|---|---|
| `¬` | Word continues on next line (original hyphen present) | `<lb break="no"/>` |
| `~` | Word continues on next line (hyphen missing - compositor error) | `<lb break="no" rend="no-hyphen"/>` |
| `{sic|corr}` | Typographic error with correction | `<choice><sic>...</sic><corr>...</corr></choice>` |
| `{sic|}` | Error with no correction | `<sic>...</sic>` |
| `//` | Sentence boundary | `</s><s>` |
| `##` / `#` | Heading level 1 / 2 | `<head>` |
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
./procesar_pagina.sh 37 der --only coords
./procesar_pagina.sh 37 der --only html
```

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
(--strip-catchword) and cross-column word joining (--join-left).

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

### `scripts/generate_facs_xsl.py`
Generates xslt/onate_tei2html_facs.xsl from the base stylesheet via
<xsl:import>, so template-level changes to the base propagate automatically.
JavaScript is NOT inherited via xsl:import -- only XSLT templates are -- so
any JS changes must be made in both places.

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

## HTML Review Interfaces

Three HTML variants are generated per run, all from the same assembled XML:

- `disp63_facs.html` -- the primary interface: two-column text with an
  interactive facsimile panel, syncing word-level highlighting on hover.
- `disp63_bibl.html` -- text only, with bibliographic annotation inline.
- `disp63_simple.html` -- a lighter text-only rendering.

Common features:
- Morphological colour-coding by POS tag
- Tooltips on hover showing lemma, POS, morphological features; manually-
  corrected words are flagged
- Ctrl + hover on a citation word shows the full citation instead of lemma/pos
- Sentence/word-pair highlighting across column and facsimile boundaries
- Line numbers matching the PAGE XML source
- Single-column pages render text above/below the facsimile

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

The generated HTML files load facsimile images and word coordinates
dynamically via JavaScript, so they must be served over HTTP:

```bash
python3 -m http.server 8000
# then open http://localhost:8000/html/disp63/disp63_facs.html
```

---

## Related Projects

- Scholastic Commentaries and Texts Archive (scta.info)
- LombardPress Schema (github.com/lombardpress/lombardpress-schema)
- e-editiones (e-editiones.ch)
