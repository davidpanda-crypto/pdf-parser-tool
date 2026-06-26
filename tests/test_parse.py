from __future__ import annotations

import json
from pathlib import Path

import pytest

import parse


def test_parse_pdf_returns_document(sample_pdf: Path):
    doc = parse.parse_pdf(sample_pdf)
    assert "Hello World" in doc.export_to_text()


def test_render_text(sample_pdf: Path):
    doc = parse.parse_pdf(sample_pdf)
    assert "Hello World" in parse.render(doc, "text")


def test_render_markdown(sample_pdf: Path):
    doc = parse.parse_pdf(sample_pdf)
    assert "Hello World" in parse.render(doc, "markdown")


def test_render_json_is_valid_and_structured(sample_pdf: Path):
    doc = parse.parse_pdf(sample_pdf)
    data = json.loads(parse.render(doc, "json"))
    assert "texts" in data
    assert any("Hello World" in t.get("text", "") for t in data["texts"])


def test_render_html(sample_pdf: Path):
    doc = parse.parse_pdf(sample_pdf)
    html = parse.render(doc, "html")
    assert "<html>" in html
    assert "Hello World" in html


def test_render_doctags(sample_pdf: Path):
    doc = parse.parse_pdf(sample_pdf)
    assert "<doctag>" in parse.render(doc, "doctags")


def test_render_rejects_unknown_format(sample_pdf: Path):
    doc = parse.parse_pdf(sample_pdf)
    with pytest.raises(ValueError):
        parse.render(doc, "yaml")


def test_extract_tables_with_no_tables_prints_message(sample_pdf: Path, tmp_path: Path, capsys):
    doc = parse.parse_pdf(sample_pdf)
    tables_dir = tmp_path / "tables"
    parse.extract_tables(doc, sample_pdf, tables_dir)
    assert "No tables found" in capsys.readouterr().out
    assert not tables_dir.exists()


def test_extract_pictures_with_no_pictures_prints_message(sample_pdf: Path, tmp_path: Path, capsys):
    doc = parse.parse_pdf(sample_pdf)
    images_dir = tmp_path / "pictures"
    parse.extract_pictures(doc, sample_pdf, images_dir)
    assert "No embedded pictures found" in capsys.readouterr().out
    assert not images_dir.exists()


def test_build_metadata_reports_counts(sample_pdf: Path):
    doc = parse.parse_pdf(sample_pdf)
    meta = parse.build_metadata(doc, sample_pdf)
    assert meta["filename"] == sample_pdf.name
    assert meta["num_pages"] == 1
    assert meta["num_tables"] == 0
    assert meta["num_pictures"] == 0
    assert meta["num_acroform_fields"] == 0
    assert meta["origin"]["mimetype"] == "application/pdf"


def test_extract_form_fields_on_plain_pdf_returns_empty(sample_pdf: Path):
    assert parse.extract_form_fields(sample_pdf) == {}


def test_extract_form_fields_reads_acroform_values(form_pdf: Path):
    assert parse.extract_form_fields(form_pdf) == {"Name": "Jane Doe"}


def test_render_json_merges_form_fields(form_pdf: Path):
    doc = parse.parse_pdf(form_pdf)
    form_fields = parse.extract_form_fields(form_pdf)
    data = json.loads(parse.render(doc, "json", form_fields))
    assert data["form_fields"] == {"Name": "Jane Doe"}


def test_render_markdown_appends_form_fields_section(form_pdf: Path):
    doc = parse.parse_pdf(form_pdf)
    form_fields = parse.extract_form_fields(form_pdf)
    markdown = parse.render(doc, "markdown", form_fields)
    assert "## Form Field Values" in markdown
    assert "- Name: Jane Doe" in markdown


def test_render_html_inserts_form_fields_before_closing_body(form_pdf: Path):
    doc = parse.parse_pdf(form_pdf)
    form_fields = parse.extract_form_fields(form_pdf)
    html = parse.render(doc, "html", form_fields)
    assert "<h2>Form Field Values</h2>" in html
    assert html.index("<h2>Form Field Values</h2>") < html.index("</body>")


def test_render_without_form_fields_is_unchanged(sample_pdf: Path):
    doc = parse.parse_pdf(sample_pdf)
    assert "Form Field Values" not in parse.render(doc, "markdown", {})


def test_build_metadata_reports_acroform_field_count(form_pdf: Path):
    doc = parse.parse_pdf(form_pdf)
    form_fields = parse.extract_form_fields(form_pdf)
    meta = parse.build_metadata(doc, form_pdf, form_fields)
    assert meta["num_acroform_fields"] == 1


def test_main_includes_form_fields_in_json_output(form_pdf: Path, tmp_path: Path):
    out_path = tmp_path / "out.json"
    exit_code = parse.main([str(form_pdf), "-f", "json", "-o", str(out_path)])
    assert exit_code == 0
    data = json.loads(out_path.read_text())
    assert data["form_fields"] == {"Name": "Jane Doe"}


def test_build_converter_uses_pypdfium_backend_when_password_given():
    converter = parse.build_converter(
        ocr=True,
        table_mode="accurate",
        ocr_lang=None,
        password="secret",
        want_pictures=False,
        want_page_images=False,
    )
    format_option = converter.format_to_options[parse.InputFormat.PDF]
    assert format_option.backend is parse.PyPdfiumDocumentBackend
    assert format_option.backend_options.password.get_secret_value() == "secret"


def test_build_converter_uses_default_backend_without_password():
    converter = parse.build_converter(
        ocr=True, table_mode="fast", ocr_lang=None, password=None, want_pictures=False, want_page_images=False
    )
    format_option = converter.format_to_options[parse.InputFormat.PDF]
    assert format_option.backend is not parse.PyPdfiumDocumentBackend


def test_main_missing_file_returns_1(tmp_path: Path, capsys):
    exit_code = parse.main([str(tmp_path / "does-not-exist.pdf")])
    assert exit_code == 1
    assert "not found" in capsys.readouterr().err


def test_main_invalid_pdf_returns_1(tmp_path: Path, capsys):
    bad_pdf = tmp_path / "bad.pdf"
    bad_pdf.write_text("this is not a pdf")
    exit_code = parse.main([str(bad_pdf)])
    assert exit_code == 1
    assert "could not parse" in capsys.readouterr().err


def test_main_writes_output_file(sample_pdf: Path, tmp_path: Path):
    out_path = tmp_path / "out.txt"
    exit_code = parse.main([str(sample_pdf), "-f", "text", "-o", str(out_path)])
    assert exit_code == 0
    assert "Hello World" in out_path.read_text()


def test_main_metadata_flag_prints_json_to_stderr(sample_pdf: Path, tmp_path: Path, capsys):
    out_path = tmp_path / "out.txt"
    exit_code = parse.main([str(sample_pdf), "-f", "text", "-o", str(out_path), "--metadata"])
    assert exit_code == 0
    meta = json.loads(capsys.readouterr().err)
    assert meta["num_pages"] == 1


def test_main_page_range_restricts_pages(sample_pdf: Path, tmp_path: Path, capsys):
    out_path = tmp_path / "out.txt"
    exit_code = parse.main(
        [str(sample_pdf), "-f", "text", "-o", str(out_path), "--page-range", "1", "1", "--metadata"]
    )
    assert exit_code == 0
    meta = json.loads(capsys.readouterr().err)
    assert meta["num_pages"] == 1
