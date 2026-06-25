# pdf-parser-tool

CLI tool that parses PDFs into structured data using [Docling](https://github.com/docling-project/docling).

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
```

Extract any tables found in the PDF as CSV files:

```bash
./.venv/bin/python parse.py input.pdf --tables-dir ./tables
```

### Options

- `--format, -f` — `json` (full structured document), `markdown`, or `text` (default: `json`)
- `--output, -o` — write to a file instead of stdout
- `--tables-dir` — directory to write extracted tables as `<pdf-name>_table_N.csv`

## Development

```bash
./.venv/bin/pip install -r requirements-dev.txt
./.venv/bin/ruff check .
./.venv/bin/ruff format .
./.venv/bin/pytest
```
