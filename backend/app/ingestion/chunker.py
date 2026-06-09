"""
DriveLegal — Text Chunker

Splits page-level text into smaller, overlapping chunks suitable for
vector embedding and retrieval.

Uses LangChain's RecursiveCharacterTextSplitter, which intelligently
splits on paragraph boundaries, then sentences, then words — preserving
meaningful context in each chunk.

NO LLM OR API NEEDED — runs 100% locally.
"""

from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.config import CHUNK_SIZE, CHUNK_OVERLAP


def create_chunks(
    pages: list[dict],
    extra_metadata: dict,
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
) -> list[dict]:
    """
    Split page-level documents into smaller, overlapping chunks with metadata.

    Args:
        pages: List of page dicts from pdf_parser (each has "text", "page_number", "source_file").
        extra_metadata: Additional metadata to attach to every chunk
                        (e.g., level, state, year, act_name).
        chunk_size: Maximum characters per chunk.
        chunk_overlap: Number of overlapping characters between consecutive chunks.

    Returns:
        List of chunk dicts, each containing:
            - "text": The chunk text content.
            - "metadata": Combined page metadata + extra_metadata.
            - "chunk_id": A unique ID for this chunk.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=[
            "\n\n",  # First try splitting on paragraph boundaries
            "\n",    # Then on newlines
            ". ",    # Then on sentence boundaries
            ", ",    # Then on clause boundaries
            " ",     # Then on word boundaries
            "",      # Last resort: character-level
        ],
    )

    all_chunks = []
    chunk_counter = 0

    for page in pages:
        # Split this page's text into chunks
        text_chunks = splitter.split_text(page["text"])

        for chunk_text in text_chunks:
            # Skip very short chunks (likely artifacts)
            if len(chunk_text.strip()) < 30:
                continue

            chunk_counter += 1

            # Build metadata: page-level info + PDF-level info
            metadata = {
                "source_file": page["source_file"],
                "page_number": page["page_number"],
                **extra_metadata,  # level, state, year, act_name, country
            }

            # Create a unique chunk ID
            chunk_id = (
                f"{extra_metadata.get('act_name', 'unknown')}"
                f"_p{page['page_number']}"
                f"_c{chunk_counter}"
            ).replace(" ", "_").lower()

            all_chunks.append(
                {
                    "text": chunk_text.strip(),
                    "metadata": metadata,
                    "chunk_id": chunk_id,
                }
            )

    return all_chunks


# ============================================
# Quick test — run this file directly to verify
# ============================================
if __name__ == "__main__":
    # Example test with dummy data
    dummy_pages = [
        {
            "text": "Section 129. Wearing of protective headgear. "
                    "Every person driving or riding on a motor cycle of any class "
                    "or description shall, while in a public place, wear protective "
                    "headgear conforming to the standards of Bureau of Indian Standards. "
                    "Provided that the provisions of this section shall not apply to a "
                    "person who is a Sikh, if he is, while driving or riding on the "
                    "motor cycle, in a public place, wearing a turban.",
            "page_number": 45,
            "source_file": "motorvehicleact-1988.pdf",
        }
    ]

    extra_meta = {
        "level": "national",
        "state": "all",
        "act_name": "Motor Vehicles Act 1988",
        "year": 1988,
        "country": "india",
    }

    chunks = create_chunks(dummy_pages, extra_meta)
    print(f"Created {len(chunks)} chunks from {len(dummy_pages)} pages")
    for c in chunks[:3]:
        print(f"\n  ID: {c['chunk_id']}")
        print(f"  Text: {c['text'][:100]}...")
        print(f"  Metadata: {c['metadata']}")
