"""File text extraction and chunking for ChromaDB embedding"""

import io
from typing import List

SUPPORTED_TEXT_EXTENSIONS = {
    ".txt", ".md", ".py", ".js", ".ts", ".jsx", ".tsx",
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg",
    ".html", ".css", ".sh", ".bash", ".sql", ".xml",
    ".csv", ".rst", ".env", ".java", ".go", ".rs",
    ".cpp", ".c", ".h", ".cs", ".rb", ".php",
}


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
