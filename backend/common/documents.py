import io
import zipfile

import docx
import pypdf

PDF_MIME = "application/pdf"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
DOCUMENT_MIMES = (PDF_MIME, DOCX_MIME)
PDF_MAX_PAGES = 300
DOCX_MAX_UNCOMPRESSED = 100 * 1024 * 1024


def extract_pdf(data: bytes, max_pages: int = PDF_MAX_PAGES) -> str:
    reader = pypdf.PdfReader(io.BytesIO(data))
    parts = []
    for page in reader.pages[:max_pages]:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            continue
    return "\n".join(parts)


def extract_docx(data: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            uncompressed = sum(zi.file_size for zi in zf.infolist())
    except zipfile.BadZipFile as exc:
        raise ValueError("Invalid DOCX file") from exc
    if uncompressed > DOCX_MAX_UNCOMPRESSED:
        raise ValueError("Document too large when decompressed")
    doc = docx.Document(io.BytesIO(data))
    return "\n".join(p.text for p in doc.paragraphs if p.text)


def extract_text(data: bytes, mime: str) -> str:
    if mime == PDF_MIME:
        return extract_pdf(data)
    if mime == DOCX_MIME:
        return extract_docx(data)
    return data.decode("utf-8", errors="replace")


def read_text(path: str, mime: str, limit: int) -> str:
    with open(path, "rb") as fh:
        data = fh.read()
    return (extract_text(data, mime) or "")[:limit]


def document_stats(text: str) -> dict:
    words = len(text.split())
    return {"characters": len(text), "words": words}
