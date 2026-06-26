#!/usr/bin/env python3
"""CLI tool to parse PDFs into structured data using Docling.

Covers every aspect of a PDF: body text, tables (as CSV), embedded pictures
and full page renders (as PNG), OCR for scanned content, password-protected
files, document metadata, and interactive AcroForm field values (read directly
via pypdf, since Docling's layout reconstruction can mangle or disconnect them
from their labels).
"""

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
# pypdf logs every minor PDF non-compliance it repairs (e.g. bad xref entries); not actionable for us.
logging.getLogger("pypdf").setLevel(logging.CRITICAL)

from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend  # noqa: E402
from docling.datamodel.backend_options import PdfBackendOptions  # noqa: E402
from docling.datamodel.base_models import InputFormat  # noqa: E402
from docling.datamodel.pipeline_options import PdfPipelineOptions, TableFormerMode  # noqa: E402
from docling.document_converter import DocumentConverter, PdfFormatOption  # noqa: E402
from docling.exceptions import ConversionError  # noqa: E402
from docling_core.types.doc import DoclingDocument  # noqa: E402
from pydantic import SecretStr  # noqa: E402
from pypdf import PdfReader  # noqa: E402

OutputFormat = str  # one of "json", "markdown", "text", "html", "doctags"
TABLE_MODES = {"fast": TableFormerMode.FAST, "accurate": TableFormerMode.ACCURATE}


def build_converter(
    *,
    ocr: bool,
    table_mode: str,
    ocr_lang: list[str] | None,
    password: str | None,
    want_pictures: bool,
    want_page_images: bool,
    force_full_page_ocr: bool = False,
) -> DocumentConverter:
    """Build a DocumentConverter configured for the requested level of detail.

    force_full_page_ocr OCRs the whole page rather than only the regions the
    layout model flags as needing it. Some scanned pages (typically a single
    full-bleed background image with text directly on top) get zero text
    under regional OCR because the layout model never isolates a text region
    to OCR at all -- this is the fallback for those.
    """
    pipeline_options = PdfPipelineOptions(
        do_ocr=ocr,
        generate_picture_images=want_pictures,
        generate_page_images=want_page_images,
    )
    pipeline_options.table_structure_options.mode = TABLE_MODES[table_mode]
    if ocr_lang:
        pipeline_options.ocr_options.lang = ocr_lang
    pipeline_options.ocr_options.force_full_page_ocr = force_full_page_ocr

    if password:
        # The default DoclingParseV4 backend doesn't propagate the password to
        # its internal page-count check on encrypted PDFs; pypdfium2 does.
        format_option = PdfFormatOption(
            pipeline_options=pipeline_options,
            backend=PyPdfiumDocumentBackend,
            backend_options=PdfBackendOptions(password=SecretStr(password)),
        )
    else:
        format_option = PdfFormatOption(pipeline_options=pipeline_options)
    return DocumentConverter(format_options={InputFormat.PDF: format_option})


def parse_pdf(
    pdf_path: Path,
    converter: DocumentConverter | None = None,
    page_range: tuple[int, int] = (1, sys.maxsize),
) -> DoclingDocument:
    """Convert a PDF (or other Docling-supported file) into a DoclingDocument."""
    converter = converter or DocumentConverter()
    result = converter.convert(str(pdf_path), page_range=page_range)
    return result.document


def extract_form_fields(pdf_path: Path, password: str | None = None) -> dict[str, str]:
    """Read AcroForm field name/value pairs directly from the PDF.

    Docling's OCR/layout pipeline reads what's rendered on the page, which for
    interactive form widgets often disconnects an entered value from its question
    label, leaks raw widget state names (e.g. "/Off") into the text, or fails to
    decode custom comb-field fonts into readable glyphs. The PDF's own AcroForm
    dictionary has the actual, correctly-labeled field values, so we read it
    directly instead of relying on layout reconstruction. Returns {} for PDFs
    with no form fields (or non-PDF inputs, where this isn't applicable).
    """
    try:
        reader = PdfReader(str(pdf_path), password=password)
        fields = reader.get_fields() or {}
    except Exception:
        return {}
    return {name: str(field.get("/V") or "") for name, field in fields.items()}


def _format_form_fields_block(form_fields: dict[str, str], fmt: OutputFormat) -> str:
    if fmt == "html":
        items = "".join(f"<li><b>{name}</b>: {value}</li>" for name, value in form_fields.items())
        return f"<h2>Form Field Values</h2><ul>{items}</ul>"
    lines = ["## Form Field Values", ""]
    lines += [f"- {name}: {value}" for name, value in form_fields.items()]
    return "\n".join(lines)


def render(doc: DoclingDocument, fmt: OutputFormat, form_fields: dict[str, str] | None = None) -> str:
    """Render a parsed document to the requested text format.

    For json, form_fields are merged in under a "form_fields" key. For
    markdown/text/html, they're appended as their own section, since Docling's
    layout reconstruction can't reliably place them (see extract_form_fields).
    """
    form_fields = form_fields or {}
    if fmt == "json":
        data = doc.export_to_dict()
        data["form_fields"] = form_fields
        return json.dumps(data, indent=2, ensure_ascii=False)
    if fmt == "markdown":
        body = doc.export_to_markdown()
    elif fmt == "text":
        body = doc.export_to_text()
    elif fmt == "html":
        body = doc.export_to_html()
    elif fmt == "doctags":
        return doc.export_to_doctags()
    else:
        raise ValueError(f"Unknown format: {fmt}")

    if not form_fields:
        return body
    block = _format_form_fields_block(form_fields, fmt)
    if fmt == "html" and "</body>" in body:
        return body.replace("</body>", block + "</body>")
    return f"{body}\n\n{block}"


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


def extract_pictures(doc: DoclingDocument, pdf_path: Path, images_dir: Path) -> None:
    """Write each embedded picture in the document to its own PNG file in images_dir."""
    if not doc.pictures:
        print("No embedded pictures found in document.")
        return

    images_dir.mkdir(parents=True, exist_ok=True)
    for i, picture in enumerate(doc.pictures):
        image = picture.get_image(doc)
        if image is None:
            continue
        png_path = images_dir / f"{pdf_path.stem}_picture_{i + 1}.png"
        image.save(png_path)
        print(f"Wrote picture {i + 1} to {png_path}")


def extract_page_images(doc: DoclingDocument, pdf_path: Path, page_images_dir: Path) -> None:
    """Write a full-page render for each page in the document to page_images_dir."""
    if not doc.pages:
        print("No page images available.")
        return

    page_images_dir.mkdir(parents=True, exist_ok=True)
    for page_no, page in sorted(doc.pages.items()):
        if page.image is None:
            continue
        png_path = page_images_dir / f"{pdf_path.stem}_page_{page_no}.png"
        page.image.pil_image.save(png_path)
        print(f"Wrote page {page_no} image to {png_path}")


def build_metadata(doc: DoclingDocument, pdf_path: Path, form_fields: dict[str, str] | None = None) -> dict:
    """Summarize document-level metadata: page count, element counts, file origin."""
    return {
        "filename": pdf_path.name,
        "num_pages": doc.num_pages(),
        "num_tables": len(doc.tables),
        "num_pictures": len(doc.pictures),
        "num_form_items": len(doc.form_items),
        "num_key_value_items": len(doc.key_value_items),
        "num_acroform_fields": len(form_fields or {}),
        "origin": doc.origin.model_dump(mode="json") if doc.origin else None,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Parse a PDF into structured data using Docling.")
    parser.add_argument("pdf", type=Path, help="Path to the input PDF file")
    parser.add_argument(
        "--format",
        "-f",
        choices=["json", "markdown", "text", "html", "doctags"],
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
        help="Extract any tables found in the PDF as individual CSV files into this directory",
    )
    parser.add_argument(
        "--images-dir",
        type=Path,
        default=None,
        help="Extract embedded pictures from the PDF as individual PNG files into this directory",
    )
    parser.add_argument(
        "--page-images-dir",
        type=Path,
        default=None,
        help="Render each page of the PDF as a PNG file into this directory",
    )
    parser.add_argument(
        "--metadata",
        action="store_true",
        help="Print document metadata (page count, element counts, origin) as JSON to stderr",
    )
    parser.add_argument(
        "--password",
        default=None,
        help="Password for an encrypted PDF",
    )
    parser.add_argument(
        "--no-ocr",
        action="store_true",
        help="Disable OCR (by default, scanned/image-only pages are OCR'd)",
    )
    parser.add_argument(
        "--force-full-page-ocr",
        action="store_true",
        help=(
            "OCR the entire page rather than only regions the layout model flags. "
            "Slower, but fixes scanned pages that otherwise yield zero text. "
            "(Applied automatically as a fallback if a first pass yields no text at all.)"
        ),
    )
    parser.add_argument(
        "--ocr-lang",
        default=None,
        help="Comma-separated OCR languages (e.g. 'en,fr'); defaults to the OCR engine's default",
    )
    parser.add_argument(
        "--table-mode",
        choices=["fast", "accurate"],
        default="accurate",
        help="Table structure recognition mode (default: accurate)",
    )
    parser.add_argument(
        "--page-range",
        nargs=2,
        type=int,
        metavar=("START", "END"),
        default=None,
        help="1-based inclusive page range to parse, e.g. --page-range 1 5",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    if not args.pdf.exists():
        print(f"Error: file not found: {args.pdf}", file=sys.stderr)
        return 1

    ocr_lang = args.ocr_lang.split(",") if args.ocr_lang else None
    page_range = tuple(args.page_range) if args.page_range else (1, sys.maxsize)
    converter = build_converter(
        ocr=not args.no_ocr,
        table_mode=args.table_mode,
        ocr_lang=ocr_lang,
        password=args.password,
        want_pictures=bool(args.images_dir),
        want_page_images=bool(args.page_images_dir),
        force_full_page_ocr=args.force_full_page_ocr,
    )

    try:
        doc = parse_pdf(args.pdf, converter, page_range)
    except ConversionError as e:
        print(f"Error: could not parse {args.pdf}: {e}", file=sys.stderr)
        return 1

    if not args.no_ocr and not args.force_full_page_ocr and not doc.export_to_text().strip():
        # Some scanned pages (typically one full-bleed background image with text
        # directly on top) yield zero text under regional OCR: the layout model
        # never isolates a region to OCR in the first place. Retry forcing OCR
        # over the whole page before giving up.
        print("No text found; retrying with full-page OCR forced...", file=sys.stderr)
        converter = build_converter(
            ocr=True,
            table_mode=args.table_mode,
            ocr_lang=ocr_lang,
            password=args.password,
            want_pictures=bool(args.images_dir),
            want_page_images=bool(args.page_images_dir),
            force_full_page_ocr=True,
        )
        doc = parse_pdf(args.pdf, converter, page_range)

    form_fields = extract_form_fields(args.pdf, args.password)
    write_text_output(render(doc, args.format, form_fields), args.format, args.output)

    if args.tables_dir is not None:
        extract_tables(doc, args.pdf, args.tables_dir)
    if args.images_dir is not None:
        extract_pictures(doc, args.pdf, args.images_dir)
    if args.page_images_dir is not None:
        extract_page_images(doc, args.pdf, args.page_images_dir)
    if args.metadata:
        print(json.dumps(build_metadata(doc, args.pdf, form_fields), indent=2), file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
