"""
DriveLegal - Main Ingestion Pipeline

This is the script you run ONCE to:
  1. Parse all PDFs -> raw text (page-level)
  2. Chunk text -> overlapping pieces with metadata
  3. Embed chunks -> numerical vectors (using local embedding model)
  4. Store in ChromaDB -> persistent vector database

Usage:
    cd backend
    python -m app.ingestion.ingest

NO LLM NEEDED - uses only the local Embedding Model (all-MiniLM-L6-v2).
"""

import sys
import io
import time
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from app.config import (
    DATASETS_DIR,
    CHROMA_DB_DIR,
    EMBEDDING_MODEL_NAME,
    PDF_REGISTRY,
)
from app.ingestion.pdf_parser import extract_text_from_pdf
from app.ingestion.chunker import create_chunks

# Fix Windows console encoding for Unicode characters
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def run_ingestion():
    """
    Full ingestion pipeline:
    PDF files -> Parse -> Chunk -> Embed -> Store in ChromaDB
    """
    start_time = time.time()

    print("=" * 60)
    print("[STARTING] DriveLegal - Data Ingestion Pipeline")
    print("=" * 60)

    # -------------------------------------------------
    # Step 1: Initialize the Embedding Model (local, free)
    # -------------------------------------------------
    print(f"\n[STEP 1] Loading embedding model: {EMBEDDING_MODEL_NAME}")
    print("   (First run will download ~80MB model. Subsequent runs use cache.)")

    embedding_fn = SentenceTransformerEmbeddingFunction(
        model_name=EMBEDDING_MODEL_NAME,
    )
    print("   [OK] Embedding model loaded.\n")

    # -------------------------------------------------
    # Step 2: Initialize ChromaDB (local, persistent storage)
    # -------------------------------------------------
    print(f"[STEP 2] Initializing ChromaDB at: {CHROMA_DB_DIR}")
    client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))

    # Track stats
    total_chunks_stored = 0
    collection_stats = {}

    # -------------------------------------------------
    # Step 3: Process each PDF from the registry
    # -------------------------------------------------
    print(f"\n[STEP 3] Processing {len(PDF_REGISTRY)} registered PDFs...\n")

    for entry in PDF_REGISTRY:
        filename = entry["filename"]
        collection_name = entry["collection"]
        metadata = entry["metadata"]

        pdf_path = DATASETS_DIR / filename

        if not pdf_path.exists():
            print(f"  [WARN] Skipping {filename} - file not found at {pdf_path}")
            continue

        print(f"--- Processing: {filename} ---")

        # Step 3a: Parse PDF -> pages
        pages = extract_text_from_pdf(pdf_path)

        # Step 3b: Chunk pages -> smaller pieces with metadata
        chunks = create_chunks(pages, extra_metadata=metadata)
        print(f"  [CHUNKS] Created {len(chunks)} chunks")

        # Step 3c: Get or create the ChromaDB collection
        collection = client.get_or_create_collection(
            name=collection_name,
            embedding_function=embedding_fn,
            metadata={"description": f"DriveLegal {collection_name} collection"},
        )

        # Step 3d: Add chunks to ChromaDB in batches
        # ChromaDB handles embedding automatically via the embedding_function
        batch_size = 50
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]

            collection.add(
                ids=[c["chunk_id"] for c in batch],
                documents=[c["text"] for c in batch],
                metadatas=[c["metadata"] for c in batch],
            )

        print(f"  [STORED] {len(chunks)} chunks in collection: '{collection_name}'")

        # Track stats
        total_chunks_stored += len(chunks)
        if collection_name not in collection_stats:
            collection_stats[collection_name] = 0
        collection_stats[collection_name] += len(chunks)

        print()

    # -------------------------------------------------
    # Step 4: Print summary
    # -------------------------------------------------
    elapsed = time.time() - start_time

    print("=" * 60)
    print("[DONE] INGESTION COMPLETE")
    print("=" * 60)
    print(f"\nSummary:")
    print(f"   Total chunks stored: {total_chunks_stored}")
    for coll_name, count in collection_stats.items():
        print(f"   Collection '{coll_name}': {count} chunks")
    print(f"   Time taken: {elapsed:.1f} seconds")
    print(f"   ChromaDB path: {CHROMA_DB_DIR}")
    print(f"   Embedding model: {EMBEDDING_MODEL_NAME}")
    print()


def verify_ingestion():
    """
    Quick verification: search the vector DB with a sample query
    to confirm everything was stored correctly.
    """
    print("=" * 60)
    print("[VERIFY] Verifying Ingestion - Sample Searches")
    print("=" * 60)

    embedding_fn = SentenceTransformerEmbeddingFunction(
        model_name=EMBEDDING_MODEL_NAME,
    )

    client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))

    # List all collections
    collections = client.list_collections()
    print(f"\nCollections found: {[c.name for c in collections]}\n")

    # Test queries
    test_queries = [
        ("national_laws", "helmet mandatory two wheeler"),
        ("national_laws", "fine for drunk driving penalty"),
        ("national_laws", "speed limit exceeding"),
        ("state_laws", "Tamil Nadu vehicle registration"),
        ("state_laws", "taxation motor vehicle Tamil Nadu"),
    ]

    for coll_name, query in test_queries:
        try:
            collection = client.get_collection(
                name=coll_name,
                embedding_function=embedding_fn,
            )

            results = collection.query(
                query_texts=[query],
                n_results=2,
            )

            print(f"[SEARCH] Query: '{query}' (Collection: {coll_name})")
            print(f"   Collection size: {collection.count()} chunks")

            if results["documents"] and results["documents"][0]:
                for j, doc in enumerate(results["documents"][0]):
                    meta = results["metadatas"][0][j]
                    distance = results["distances"][0][j] if results["distances"] else "N/A"
                    print(f"   Result {j+1} (distance: {distance:.4f}):")
                    print(f"     Source: {meta.get('act_name', 'N/A')}, Page {meta.get('page_number', 'N/A')}")
                    print(f"     Text: {doc[:150]}...")
            else:
                print("   [WARN] No results found.")
            print()

        except Exception as e:
            print(f"   [ERROR] Error querying '{coll_name}': {e}\n")


# ============================================
# Main entry point
# ============================================
if __name__ == "__main__":
    # Run the full ingestion pipeline
    run_ingestion()

    # Verify with sample searches
    verify_ingestion()
