"""Convert invoice files (PDF or image) into PIL Image objects."""

from __future__ import annotations

from pathlib import Path

import pymupdf as fitz
from PIL import Image

PDF_EXTENSION = ".pdf"
IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp"})
PDF_RENDER_DPI = 200


def convert_to_images(file_path: str) -> list[Image.Image]:
    """Convert an invoice file into one or more PIL images.

    PDFs are rendered page-by-page at 200 DPI. Image files (JPG, JPEG, PNG,
    WEBP) are opened directly and returned as a single-item list. Downstream
    code can always work with images regardless of the original input format.

    Args:
        file_path: Path to a supported invoice file.

    Returns:
        A list of PIL Image objects — one per PDF page, or a single image
        for raster formats.

    Raises:
        ValueError: If the file extension is not supported.
    """
    path = Path(file_path)
    extension = path.suffix.lower()

    if extension == PDF_EXTENSION:
        return _pdf_to_images(path)
    if extension in IMAGE_EXTENSIONS:
        with Image.open(path) as img:
            return [img.copy()]
    raise ValueError(
        f"Unsupported file extension '{extension}'. "
        f"Supported formats: PDF, JPG, JPEG, PNG, WEBP."
    )


def _pdf_to_images(path: Path) -> list[Image.Image]:
    """Render each page of a PDF as a PIL Image at 200 DPI."""
    images: list[Image.Image] = []

    with fitz.open(path) as document:
        for page in document:
            pixmap = page.get_pixmap(dpi=PDF_RENDER_DPI)
            images.append(pixmap.pil_image())

    return images
