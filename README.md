# Oñate · *De contractibus* — Digital Diplomatic Edition

A digital edition of Pedro de Oñate SJ, *De contractibus* (Rome, 1646–1654),
Tractatus XXI: *De emptione et venditione*, Disputatio LXIII.

## Overview

This project produces a TEI XML diplomatic edition from Transkribus HTR output,
with bibliographic enrichment, sentence segmentation, and an HTML review interface.
The pipeline is entirely command-line driven and version-controlled with Git.

**Editor:** Andrés Vial  
**Source:** *De contractibus*, Tomus III, Francesco Cavalli, Rome, 1646–1654  
**Licence:** CC BY 4.0

---

## Toolchain

| Tool | Role |
|---|---|
| [Transkribus](https://transkribus.eu) | HTR transcription → PAGE XML |
| Python 3 + lxml | Pipeline scripts |
| Emacs + nxml-mode | Manual TEI editing and review |
| xsltproc | TEI → HTML transformation |
| Git | Version control |

---

## Repository Structure

```
onate/
├── transkribus/disp63/     PAGE XML exports from Transkribus (one file per column)
├── src/disp63/             TEI diplomatic layer (output of Step 1)
├── bibl/disp63/            TEI bibliographic layer (output of Step 2)
│   └── disp63_bibl.xml     XInclude master file
├── output/                 Assembled XML (output of Step 3)
├── html/disp63/            HTML review interface (output of Step 5)
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

```
Transkribus PAGE XML
        │
        ▼  Step 1 — onate_page2tei.py
src/disp63/pg_63_NN_col.xml          TEI diplomatic transcript
        │
        ▼  Step 2 — bibl_enricher.py
bibl/disp63/pg_63_NN_col_bibl.xml    TEI + bibliographic markup
        │
        ▼  Step 3 — xmllint --xinclude
output/disp63_bibl_completo.xml      Full assembled XML
        │
        ▼  Step 3.5 — onate_sentences.py
output/disp63_bibl_completo.xml      Sentence spans across column boundaries
        │
        ▼  Step 4 — validation
        │
        ▼  Step 5 — xsltproc
html/disp63/disp63_bibl.html         HTML review interface
```

### Running the full pipeline

```bash
./procesar_pagina.sh all
```

### Running individual steps

```bash
# Single column, all steps
./procesar_pagina.sh 37 izq

# Single step only
./procesar_pagina.sh 37 izq --only page2tei
./procesar_pagina.sh 37 izq --only enrich
./procesar_pagina.sh 37 der --only assemble
./procesar_pagina.sh 37 der --only sentences
./procesar_pagina.sh 37 der --only validate
./procesar_pagina.sh 37 der --only html
```

### Options

```
--force-bibl    Rebuild <bibl> elements even if already present
--verbose       Show token and abbreviation detail during page2tei
```

---

## Scripts

### `scripts/onate_tokens.py`
Lexical tables and tokenizer. Contains:
- `LONG_S` — dictionary mapping normalized forms to diplomatic forms with long-s (ſ)
- `LONG_S_ROOTS` — root-based rules for long-s conversion not covered by the dictionary
- `ABBREV_EXPAN` — abbreviation expansion dictionary
- `ORIG_REG` — manual orthographic variants (v/u, ae/æ, etc.)
- `apply_long_s_to_split()` — reconstructs diplomatic form for words split across columns
- `classify_tag()` — determines whether a token is `<abbr>` or `<orig>`
- `extract_lines()` — parses PAGE XML and extracts text lines with metadata

### `scripts/onate_tei.py`
TEI tree builder. Contains:
- `add_w()` — generates `<w>`, `<choice><orig>/<reg>`, `<choice><abbr>/<expan>`, or nested `<choice>` for abbreviations with long-s variant
- `add_w_lb()` — generates words split by line break with diplomatic form reconstruction
- `emit_token()` — dispatches tokens to the appropriate builder function
- `lines_to_tei()` — converts a list of lines into a `<div type="page">` element

### `scripts/onate_bibl.py`
Bibliographic token grouping. Detects sequences of author + work + locator tokens
and groups them into `<bibl>` candidates.

### `scripts/onate_page2tei.py`
Main entry point. Orchestrates extraction, tokenization, and TEI generation for
a single column. Handles catchword detection (`--strip-catchword`) and
cross-column word joining (`--join-left`).

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
```xml
<choice>
  <orig><w>conſue<lb break="no" n="48"/>tudine</w></orig>
  <reg><w>consuetudine</w></reg>
</choice>
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
- **Tooltips** on hover showing `reg` (normalized form) or `expan` (expansion)
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
pip install lxml

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
