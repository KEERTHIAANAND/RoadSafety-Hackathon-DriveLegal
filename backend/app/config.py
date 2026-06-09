"""
DriveLegal — Central Configuration

All paths, model names, and settings are defined here.
This is the single source of truth for the entire backend.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file and override existing ones
load_dotenv(override=True)

# ============================================
# Paths
# ============================================
# Root of the backend folder
BACKEND_DIR = Path(__file__).resolve().parent.parent

# Where your legal PDFs and challan_fines.csv live
DATASETS_DIR = BACKEND_DIR / os.getenv("DATASETS_PATH", "../datasets")

# Where ChromaDB stores its vector data persistently
CHROMA_DB_DIR = BACKEND_DIR / os.getenv("CHROMA_DB_PATH", "./data/chroma_db")

# Challan fines CSV file path
CHALLAN_FINES_CSV = DATASETS_DIR / "challan_fines.csv"

# ============================================
# AI Models
# ============================================
# Embedding model (runs locally, no API key needed)
# Downloads automatically on first run (~80MB)
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

# LLM model (used in Phase 2 for the agent brain)
LLM_MODEL_NAME = os.getenv("LLM_MODEL", "llama-3.1-8b-instant")

# Groq API key (needed only in Phase 2)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# ============================================
# ChromaDB Collection Names
# ============================================
NATIONAL_LAWS_COLLECTION = "national_laws"
STATE_LAWS_COLLECTION = "state_laws"

# ============================================
# Chunking Configuration
# ============================================
CHUNK_SIZE = 500        # Number of characters per chunk
CHUNK_OVERLAP = 100     # Overlap between consecutive chunks (for context continuity)

# ============================================
# Retrieval Configuration
# ============================================
TOP_K_RESULTS = 5       # Number of similar chunks to retrieve per search

# ============================================
# PDF → Collection Mapping
# ============================================
# This maps each PDF file to its metadata and target ChromaDB collection.
# When you add a new state or country, just add a new entry here.

PDF_REGISTRY = [
    {
        "filename": "motorvehicleact-1988.pdf",
        "collection": NATIONAL_LAWS_COLLECTION,
        "metadata": {
            "level": "national",
            "state": "all",
            "act_name": "Motor Vehicles Act 1988",
            "year": 1988,
            "country": "india",
        },
    },
    {
        "filename": "Motor Vehicles (Amendment) Act, 2019.pdf",
        "collection": NATIONAL_LAWS_COLLECTION,
        "metadata": {
            "level": "national",
            "state": "all",
            "act_name": "Motor Vehicles (Amendment) Act 2019",
            "year": 2019,
            "country": "india",
        },
    },
    {
        "filename": "Central motor vehicle rules 1989.pdf",
        "collection": NATIONAL_LAWS_COLLECTION,
        "metadata": {
            "level": "national",
            "state": "all",
            "act_name": "Central Motor Vehicle Rules 1989",
            "year": 1989,
            "country": "india",
        },
    },
    {
        "filename": "TN motor vehicles rules 1989.pdf",
        "collection": STATE_LAWS_COLLECTION,
        "metadata": {
            "level": "state",
            "state": "tamil_nadu",
            "act_name": "Tamil Nadu Motor Vehicles Rules 1989",
            "year": 1989,
            "country": "india",
        },
    },
    {
        "filename": "TN motor vehicle taxation act 1974.pdf",
        "collection": STATE_LAWS_COLLECTION,
        "metadata": {
            "level": "state",
            "state": "tamil_nadu",
            "act_name": "Tamil Nadu Motor Vehicle Taxation Act 1974",
            "year": 1974,
            "country": "india",
        },
    },
    {
        "filename": "TN motor vehicle taxation rules 1974.pdf",
        "collection": STATE_LAWS_COLLECTION,
        "metadata": {
            "level": "state",
            "state": "tamil_nadu",
            "act_name": "Tamil Nadu Motor Vehicle Taxation Rules 1974",
            "year": 1974,
            "country": "india",
        },
    },
    {
        "filename": "delhi-elv-rules.pdf",
        "collection": STATE_LAWS_COLLECTION,
        "metadata": {
            "level": "state",
            "state": "delhi",
            "act_name": "Delhi End-of-Life Vehicle Regulations",
            "year": 2024,
            "country": "india",
        },
    },
]
