# Oñate · *De contractibus* — Digital Diplomatic Edition

A digital edition of Pedro de Oñate SJ, *De contractibus* (Rome, 1646–1654),
Tractatus XXI: *De emptione et venditione*, Disputatio LXIII.

## Overview

This project produces a TEI XML diplomatic edition from Transkribus HTR output,
with morphological annotation, bibliographic enrichment, sentence segmentation,
and an HTML review interface. The pipeline is entirely command-line driven and
version-controlled with Git.

**Editor:** Andrés Vial  
**Source:** *De contractibus*, Tomus III, Francesco Cavalli, Rome, 1646–1654  
**Licence:** CC BY 4.0

---

## Toolchain

| Tool | Role |
|---|---|
| [Transkribus](https://transkribus.eu) | HTR transcription → PAGE XML |
| Python 3 + lxml | Pipeline scripts |
| [LatinCy](https://huggingface.co/latincy) (`la_core_web_sm`) | Morphological annotation (POS, lemma, MSD) |
| Emacs + nxml-mode | Manual staging review and TEI editing |
| xsltproc | TEI → HTML transformation |
| Git | Version control |

---

## Repository Structure

```
onate/
├── transkribus/disp63/     PAGE XML exports from Transkribus (one file per column)
├── staging/disp63/         Normalised staging files (one file per column, manually reviewed)
├── src/disp63/             TEI diplomatic layer + morphological annotation
├── bibl/disp63/            TEI bibliographic layer
│   └── disp63_bibl.xml     XInclude master file
├── output/                 Assembled XML
├── html/disp63/            HTML review interface
├── xslt/                   XSLT stylesheets
├── scripts/                Python pipeline scripts
├── schema/                 RelaxNG schema (tei_all.rnc)
├── config/                 Project configuration
└── doc/                    Project documentation
```

---

## Pipeline

Each page of the source is a two-column folio. Columns are processed in reading
order (left before right) and identified as `pg_63_NN_izq` (left) and
`pg_63_NN_der` (right).

The pipeline has two phases. The first — normalisation — produces a staging file
that is reviewed and edited manually before the automated steps run. The second
phase is fully automated and driven by `procesar_pagina.sh`.

```
transkribus/disp63/pg_63_NN_col.xml      Transkribus PAGE XML export
        │
        ▼  onate_normalize.py
staging/disp63/pg_63_NN_col.xml          Normalised staging file
        │
        │  ← manual review (staging markers, sic/corr, etc.)
        │
        ▼  Step 1 — onate_page2tei.py
src/disp63/pg_63_NN_col.xml              TEI diplomatic transcript
        │
        ▼  Step 1.5 — onate_nlp.py
src/disp63/pg_63_NN_col.xml              + morphological annotation (POS, lemma, MSD)
        │
        ▼  Step 2 — bibl_enricher.py
bibl/disp63/pg_63_NN_col_bibl.xml        TEI + bibliographic markup
        │
        ▼  Step 3 — xmllint --xinclude
output/disp63_bibl_completo.xml          Full assembled XML
        │
        ▼  Step 3.5 — onate_sentences.py
output/disp63_bibl_completo.xml          + sentence spans across column boundaries
        │
        ▼  Step 4 — validation
        │
        ▼  Step 5 — xsltproc
html/disp63/disp63_bibl.html             HTML review interface
```

### Normalisation

```bash
python3 scripts/onate_normalize.py transkribus/disp63/pg_63_NN_col.xml \
    --out staging/disp63/pg_63_NN_col.xml
```

This cleans up Unicode artefacts from the HTR output and reports suspected
unhy­phen­ated word breaks for manual review. The resulting staging file is then
edited before the pipeline runs.

#### Staging markers

| Marker | Meaning | TEI output |
|---|---|---|
| `¬` | Word continues on next line (original hyphen present) | `<lb break="no"/>` |
| `~` | Word continues on next line (hyphen missing — compositor error) | `<lb break="no" rend="no-hyphen"/>` |
| `{sic\|corr}` | Typographic error with correction | `<choice><sic>…</sic><corr>…</corr></choice>` |
| `{sic\|}` | Error with no correction | `<sic>…</sic>` |
| `//` | Sentence boundary | `</s><s>` |
| `##` / `#` | Heading level 1 / 2 | `<head>` |
| `@ref@` | Bibliographic reference | `<bibl>` candidate |

### Running the automated pipeline

```bash
# Single column, all steps
./procesar_pagina.sh 37 izq

# Left column only (no assembly — right column not yet available)
./procesar_pagina.sh 39 izq --only page2tei
./procesar_pagina.sh 39 izq --only nlp
./procesar_pagina.sh 39 izq --only enrich

# Right column — runs all steps including assembly
./procesar_pagina.sh 39 der
```

#### Individual steps

```bash
./procesar_pagina.sh 37 izq --only page2tei
./procesar_pagina.sh 37 izq --only nlp
./procesar_pagina.sh 37 izq --only enrich
./procesar_pagina.sh 37 der --only assemble
./procesar_pagina.sh 37 der --only sentences
./procesar_pagina.sh 37 der --only validate
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

### `scripts/onate_tokens.py`
Lexical tables and tokenizer. Contains:
- `LONG_S` — dictionary mapping normalized forms to diplomatic forms with long-s (ſ)
- `LONG_S_ROOTS` — root-based rules for long-s conversion not covered by the dictionary
- `ABBREV_EXPAN` — abbreviation expansion dictionary
- `ORIG_REG` — manual orthographic variants (v/u, ae/æ, etc.)
- `apply_long_s_to_split()` — reconstructs diplomatic form for words split across lines
- `classify_tag()` — determines whether a token is `<abbr>` or `<orig>`
- `extract_lines()` — parses the staging file and extracts text lines with metadata

### `scripts/onate_tei.py`
TEI tree builder. Contains:
- `add_w()` — generates `<w>`, `<choice><orig>/<reg>`, `<choice><abbr>/<expan>`, or nested `<choice>` for abbreviations with long-s variant
- `add_w_lb()` — generates words split by line break with diplomatic form reconstruction
- `emit_token()` — dispatches tokens to the appropriate builder function
- `lines_to_tei()` — converts a list of lines into a `<div type="page">` element

### `scripts/onate_page2tei.py`
Main entry point for TEI generation. Orchestrates extraction, tokenization, and
TEI tree building for a single column. Handles catchword detection
(`--strip-catchword`) and cross-column word joining (`--join-left`).

### `scripts/onate_nlp.py`
Morphological annotation. Runs LatinCy (`la_core_web_sm`) over the `<w>`
elements in the TEI file and adds `@lemma`, `@pos`, and `@msd` attributes
in place.

### `scripts/onate_bibl.py`
Bibliographic token grouping. Detects sequences of author + work + locator
tokens in the staging file and groups them into `<bibl>` candidates for the
enrichment step.

### `scripts/bibl_enricher.py`
Bibliographic enrichment. Adds `@corresp`, `<author ref>`, `<biblScope>`, and
wraps `<bibl>` elements in `<cit xml:id>`. Matches against the authority list
in `tei_header.xml`.

### `scripts/onate_sentences.py`
Cross-column sentence segmentation. After assembly, analyses each pair of
consecutive columns and:
- Detects sentences that continue across column boundaries
- Adds `@part`, `@xml:id`, `@next`/`@prev` to the boundary `<s>` elements
- Reconstructs words split at column boundaries as `<choice><orig>/<reg>`
  with long-s form in `<orig>` and full normalized form in `<reg>`

---

## TEI Encoding Decisions

### Orthographic variants (long-s, æ, v/u)
Diplomatic forms are encoded in `<orig>`, normalized forms in `<reg>`:
```xml
<choice>
  <orig><w>diſputatio</w></orig>
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

### Abbreviations with long-s (nested choice)
When an abbreviation also has a long-s variant, the diplomatic and modern
abbreviated forms are encoded in an inner `<choice>`:
```xml
<choice>
  <abbr>
    <choice>
      <orig><w>diſput.</w></orig>
      <reg><w>disput.</w></reg>
    </choice>
  </abbr>
  <expan><w>disputatio</w></expan>
</choice>
```

### Words split at line boundaries
The `~` staging marker indicates a compositor error (break without hyphen);
`¬` indicates an original hyphen. Both produce `<lb break="no"/>`, but `~`
additionally carries `rend="no-hyphen"`:

```xml
<!-- ¬ — original hyphen -->
<w>conſue<lb break="no" n="48"/>tudine</w>

<!-- ~ — missing hyphen (compositor error) -->
<w>pla<lb break="no" rend="no-hyphen" n="38"/>num</w>
```

### Words split at column boundaries
```xml
<!-- end of left column -->
<s xml:id="s_2_I" part="I" next="#s_2_F">
  …<choice><orig><w>con<lb break="no"/></w></orig>
            <reg><w>consuetudine</w></reg></choice>
</s>

<!-- start of right column -->
<s xml:id="s_2_F" part="F" prev="#s_2_I">
  <choice><orig><w>ſuetudine</w></orig>
           <reg><w>consuetudine</w></reg></choice>…
</s>
```

### Bibliographic citations
```xml
<cit xml:id="cit_p35_der_Aug_CivDei_1">
  <bibl corresp="#bib_Aug_CivDei" cert="high">
    <author ref="#pers_Augustinus">
      <choice><abbr><w>Aug.</w></abbr><expan><w>Augustinus</w></expan></choice>
    </author>
  </bibl>
</cit>
```

---

## HTML Review Interface

The HTML output (`html/disp63/disp63_bibl.html`) displays the text in two
columns per page with:
- **Morphological colour-coding** by POS tag (VERB, NOUN, ADJ, etc.)
- **Tooltips** on hover showing lemma, POS, morphological features, and
  normalized or expanded form
- **Sentence highlighting**: hovering over a sentence fragment that continues
  in the adjacent column highlights both fragments simultaneously
- **Line numbers** matching the PAGE XML source

---

## Setup

```bash
# Clone and create virtual environment
git clone https://github.com/afvial/onate.git
cd onate
python3 -m venv venv
source venv/bin/activate
pip install lxml spacy
python3 -m spacy download la_core_web_sm

# System dependencies (Debian/Ubuntu)
sudo apt install libxml2-utils xsltproc
```

---

## Related Projects

- [Scholastic Commentaries and Texts Archive](https://scta.info) — TEI encoding
  of scholastic texts with shared authority files for authors and works
- [LombardPress Schema](https://github.com/lombardpress/lombardpress-schema) —
  TEI customisation for scholastic commentaries
- [e-editiones](https://e-editiones.ch) — digital editions in TEI with
  open-source infrastructure
