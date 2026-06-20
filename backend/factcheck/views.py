import io
import logging
import zipfile

import docx
import pypdf
import requests as http_requests
import trafilatura
from django.core.cache import cache
from django.http import HttpResponse
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from common.url_safety import UnsafeUrlError, safe_get
from users.permissions import IsVerifiedUser

from .pdf import render_factcheck_pdf
from .tasks import run_factcheck

logger = logging.getLogger(__name__)

DOC_MAX_BYTES = 10 * 1024 * 1024
URL_FETCH_MAX_BYTES = 1024 * 1024
DOCX_MAX_UNCOMPRESSED = 100 * 1024 * 1024
PDF_MAX_PAGES = 300


class FactCheckView(APIView):
    permission_classes = [IsVerifiedUser]

    def post(self, request):
        text = request.data.get("text", "").strip()
        if not text:
            return Response({"error": "text is required"}, status=status.HTTP_400_BAD_REQUEST)
        if len(text) > 10000:
            return Response({"error": "text too long (max 10000 chars)"}, status=status.HTTP_400_BAD_REQUEST)
        task = run_factcheck.delay(text)
        return Response({"task_id": task.id}, status=status.HTTP_202_ACCEPTED)


class FactCheckStatusView(APIView):
    permission_classes = [IsVerifiedUser]

    def get(self, request, task_id):
        payload = cache.get(f"fc:{task_id}")
        if payload is None:
            return Response({"stage": "pending", "progress": 0})
        return Response(payload)


class FactCheckExportView(APIView):
    permission_classes = [IsVerifiedUser]

    def post(self, request):
        result = request.data.get("result")
        text = request.data.get("text", "")
        if not isinstance(result, dict):
            return Response({"error": "result required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            pdf_bytes = render_factcheck_pdf(result, text)
        except Exception:
            logger.exception("PDF render failed")
            return Response({"error": "PDF generation failed"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return HttpResponse(
            pdf_bytes,
            content_type="application/pdf",
            headers={"Content-Disposition": 'attachment; filename="factcheck.pdf"'},
        )


class FactCheckFetchUrlView(APIView):
    permission_classes = [IsVerifiedUser]

    def post(self, request):
        url = (request.data.get("url") or "").strip()
        try:
            resp = safe_get(url, timeout=10, headers={"User-Agent": "ProofLayer/1.0"})
            resp.raise_for_status()
            content_type = (resp.headers.get("Content-Type") or "").lower()
            if "html" not in content_type and "text" not in content_type:
                return Response(
                    {"error": "URL must return an HTML page"},
                    status=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                )
            buf = bytearray()
            for chunk in resp.iter_content(chunk_size=16384):
                if not chunk:
                    continue
                buf.extend(chunk)
                if len(buf) >= URL_FETCH_MAX_BYTES:
                    break
            raw = bytes(buf)
        except UnsafeUrlError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except http_requests.RequestException as exc:
            logger.warning("URL fetch failed for %s: %s", url, exc)
            return Response(
                {"error": "Could not fetch URL"}, status=status.HTTP_502_BAD_GATEWAY
            )

        decoded = raw.decode("utf-8", errors="ignore")
        try:
            extracted = trafilatura.extract(decoded) or ""
        except Exception as exc:
            logger.warning("Trafilatura extract failed: %s", exc)
            extracted = ""
        title = ""
        try:
            meta = trafilatura.extract_metadata(decoded)
            if meta and getattr(meta, "title", None):
                title = meta.title or ""
        except Exception:
            title = ""

        text = (extracted or "").strip()[:10000]
        if not text:
            return Response(
                {"error": "Could not extract article text"},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        return Response({"text": text, "title": title})


class FactCheckExtractDocView(APIView):
    permission_classes = [IsVerifiedUser]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        f = request.FILES.get("file")
        if not f:
            return Response({"error": "file required"}, status=status.HTTP_400_BAD_REQUEST)
        if f.size > DOC_MAX_BYTES:
            return Response(
                {"error": "file too large (max 10 MB)"},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )
        data = f.read()
        name = (f.name or "").lower()
        mime = (f.content_type or "").lower()
        try:
            if "pdf" in mime or name.endswith(".pdf"):
                text = _extract_pdf(data)
            elif "word" in mime or "officedocument" in mime or name.endswith(".docx"):
                text = _extract_docx(data)
            else:
                return Response(
                    {"error": "unsupported format (PDF/DOCX only)"},
                    status=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                )
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        except Exception:
            logger.exception("Doc extract failed")
            return Response(
                {"error": "Could not read document"},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        text = (text or "").strip()[:10000]
        if not text:
            return Response(
                {"error": "No text found in document"},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        return Response({"text": text})


def _extract_pdf(data: bytes) -> str:
    reader = pypdf.PdfReader(io.BytesIO(data))
    parts = []
    for page in reader.pages[:PDF_MAX_PAGES]:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            continue
    return "\n".join(parts)


def _extract_docx(data: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            uncompressed = sum(zi.file_size for zi in zf.infolist())
    except zipfile.BadZipFile as exc:
        raise ValueError("Invalid DOCX file") from exc
    if uncompressed > DOCX_MAX_UNCOMPRESSED:
        raise ValueError("Document too large when decompressed")
    doc = docx.Document(io.BytesIO(data))
    return "\n".join(p.text for p in doc.paragraphs if p.text)
