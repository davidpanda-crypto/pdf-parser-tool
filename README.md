# pdf-parser-tool

CLI tool that parses PDFs into structured data using [Docling](https://github.com/docling-project/docling).
Handles text, tables, embedded pictures, full-page renders, OCR (for scanned
pages), password-protected files, document metadata, and interactive form
(AcroForm) field values.

Note on forms: for PDFs with fillable form fields, the entered values are read
directly from the PDF's AcroForm data (via `pypdf`), not reconstructed from
the rendered page layout. Docling's OCR/layout pipeline can disconnect a
filled-in value from its question label, or fail to decode custom comb-field
fonts — reading the AcroForm dictionary directly avoids that. These values
appear under a `form_fields` key in JSON output, or a "Form Field Values"
section appended to markdown/text/html output.

Note on scanned pages: some scanned pages (typically a single full-bleed
background image with text directly on top) yield zero text under normal OCR,
because the layout model never isolates a region to OCR in the first place.
If a first pass comes back with no text at all, the tool automatically
retries once with full-page OCR forced (`--force-full-page-ocr` to do this
from the start instead of waiting for the empty-text fallback).

Note on table structure fidelity: Docling's table-structure model can fail to
detect column boundaries on **borderless** tables (no visible grid lines),
collapsing what's actually a multi-column, multi-row table into a single
column with cells that concatenate many original cells' text together.
Verified against a real report: a 2-column/10-row table came back as 1
column with a 1292-character cell. `--format simple` flags this per table as
`"possibly_under_segmented": true` whenever a single-column table has an
unusually long cell — when you see that flag, cross-check the table against
the source page (`--page-images-dir`) rather than trusting the row data as-is.
This is a real limitation of the underlying model, not something this tool
can fully correct; the flag exists so it's surfaced instead of silently wrong.

## Setup

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
```

## Usage

```bash
./.venv/bin/python parse.py input.pdf --format json -o output.json
./.venv/bin/python parse.py input.pdf --format simple -o output.json
./.venv/bin/python parse.py input.pdf --format markdown
./.venv/bin/python parse.py input.pdf --format text
./.venv/bin/python parse.py input.pdf --format html
./.venv/bin/python parse.py input.pdf --format doctags
```

`json` is Docling's full internal schema — every text/table/picture is a node
with `$ref` pointers, bounding boxes, and provenance. `simple` is a flat view
of the same document: plain `text`, a `headings` list, `tables` as actual row
data (with a `page` number and the under-segmentation flag described below),
`pictures` with captions, and `form_fields` — built for consumers who just
want the content, not Docling's internal bookkeeping.

Extract tables, embedded pictures, and per-page renders:

```bash
./.venv/bin/python parse.py input.pdf --tables-dir ./tables
./.venv/bin/python parse.py input.pdf --images-dir ./pictures
./.venv/bin/python parse.py input.pdf --page-images-dir ./pages
```

Print document metadata (page count, element counts, file origin):

```bash
./.venv/bin/python parse.py input.pdf --metadata
```

Parse a password-protected PDF, a page subrange, or tune OCR/table recognition:

```bash
./.venv/bin/python parse.py input.pdf --password secret123
./.venv/bin/python parse.py input.pdf --page-range 1 5
./.venv/bin/python parse.py input.pdf --no-ocr
./.venv/bin/python parse.py input.pdf --ocr-lang en,fr
./.venv/bin/python parse.py input.pdf --table-mode fast
```

### Options

- `--format, -f` — `json` (full structured document), `simple` (flat, consumer-friendly JSON), `markdown`, `text`, `html`, or `doctags` (default: `json`)
- `--output, -o` — write the rendered output to a file instead of stdout
- `--tables-dir` — write each table as `<pdf-name>_table_N.csv`
- `--images-dir` — write each embedded picture as `<pdf-name>_picture_N.png`
- `--page-images-dir` — write a full-page render per page as `<pdf-name>_page_N.png`
- `--metadata` — print a JSON summary (page count, table/picture/form counts, file origin) to stderr
- `--password` — password for an encrypted PDF
- `--no-ocr` — disable OCR (on by default, for scanned/image-only pages)
- `--force-full-page-ocr` — OCR the whole page instead of only layout-flagged regions (slower; fixes scanned pages that otherwise yield no text — applied automatically as a fallback if a first pass yields none)
- `--ocr-lang` — comma-separated OCR languages, e.g. `en,fr`
- `--table-mode` — `fast` or `accurate` (default: `accurate`) table structure recognition
- `--page-range START END` — 1-based inclusive page range to parse

## Development

```bash
./.venv/bin/pip install -r requirements-dev.txt
./.venv/bin/ruff check .
./.venv/bin/ruff format .
./.venv/bin/pytest
```
