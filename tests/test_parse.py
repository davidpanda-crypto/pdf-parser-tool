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
