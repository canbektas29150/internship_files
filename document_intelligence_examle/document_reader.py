"""Document text extraction helpers.

Supported by default:
- .txt / .md: direct text reading
- .pdf: text extraction with pypdf
- .png / .jpg / .jpeg: optional OCR with pytesseract if installed on system

For scanned PDFs, pypdf may return little or no text. In that case install a
proper OCR stack such as Tesseract + pdf image rendering, or convert pages to
images and pass them through this tool.
"""

from __future__ import annotations

from pathlib import Path


def read_document(path: str | Path) -> str:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Input file does not exist: {file_path}")

    suffix = file_path.suffix.lower()
    if suffix in {".txt", ".md"}:
        return file_path.read_text(encoding="utf-8", errors="ignore")
    if suffix == ".pdf":
        return _read_pdf(file_path)
    if suffix in {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"}:
        return _ocr_image(file_path)
    raise ValueError(f"Unsupported file type: {suffix}. Use TXT, PDF, PNG, JPG, WEBP, or TIFF.")


def _read_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("pypdf is required for PDF extraction. Run: pip install pypdf") from exc

    reader = PdfReader(str(path))
    pages: list[str] = []
    for index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        pages.append(f"\n--- PAGE {index} ---\n{text}")

    combined = "\n".join(pages).strip()
    if len(combined) < 30:
        return (
            "[WARNING: Very little text was extracted from this PDF. It may be scanned. "
            "Use OCR or convert the pages to images.]\n" + combined
        )
    return combined


def _ocr_image(path: Path) -> str:
    try:
        from PIL import Image
        import pytesseract
    except ImportError as exc:
        raise RuntimeError(
            "Image OCR requires pillow and pytesseract Python packages. "
            "Also install the Tesseract OCR engine on your operating system."
        ) from exc

    image = Image.open(path)
    text = pytesseract.image_to_string(image, lang="tur+eng")
    if not text.strip():
        return "[WARNING: OCR returned empty text.]"
    return text


def compact_text(text: str, max_chars: int = 60_000) -> str:
    """Keep prompt size controlled for normal documents."""
    text = "\n".join(line.rstrip() for line in text.splitlines())
    text = "\n".join(line for line in text.splitlines() if line.strip())
    if len(text) <= max_chars:
        return text
    head = text[: max_chars // 2]
    tail = text[-max_chars // 2 :]
    return head + "\n\n[... DOCUMENT TRUNCATED IN THE MIDDLE ...]\n\n" + tail
