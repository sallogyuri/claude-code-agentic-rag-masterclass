import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import MagicMock, patch
import pytest

from services.parsing_service import extract_text, _docling_extract


# ---------------------------------------------------------------------------
# Fast path: txt and md
# ---------------------------------------------------------------------------

def test_txt_passthrough_returns_utf8_decoded_string():
    content = "Hello, plain text world."
    result = extract_text(content.encode("utf-8"), "notes.txt")
    assert result == content


def test_md_passthrough_returns_utf8_decoded_string():
    content = "# Heading\n\nSome markdown content."
    result = extract_text(content.encode("utf-8"), "README.md")
    assert result == content


def test_txt_does_not_invoke_docling():
    """Fast path must never call _docling_extract."""
    with patch("services.parsing_service._docling_extract") as mock_extract:
        extract_text(b"plain text", "file.txt")
    mock_extract.assert_not_called()


# ---------------------------------------------------------------------------
# Docling path: pdf, docx, html
# ---------------------------------------------------------------------------

def test_pdf_routes_to_docling_extract():
    with patch("services.parsing_service._docling_extract", return_value="## PDF Content") as mock:
        result = extract_text(b"%PDF-1.4 fake", "report.pdf")
    mock.assert_called_once_with(b"%PDF-1.4 fake", ".pdf")
    assert result == "## PDF Content"


def test_docx_routes_to_docling_extract():
    with patch("services.parsing_service._docling_extract", return_value="# Word Doc") as mock:
        result = extract_text(b"PK fake docx", "contract.docx")
    mock.assert_called_once_with(b"PK fake docx", ".docx")
    assert result == "# Word Doc"


def test_html_routes_to_docling_extract():
    with patch("services.parsing_service._docling_extract", return_value="## HTML Title") as mock:
        result = extract_text(b"<html><body>hi</body></html>", "page.html")
    mock.assert_called_once_with(b"<html><body>hi</body></html>", ".html")
    assert result == "## HTML Title"


# ---------------------------------------------------------------------------
# Fallback: unknown extension
# ---------------------------------------------------------------------------

def test_unknown_extension_with_valid_utf8_falls_back_to_decode():
    content = "col1,col2\nval1,val2"
    result = extract_text(content.encode("utf-8"), "data.csv")
    assert result == content


def test_unknown_extension_with_binary_raises_value_error():
    binary_bytes = bytes(range(256))
    with pytest.raises(ValueError, match="Unsupported file type '.bin'"):
        extract_text(binary_bytes, "image.bin")


# ---------------------------------------------------------------------------
# _docling_extract: temp file cleanup
# ---------------------------------------------------------------------------

def test_docling_extract_cleans_up_temp_file_on_success():
    """Temp file must be deleted after a successful conversion."""
    import types

    mock_result = MagicMock()
    mock_result.document.export_to_markdown.return_value = "Extracted text"
    mock_converter = MagicMock()
    mock_converter.convert.return_value = mock_result
    mock_converter_cls = MagicMock(return_value=mock_converter)

    fake_converter_module = types.ModuleType("docling.document_converter")
    fake_converter_module.DocumentConverter = mock_converter_cls
    fake_converter_module.PdfFormatOption = MagicMock()

    fake_pipeline_module = types.ModuleType("docling.datamodel.pipeline_options")
    fake_pipeline_module.PdfPipelineOptions = MagicMock()

    fake_base_module = types.ModuleType("docling.datamodel.base_models")
    fake_base_module.InputFormat = MagicMock()

    originals = {k: sys.modules.get(k) for k in (
        "docling.document_converter",
        "docling.datamodel.pipeline_options",
        "docling.datamodel.base_models",
    )}
    sys.modules["docling.document_converter"] = fake_converter_module
    sys.modules["docling.datamodel.pipeline_options"] = fake_pipeline_module
    sys.modules["docling.datamodel.base_models"] = fake_base_module
    try:
        # Capture temp file path via a side-effecting wrapper
        created_paths = []
        import tempfile as _tf
        original_ntf = _tf.NamedTemporaryFile

        def tracking_ntf(*args, **kwargs):
            f = original_ntf(*args, **kwargs)
            created_paths.append(f.name)
            return f

        with patch("tempfile.NamedTemporaryFile", side_effect=tracking_ntf):
            result = _docling_extract(b"fake pdf bytes", ".pdf")

        assert result == "Extracted text"
        for path in created_paths:
            assert not os.path.exists(path), f"Temp file {path} was not cleaned up"
    finally:
        for k, v in originals.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v


def test_docling_extract_cleans_up_temp_file_on_failure():
    """Temp file must be deleted even when Docling raises."""
    import types

    class _FailingConverter:
        def __init__(self, **kwargs):
            pass

        def convert(self, path):
            raise RuntimeError("Conversion failed")

    fake_converter_module = types.ModuleType("docling.document_converter")
    fake_converter_module.DocumentConverter = _FailingConverter
    fake_converter_module.PdfFormatOption = MagicMock()

    fake_pipeline_module = types.ModuleType("docling.datamodel.pipeline_options")
    fake_pipeline_module.PdfPipelineOptions = MagicMock()

    fake_base_module = types.ModuleType("docling.datamodel.base_models")
    fake_base_module.InputFormat = MagicMock()

    originals = {k: sys.modules.get(k) for k in (
        "docling.document_converter",
        "docling.datamodel.pipeline_options",
        "docling.datamodel.base_models",
    )}
    sys.modules["docling.document_converter"] = fake_converter_module
    sys.modules["docling.datamodel.pipeline_options"] = fake_pipeline_module
    sys.modules["docling.datamodel.base_models"] = fake_base_module
    try:
        created_paths = []
        import tempfile as _tf
        original_ntf = _tf.NamedTemporaryFile

        def tracking_ntf(*args, **kwargs):
            f = original_ntf(*args, **kwargs)
            created_paths.append(f.name)
            return f

        with patch("tempfile.NamedTemporaryFile", side_effect=tracking_ntf):
            with pytest.raises(RuntimeError, match="Conversion failed"):
                _docling_extract(b"fake pdf bytes", ".pdf")

        for path in created_paths:
            assert not os.path.exists(path), f"Temp file {path} was not cleaned up"
    finally:
        for k, v in originals.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
