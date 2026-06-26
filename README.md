# pdf-parser-tool

CLI tool that parses PDFs into structured data using [Docling](https://github.com/docling-project/docling).
Handles text, tables, embedded pictures, full-page renders, OCR (for scanned
pages), forms/key-value pairs, password-protected files, and document
metadata.

## Setup

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
```

## Usage

```bash
./.venv/bin/python parse.py input.pdf --format json -o output.json
./.venv/bin/python parse.py input.pdf --format markdown
./.venv/bin/python parse.py input.pdf --format text
./.venv/bin/python parse.py input.pdf --format html
./.venv/bin/python parse.py input.pdf --format doctags
```

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

- `--format, -f` — `json` (full structured document), `markdown`, `text`, `html`, or `doctags` (default: `json`)
- `--output, -o` — write the rendered output to a file instead of stdout
- `--tables-dir` — write each table as `<pdf-name>_table_N.csv`
- `--images-dir` — write each embedded picture as `<pdf-name>_picture_N.png`
- `--page-images-dir` — write a full-page render per page as `<pdf-name>_page_N.png`
- `--metadata` — print a JSON summary (page count, table/picture/form counts, file origin) to stderr
- `--password` — password for an encrypted PDF
- `--no-ocr` — disable OCR (on by default, for scanned/image-only pages)
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
