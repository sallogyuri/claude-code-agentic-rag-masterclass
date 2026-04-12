import os
import tempfile

_TEXT_EXTENSIONS = {".txt", ".md"}
_DOCLING_EXTENSIONS = {".pdf", ".docx", ".html"}


def extract_text(file_bytes: bytes, filename: str) -> str:
    ext = _get_extension(filename)
    if ext in _TEXT_EXTENSIONS:
        return file_bytes.decode("utf-8")
    if ext in _DOCLING_EXTENSIONS:
        return _docling_extract(file_bytes, ext)
    try:
        return file_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"Unsupported file type '{ext}' and content is not valid UTF-8.") from exc


def _get_extension(filename: str) -> str:
    _, ext = os.path.splitext(filename)
    return ext.lower()


def _docling_extract(file_bytes: bytes, ext: str) -> str:
    from docling.document_converter import DocumentConverter, PdfFormatOption  # deferred — keeps tests fast
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name
        # File closed before Docling opens it — required on Windows
        pipeline_options = PdfPipelineOptions()
        pipeline_options.document_timeout = 120
        converter = DocumentConverter(
            format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)}
        )
        result = converter.convert(tmp_path)
        return result.document.export_to_markdown()
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
