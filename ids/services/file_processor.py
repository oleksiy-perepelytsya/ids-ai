"""File text extraction and chunking for vector embedding"""

import io
import re
from typing import List
from urllib.parse import urlparse, unquote, parse_qs

SUPPORTED_TEXT_EXTENSIONS = {
    ".txt", ".md", ".py", ".js", ".ts", ".jsx", ".tsx",
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg",
    ".html", ".css", ".sh", ".bash", ".sql", ".xml",
    ".csv", ".rst", ".env", ".java", ".go", ".rs",
    ".cpp", ".c", ".h", ".cs", ".rb", ".php",
}


def _detect_google_url(url: str) -> tuple[str, str] | None:
    """
    Detect Google Drive / Docs / Sheets / Slides share links and transform them
    into direct download URLs.

    Returns (download_url, fallback_filename) or None if not a Google URL.
    """
    # Google Drive file share: drive.google.com/file/d/FILE_ID/...
    m = re.match(r'https?://drive\.google\.com/file/d/([^/?]+)', url)
    if m:
        file_id = m.group(1)
        return (
            f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t",
            "",  # Google sets Content-Disposition with real filename
        )

    # Google Drive open: drive.google.com/open?id=FILE_ID
    if re.search(r'drive\.google\.com/open', url):
        qs = parse_qs(urlparse(url).query)
        if "id" in qs:
            file_id = qs["id"][0]
            return (
                f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t",
                "",
            )

    # Google Docs: docs.google.com/document/d/DOC_ID/...
    m = re.match(r'https?://docs\.google\.com/document/d/([^/?]+)', url)
    if m:
        doc_id = m.group(1)
        return (
            f"https://docs.google.com/document/d/{doc_id}/export?format=txt",
            f"document_{doc_id[:8]}.txt",
        )

    # Google Sheets: docs.google.com/spreadsheets/d/SHEET_ID/...
    m = re.match(r'https?://docs\.google\.com/spreadsheets/d/([^/?]+)', url)
    if m:
        sheet_id = m.group(1)
        return (
            f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv",
            f"spreadsheet_{sheet_id[:8]}.csv",
        )

    # Google Slides: docs.google.com/presentation/d/PRES_ID/...
    m = re.match(r'https?://docs\.google\.com/presentation/d/([^/?]+)', url)
    if m:
        pres_id = m.group(1)
        return (
            f"https://docs.google.com/presentation/d/{pres_id}/export/txt",
            f"presentation_{pres_id[:8]}.txt",
        )

    return None


async def download_url(url: str) -> tuple[str, bytes]:
    """Download a file from a URL and return (filename, bytes).

    Automatically transforms Google Drive / Docs / Sheets / Slides share links
    into direct download URLs.

    Raises ValueError for non-2xx HTTP status, HTML responses (auth/redirect
    pages), or files exceeding 50 MB.
    Raises aiohttp.ClientError on network failures.
    """
    import aiohttp  # local import — keeps module importable without network

    MAX_BYTES = 50 * 1024 * 1024  # 50 MB

    google = _detect_google_url(url)
    fetch_url = google[0] if google else url
    fallback_filename = google[1] if google else ""

    async with aiohttp.ClientSession() as session:
        async with session.get(fetch_url, timeout=aiohttp.ClientTimeout(total=120)) as resp:
            if not (200 <= resp.status < 300):
                raise ValueError(f"HTTP {resp.status} from {url}")

            content_type = resp.headers.get("Content-Type", "")
            if "text/html" in content_type:
                hint = " Ensure the file is shared as 'Anyone with the link'." if google else ""
                raise ValueError(f"URL returned an HTML page instead of a file.{hint}")

            filename = _filename_from_response(resp.headers, fetch_url) or fallback_filename or "downloaded_file"

            # Chunk-based reading — more reliable than read(n) for streaming responses
            chunks = []
            total = 0
            async for chunk in resp.content.iter_chunked(65536):
                total += len(chunk)
                if total > MAX_BYTES:
                    raise ValueError(f"File exceeds 50 MB limit: {url}")
                chunks.append(chunk)
            body = b"".join(chunks)

    return filename, body


def _filename_from_response(headers, url: str) -> str:
    """Extract filename from Content-Disposition header or URL path."""
    cd = headers.get("Content-Disposition", "")
    if cd:
        m = re.search(r'filename\*?=["\']?(?:UTF-8\'\')?([^"\';\r\n]+)', cd, re.IGNORECASE)
        if m:
            name = m.group(1).strip().strip('"\'')
            if name:
                return name
    path_part = urlparse(url).path.rstrip("/").split("/")[-1]
    return unquote(path_part) if path_part else ""


def extract_text(filename: str, file_bytes: bytes) -> str:
    """
    Extract text from a file.

    Supports plain text files (various extensions) and PDFs.
    Raises ValueError for binary files that cannot be decoded.
    """
    suffix = _get_suffix(filename)

    if suffix == ".pdf":
        return _extract_pdf(file_bytes)

    # For text files (known extensions or unknown — try decoding)
    try:
        return file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return file_bytes.decode("latin-1")
        except Exception:
            raise ValueError(
                f"Cannot decode '{filename}' as text. "
                "Binary files are not supported. Please upload text or PDF files."
            )


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 100) -> List[str]:
    """
    Split text into overlapping chunks for embedding.

    Prefers paragraph boundaries (double newlines) before splitting mid-content.
    Each chunk is at most chunk_size characters; consecutive chunks share
    'overlap' trailing characters from the previous chunk.
    """
    if not text.strip():
        return []

    paragraphs = text.split("\n\n")

    chunks: List[str] = []
    current_parts: List[str] = []
    current_size = 0

    for paragraph in paragraphs:
        para_len = len(paragraph)

        # Flush current chunk if adding this paragraph would exceed the limit
        if current_size + para_len > chunk_size and current_parts:
            chunk_str = "\n\n".join(current_parts)
            chunks.append(chunk_str)

            # Carry overlap from the end of the flushed chunk
            tail = chunk_str[-overlap:] if len(chunk_str) > overlap else chunk_str
            current_parts = [tail] if tail.strip() else []
            current_size = len(tail)

        # Paragraph is larger than chunk_size on its own — split by lines
        if para_len > chunk_size:
            if current_parts:
                chunks.append("\n\n".join(current_parts))
                current_parts = []
                current_size = 0

            lines = paragraph.split("\n")
            line_parts: List[str] = []
            line_size = 0

            for line in lines:
                if line_size + len(line) > chunk_size and line_parts:
                    chunks.append("\n".join(line_parts))
                    # Carry last line as overlap
                    line_parts = [line_parts[-1]]
                    line_size = len(line_parts[0])
                line_parts.append(line)
                line_size += len(line) + 1  # +1 for "\n"

            if line_parts:
                remainder = "\n".join(line_parts)
                current_parts = [remainder]
                current_size = len(remainder)
        else:
            current_parts.append(paragraph)
            current_size += para_len + 2  # +2 for "\n\n" separator

    # Flush anything remaining
    if current_parts:
        chunks.append("\n\n".join(current_parts))

    return [c for c in chunks if c.strip()]


def _get_suffix(filename: str) -> str:
    """Return lowercase file extension including the leading dot."""
    from pathlib import Path
    return Path(filename).suffix.lower()


def _extract_pdf(file_bytes: bytes) -> str:
    """Extract text from PDF bytes using pypdf."""
    try:
        import pypdf
    except ImportError:
        raise ValueError("PDF support requires pypdf. It should be installed already.")

    try:
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        pages = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
        return "\n\n".join(pages)
    except Exception as e:
        raise ValueError(f"Failed to extract PDF text: {str(e)}")
