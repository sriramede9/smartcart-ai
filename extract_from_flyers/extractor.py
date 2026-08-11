"""
Stage 0 — Dual-Path Extraction Engine (Approach C)

Detects whether each PDF page has usable embedded text or is a flattened
scan, and routes it to the right extractor. Output is a single unified
token schema regardless of source, so everything downstream (clustering,
normalization) doesn't care how a token was produced.

Unified token dict:
    {
        "text": str,
        "x0": float, "top": float, "x1": float, "bottom": float,
        "page": int,
        "source": "vector" | "ocr",
        "conf": float | None   # OCR confidence, None for vector text
    }
"""

from __future__ import annotations
import pdfplumber
from pdf2image import convert_from_path
import pytesseract
from pytesseract import Output

SCAN_CHAR_THRESHOLD = 100  # below this, treat the page as scanned/flattened
OCR_DPI = 300


def _is_scanned_page(page: "pdfplumber.page.Page") -> bool:
    text = page.extract_text() or ""
    return len(text.strip()) < SCAN_CHAR_THRESHOLD


def _extract_vector_tokens(page: "pdfplumber.page.Page", page_num: int) -> list[dict]:
    tokens = []
    for word in page.extract_words(use_text_flow=False, keep_blank_chars=False):
        tokens.append({
            "text": word["text"],
            "x0": float(word["x0"]),
            "top": float(word["top"]),
            "x1": float(word["x1"]),
            "bottom": float(word["bottom"]),
            "page": page_num,
            "source": "vector",
            "conf": None,
        })
    return tokens


def _extract_ocr_tokens(pil_image, page_num: int, pdf_page_width: float, pdf_page_height: float) -> list[dict]:
    data = pytesseract.image_to_data(pil_image, output_type=Output.DICT)

    # Scale factor: OCR image pixels -> PDF point coordinates, so OCR tokens
    # live in the SAME coordinate space as pdfplumber tokens.
    scale_x = pdf_page_width / pil_image.width
    scale_y = pdf_page_height / pil_image.height

    tokens = []
    n = len(data["text"])
    for i in range(n):
        raw_text = data["text"][i].strip()
        conf = float(data["conf"][i])
        if not raw_text or conf < 0:
            continue
        x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
        tokens.append({
            "text": raw_text,
            "x0": x * scale_x,
            "top": y * scale_y,
            "x1": (x + w) * scale_x,
            "bottom": (y + h) * scale_y,
            "page": page_num,
            "source": "ocr",
            "conf": conf,
        })
    return tokens


def extract_tokens(pdf_path: str, pages: list[int] | None = None) -> list[dict]:
    """
    Extract unified tokens from a flyer PDF, auto-routing each page to
    vector or OCR extraction.

    pages: optional 0-indexed list of pages to process (default: all pages)
    """
    all_tokens: list[dict] = []

    with pdfplumber.open(pdf_path) as pdf:
        target_pages = pages if pages is not None else range(len(pdf.pages))

        # Pre-render only the pages we'll actually need OCR for, lazily.
        rendered_images = None

        for page_num in target_pages:
            page = pdf.pages[page_num]

            if not _is_scanned_page(page):
                all_tokens.extend(_extract_vector_tokens(page, page_num))
                continue

            # Lazy render on first OCR need (pdf2image renders whole doc by default,
            # so we render just this page for memory efficiency on big flyers).
            imgs = convert_from_path(
                pdf_path, dpi=OCR_DPI,
                first_page=page_num + 1, last_page=page_num + 1
            )
            pil_image = imgs[0]
            all_tokens.extend(
                _extract_ocr_tokens(pil_image, page_num, page.width, page.height)
            )

    return all_tokens


if __name__ == "__main__":
    import sys, json
    path = sys.argv[1]
    toks = extract_tokens(path)
    print(f"Extracted {len(toks)} tokens from {path}")
    print(json.dumps(toks[:10], indent=2))
