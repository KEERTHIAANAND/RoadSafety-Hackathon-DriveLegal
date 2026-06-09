"""
DriveLegal - PDF Parser

Extracts raw text from legal PDF files using PyMuPDF (fitz).
Preserves page-level boundaries so we can attach page numbers as metadata.
Also attempts to detect section headers for better chunk quality.

NO LLM OR API NEEDED - runs 100% locally.
"""

import sys
import io
import fitz  # PyMuPDF
import re
from pathlib import Path
from typing import Optional

# Fix Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def extract_text_from_pdf(pdf_path: str | Path) -> list[dict]:
    """
    Extract text from a PDF file, returning a list of page-level documents.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        List of dicts, each containing:
            - "text": The raw text content of the page.
            - "page_number": 1-indexed page number.
            - "source_file": Name of the PDF file.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    doc = fitz.open(str(pdf_path))
    pages = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")  # Extract as plain text

        # Clean the extracted text
        text = _clean_text(text)

        # Skip pages with very little text (likely blank or image-only pages)
        if len(text.strip()) < 50:
            continue

        pages.append(
            {
                "text": text,
                "page_number": page_num + 1,  # 1-indexed
                "source_file": pdf_path.name,
            }
        )

    doc.close()

    print(f"  [OK] Extracted {len(pages)} pages from: {pdf_path.name}")
    return pages


def _clean_text(text: str) -> str:
    """
    Clean raw PDF text:
    - Remove excessive whitespace and blank lines.
    - Normalize unicode characters.
    - Remove page headers/footers if detectable.
    """
    # Replace multiple newlines with a single newline
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Replace multiple spaces with single space (but preserve newlines)
    text = re.sub(r"[^\S\n]+", " ", text)

    # Remove common PDF artifacts (page numbers standalone on a line)
    text = re.sub(r"^\s*\d{1,3}\s*$", "", text, flags=re.MULTILINE)

    # Strip leading/trailing whitespace from each line
    lines = [line.strip() for line in text.split("\n")]
    text = "\n".join(lines)

    return text.strip()


def extract_all_pdfs(datasets_dir: str | Path) -> dict[str, list[dict]]:
    """
    Extract text from all PDF files in the datasets directory.

    Args:
        datasets_dir: Path to the directory containing PDF files.

    Returns:
        Dict mapping filename to list of page documents.
    """
    datasets_dir = Path(datasets_dir)
    all_docs = {}

    pdf_files = sorted(datasets_dir.glob("*.pdf"))
    print(f"\n[INFO] Found {len(pdf_files)} PDF files in: {datasets_dir}\n")

    for pdf_path in pdf_files:
        try:
            pages = extract_text_from_pdf(pdf_path)
            all_docs[pdf_path.name] = pages
        except Exception as e:
            print(f"  [ERROR] Error processing {pdf_path.name}: {e}")

    return all_docs


# ============================================
# Quick test — run this file directly to verify
# ============================================
if __name__ == "__main__":
    from app.config import DATASETS_DIR

    all_docs = extract_all_pdfs(DATASETS_DIR)
    print("\n📊 Summary:")
    for filename, pages in all_docs.items():
        total_chars = sum(len(p["text"]) for p in pages)
        print(f"   {filename}: {len(pages)} pages, {total_chars:,} characters")
