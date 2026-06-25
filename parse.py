#!/usr/bin/env python3
"""CLI tool to parse PDFs into structured data using Docling."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from docling.document_converter import DocumentConverter


def parse_pdf(pdf_path: Path) -> "DoclingDocument":
    converter = DocumentConverter()
    result = converter.convert(str(pdf_path))
    return result.document


def write_output(doc, pdf_path: Path, fmt: str, output: Path | None, tables_dir: Path | None):
    if fmt == "json":
        text = json.dumps(doc.export_to_dict(), indent=2, ensure_ascii=False)
    elif fmt == "markdown":
        text = doc.export_to_markdown()
    elif fmt == "text":
        text = doc.export_to_text()
    else:
        raise ValueError(f"Unknown format: {fmt}")

    if output:
        output.write_text(text, encoding="utf-8")
        print(f"Wrote {fmt} output to {output}")
    else:
        print(text)

    if tables_dir is not None:
        if not doc.tables:
            print("No tables found in document.")
        else:
            tables_dir.mkdir(parents=True, exist_ok=True)
            for i, table in enumerate(doc.tables):
                df = table.export_to_dataframe()
                csv_path = tables_dir / f"{pdf_path.stem}_table_{i + 1}.csv"
                df.to_csv(csv_path, index=False)
                print(f"Wrote table {i + 1} ({df.shape[0]}x{df.shape[1]}) to {csv_path}")


def main():
    parser = argparse.ArgumentParser(description="Parse a PDF into structured data using Docling.")
    parser.add_argument("pdf", type=Path, help="Path to the input PDF file")
    parser.add_argument(
        "--format", "-f", choices=["json", "markdown", "text"], default="json",
        help="Output format for the full document (default: json)",
    )
    parser.add_argument("--output", "-o", type=Path, default=None, help="Write output to this file instead of stdout")
    parser.add_argument(
        "--tables-dir", type=Path, default=None,
        help="If set, extract any tables found in the PDF as individual CSV files into this directory",
    )
    args = parser.parse_args()

    if not args.pdf.exists():
        print(f"Error: file not found: {args.pdf}", file=sys.stderr)
        sys.exit(1)

    doc = parse_pdf(args.pdf)
    write_output(doc, args.pdf, args.format, args.output, args.tables_dir)


if __name__ == "__main__":
    main()
