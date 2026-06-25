#!/usr/bin/env python3
"""CLI tool to parse PDFs into structured data using Docling."""

from __future__ import annotations

import argparse
import json
import logging
import sys
import warnings
from pathlib import Path

# Suppress the LibreSSL/urllib3 compatibility warning noise on macOS system Python.
warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL")
# Docling logs full tracebacks on conversion failure; we surface a clean message instead.
logging.getLogger("docling").setLevel(logging.CRITICAL)
# docling_core.export_to_text() internally triggers its own bogus deprecation warning.
logging.getLogger("docling_core").setLevel(logging.CRITICAL)

from docling.document_converter import DocumentConverter  # noqa: E402
from docling.exceptions import ConversionError  # noqa: E402
from docling_core.types.doc import DoclingDocument  # noqa: E402

OutputFormat = str  # one of "json", "markdown", "text"


def parse_pdf(pdf_path: Path) -> DoclingDocument:
    """Convert a PDF (or other Docling-supported file) into a DoclingDocument."""
    converter = DocumentConverter()
    result = converter.convert(str(pdf_path))
    return result.document


def render(doc: DoclingDocument, fmt: OutputFormat) -> str:
    """Render a parsed document to the requested text format."""
    if fmt == "json":
        return json.dumps(doc.export_to_dict(), indent=2, ensure_ascii=False)
    if fmt == "markdown":
        return doc.export_to_markdown()
    if fmt == "text":
        return doc.export_to_text()
    raise ValueError(f"Unknown format: {fmt}")


def write_text_output(text: str, fmt: OutputFormat, output: Path | None) -> None:
    """Write rendered text to a file, or print it to stdout if no path is given."""
    if output is not None:
        output.write_text(text, encoding="utf-8")
        print(f"Wrote {fmt} output to {output}")
    else:
        print(text)


def extract_tables(doc: DoclingDocument, pdf_path: Path, tables_dir: Path) -> None:
    """Write each table found in the document to its own CSV file in tables_dir."""
    if not doc.tables:
        print("No tables found in document.")
        return

    tables_dir.mkdir(parents=True, exist_ok=True)
    for i, table in enumerate(doc.tables):
        df = table.export_to_dataframe()
        csv_path = tables_dir / f"{pdf_path.stem}_table_{i + 1}.csv"
        df.to_csv(csv_path, index=False)
        print(f"Wrote table {i + 1} ({df.shape[0]}x{df.shape[1]}) to {csv_path}")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Parse a PDF into structured data using Docling.")
    parser.add_argument("pdf", type=Path, help="Path to the input PDF file")
    parser.add_argument(
        "--format",
        "-f",
        choices=["json", "markdown", "text"],
        default="json",
        help="Output format for the full document (default: json)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Write output to this file instead of stdout",
    )
    parser.add_argument(
        "--tables-dir",
        type=Path,
        default=None,
        help="If set, extract any tables found in the PDF as individual CSV files into this directory",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    if not args.pdf.exists():
        print(f"Error: file not found: {args.pdf}", file=sys.stderr)
        return 1

    try:
        doc = parse_pdf(args.pdf)
    except ConversionError as e:
        print(f"Error: could not parse {args.pdf}: {e}", file=sys.stderr)
        return 1

    write_text_output(render(doc, args.format), args.format, args.output)

    if args.tables_dir is not None:
        extract_tables(doc, args.pdf, args.tables_dir)

    return 0


if __name__ == "__main__":
    sys.exit(main())
