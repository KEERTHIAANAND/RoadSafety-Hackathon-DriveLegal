# DriveLegal — Backend Development Instructions (Agentic RAG)

> **Approach:** Python backend first → Test with Postman/curl → Mobile UI later (Flutter/React Native)

---

## Current Project State

```
RoadSafety-Hackathon-DriveLegal/
├── datasets/
│   ├── motorvehicleact-1988.pdf          ← National Act (base law)
│   ├── Motor Vehicles (Amendment) Act, 2019.pdf  ← National Amendment (overrides fines)
│   ├── Central motor vehicle rules 1989.pdf      ← National Rules
│   ├── TN motor vehicles rules 1989.pdf          ← Tamil Nadu state rules
│   ├── TN motor vehicle taxation act 1974.pdf    ← TN tax law
│   ├── TN motor vehicle taxation rules 1974.pdf  ← TN tax rules
│   └── challan_fines.csv                ← ✅ JUST CREATED — structured fines table (30+ violations)
├── docs/
│   ├── Agentic_RAG_Architecture.md      ← Full architecture deep-dive
│   └── Implementation_Roadmap.md        ← Step-by-step roadmap
└── README.md
```

### What Was Missing (Now Fixed)
✅ **Confirmed:** The `challan_fines.csv` was the key missing piece. Your PDFs contain the raw legal text, but they don't have a clean, queryable table of `violation → fine amount → section`. That CSV now has **30+ common violations** with exact fine amounts from the 2019 Amendment. You should verify and expand it as you read through the PDFs more carefully.

---

## Step-by-Step Backend Development

### Step 1: Initialize the Python Backend

```
RoadSafety-Hackathon-DriveLegal/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              ← FastAPI app entry point
│   │   ├── config.py            ← API keys, model names, paths
│   │   ├── agent/
│   │   │   ├── __init__.py
│   │   │   ├── orchestrator.py  ← The Agentic RAG brain
│   │   │   ├── tools.py         ← All 5 tools defined here
│   │   │   └── prompts.py       ← System prompt & few-shot examples
│   │   ├── ingestion/
│   │   │   ├── __init__.py
│   │   │   ├── pdf_parser.py    ← Parse PDFs into text chunks
│   │   │   ├── chunker.py       ← Split text into overlapping chunks
│   │   │   └── ingest.py        ← Main script: parse → chunk → embed → store
│   │   ├── db/
│   │   │   ├── __init__.py
│   │   │   ├── vector_store.py  ← ChromaDB wrapper (search functions)
│   │   │   └── challan_db.py    ← SQLite/CSV wrapper (fine lookup)
│   │   └── models/
│   │       ├── __init__.py
│   │       └── schemas.py       ← Pydantic request/response models
│   ├── data/
│   │   └── chroma_db/           ← ChromaDB persistent storage (auto-created)
│   ├── requirements.txt
│   └── .env                     ← API keys (GOOGLE_API_KEY, etc.)
├── datasets/                    ← Your PDFs + challan_fines.csv
└── docs/
```

**Commands to run:**
```bash
cd d:\Projects\RoadSafety-Hackathon-DriveLegal
mkdir backend
cd backend
python -m venv venv
venv\Scripts\activate
```

**`requirements.txt`:**
```
# Core
fastapi==0.115.*
uvicorn[standard]==0.34.*
python-dotenv==1.1.*
pydantic==2.*

# AI / LLM
langchain>=0.3
langchain-google-genai          # For Gemini models
# langchain-openai              # Uncomment if using OpenAI instead

# Embeddings & Vector DB
chromadb>=0.5
sentence-transformers>=3.0      # Local embeddings (free, no API key needed)

# PDF Parsing
pymupdf==1.25.*                 # Fast PDF text extraction
# llama-parse                   # Uncomment for better table extraction (needs API key)

# Data
pandas>=2.0
```

```bash
pip install -r requirements.txt
```

---

### Step 2: Data Ingestion Pipeline

This is the most critical step. The quality of your RAG depends entirely on this.

**What happens here:**
```
PDF files → Parse text → Clean text → Split into chunks → Add metadata → Embed → Store in ChromaDB
```

**File: `backend/app/ingestion/pdf_parser.py`**
- Use `pymupdf` (aka `fitz`) to extract text from each PDF.
- Preserve page numbers (needed for citations).
- Detect and separate tables vs. narrative text.

**File: `backend/app/ingestion/chunker.py`**
- Split text into chunks of ~500 words with ~50 words overlap.
- Each chunk gets metadata:
  ```python
  {
      "source_file": "Motor Vehicles (Amendment) Act, 2019.pdf",
      "level": "national",        # or "state"
      "state": "all",             # or "tamil_nadu"
      "year": 2019,
      "page_number": 12,
      "act_name": "MV Amendment Act 2019"
  }
  ```

**File: `backend/app/ingestion/ingest.py`**
- Main script that orchestrates: parse → chunk → embed → store.
- Creates **two ChromaDB collections**:
  - `national_laws` — chunks from the 3 national PDFs
  - `state_laws` — chunks from the 3 TN PDFs (with `state: "tamil_nadu"` metadata)
- Uses `sentence-transformers` model `all-MiniLM-L6-v2` (fast, free, runs locally) or `BAAI/bge-m3` (multilingual, better accuracy).

**Run it once:**
```bash
python -m app.ingestion.ingest
```
This populates `backend/data/chroma_db/` with your vectorized legal data.

---

### Step 3: Build the 5 Agent Tools

**File: `backend/app/agent/tools.py`**

Each tool is a Python function decorated with `@tool` (LangChain) so the LLM Agent can call it.

#### Tool 1: `search_national_laws(query: str) → str`
```python
# Searches ChromaDB collection "national_laws"
# Returns top 5 chunks with section references
```

#### Tool 2: `search_state_laws(query: str, state: str) → str`
```python
# Searches ChromaDB collection "state_laws"
# Filters by metadata: state == state parameter
# Returns top 5 chunks
```

#### Tool 3: `calculate_challan(violation: str, vehicle_type: str, state: str) → str`
```python
# Loads challan_fines.csv (or SQLite)
# Searches for matching violation_code
# Applies jurisdiction filter (national + state override if exists)
# Returns exact fine, section, imprisonment details as JSON
```

#### Tool 4: `resolve_location(latitude: float, longitude: float) → str`
```python
# Calls OpenStreetMap Nominatim reverse geocoding API
# Returns: {"state": "Tamil Nadu", "country": "India", "city": "Chennai"}
```

#### Tool 5: `format_citation(section: str, act_name: str, year: int) → str`
```python
# Simple utility: returns formatted citation string
# e.g., "Section 194D, Motor Vehicles (Amendment) Act, 2019"
```

---

### Step 4: Build the Orchestrator Agent

**File: `backend/app/agent/orchestrator.py`**

This is the brain. It uses LangChain's `create_tool_calling_agent` with the Gemini model.

```python
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# 1. Initialize LLM
llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0)

# 2. Define the system prompt (from prompts.py)
prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    MessagesPlaceholder("chat_history"),
    ("human", "{input}"),
    MessagesPlaceholder("agent_scratchpad"),
])

# 3. Create the agent with all 5 tools
tools = [search_national_laws, search_state_laws, calculate_challan,
         resolve_location, format_citation]

agent = create_tool_calling_agent(llm, tools, prompt)

# 4. Wrap in executor (handles the ReAct loop)
agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    verbose=True,    # Set True during development to see reasoning
    max_iterations=8,
    handle_parsing_errors=True,
)
```

The `AgentExecutor` handles the full ReAct loop:
```
THOUGHT → ACTION (tool call) → OBSERVATION → THOUGHT → ACTION → ... → FINAL ANSWER
```

---

### Step 5: Build the FastAPI Endpoints

**File: `backend/app/main.py`**

```python
# POST /chat
# Input:  { "query": "...", "latitude": 13.08, "longitude": 80.27, "chat_history": [] }
# Output: { "response": "...", "sources": [...], "tools_used": [...] }

# POST /calculate-challan
# Input:  { "violation": "NO_HELMET", "vehicle_type": "2-wheeler", "state": "tamil_nadu" }
# Output: { "fine": 1000, "section": "194D", ... }

# GET /violations
# Output: List of all violation codes and descriptions (for the mobile app's dropdown)

# GET /health
# Output: { "status": "ok" }
```

**Run the server:**
```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

**Test with curl:**
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the fine for not wearing helmet in Chennai?", "latitude": 13.08, "longitude": 80.27}'
```

---

### Step 6: Testing & Accuracy Validation

Before touching any UI, validate the backend thoroughly:

1. **Unit test the Challan Calculator:**
   - Input: `NO_HELMET, 2-wheeler, tamil_nadu` → Expected: `₹1000, Section 194D`
   - Input: `DRUNK_DRIVING, all, national` → Expected: `₹10000, Section 185, Up to 6 months`
   - Test all 30+ violations in the CSV.

2. **Test the RAG retrieval quality:**
   - Ask: "Is helmet mandatory?" → Should retrieve Section 129 chunks.
   - Ask: "What are the rules for commercial vehicle permits in TN?" → Should retrieve TN Rule chunks.
   - Check that the agent calls **both** national and state tools for location-specific queries.

3. **Hallucination check:**
   - Ask about a law that doesn't exist: "What is the fine for jaywalking in India?"
   - The agent should say "I don't have verified information" — NOT make something up.

4. **Create a test suite** (`backend/tests/`) with 50-100 sample Q&A pairs.

---

## Development Order Summary

| Step | What | Output | Est. Time |
|---|---|---|---|
| 1 | Initialize project, install deps | Working Python environment | 30 min |
| 2 | Data ingestion pipeline | ChromaDB populated with vectorized legal chunks | 3-4 hours |
| 3 | Build 5 agent tools | 5 tested tool functions | 2-3 hours |
| 4 | Build orchestrator agent | Working ReAct agent that calls tools | 2 hours |
| 5 | Build FastAPI endpoints | API you can test with curl/Postman | 1-2 hours |
| 6 | Testing & accuracy tuning | Validated accuracy on 50+ test cases | 2-3 hours |
| 7 | **THEN** → Mobile UI | Flutter/React Native app | After backend is solid |

---

## Tech Stack Summary (Backend Only)

| Component | Technology | Cost |
|---|---|---|
| Language | Python 3.11+ | Free |
| API Framework | FastAPI + Uvicorn | Free |
| LLM | Gemini 2.0 Flash (via API) | Free tier available |
| Agent Framework | LangChain | Free |
| Embeddings | `all-MiniLM-L6-v2` (sentence-transformers) | Free, runs locally |
| Vector DB | ChromaDB (local) | Free |
| Challan DB | CSV → pandas (or SQLite) | Free |
| Geocoding | OpenStreetMap Nominatim | Free |

> [!TIP]
> **For the mobile app later:** Use **Flutter** (Dart) or **React Native** (TypeScript). Both can call your FastAPI backend via HTTP. Flutter has better offline SQLite support via `sqflite`. For offline challan calculator, bundle the `challan_fines.csv` inside the mobile app assets.

---

## What to Do Next (In Order)

1. ✅ ~~Create challan_fines.csv~~ — **DONE**
2. **→ Next:** Initialize the Python backend project structure and install dependencies
3. Write the PDF ingestion pipeline (`pdf_parser.py`, `chunker.py`, `ingest.py`)
4. Build and test each tool individually
5. Wire up the Orchestrator Agent
6. Create FastAPI endpoints
7. Test everything via Postman/curl
8. Move to mobile UI

**Shall I start writing the actual Python code for Step 2 (the ingestion pipeline)?**
