# PDF Analyst — Chat with Your Documents

A sophisticated RAG (Retrieval-Augmented Generation) system that lets you
**chat with PDF documents** using either a classic conversational chain or a
**free autonomous agent** that searches, reads specific pages, and
cross-references content using a ReAct loop.

**Powered by:** OpenAI GPT (LLM) + `text-embedding-3-small` (embeddings) +
FAISS (vector store) + PyMuPDF (page-level extraction) + **Hybrid RAG**
(BM25 keyword + dense embedding fusion via RRF) + optional GPT reranking.

---

## Docker

Run the full stack — PostgreSQL+pgvector, FastAPI backend, and the Next.js frontend — with a single command:

```bash
cp .env-example .env      # add your OPENAI_API_KEY (and DB creds if you changed them)
docker compose up --build
```

| Service | URL | Notes |
| --- | --- | --- |
| Frontend | http://localhost:3000 | Next.js production server (Docker) |
| Backend API | http://localhost:8000/api | `/api/docs` for the OpenAPI UI, `/api/health` to check liveness |
| PostgreSQL (pgvector) | localhost:5436 | db `docuchat`, user `postgres`, password `docuchat123` |

> The database schema (`backend/schema.sql`) is created automatically on first `docker compose up` (the data volume is empty). Subsequent starts reuse the persisted `db_data` volume; to reset, run `docker compose down -v`.

## Table of Contents

1. [Features](#features)
2. [Architecture](#architecture)
3. [Project Structure](#project-structure)
4. [Installation](#installation)
5. [Configuration](#configuration)
6. [Usage](#usage)
7. [Agent Mode Explained](#agent-mode-explained)
8. [Hybrid RAG Explained](#hybrid-rag-explained)
9. [API Reference](#api-reference)
10. [Development](#development)
11. [License](#license)

---

## Features

| Feature | Description |
|---|---|
| **Free Agent** | Autonomous ReAct-style agent that uses tools iteratively — search, read pages, summarize, compare — until it has a confident answer |
| **Page-Level Reading** | PyMuPDF-powered tools to read specific pages or page ranges ("special pages") |
| **Cheap OpenAI Embeddings** | `text-embedding-3-small` — the cheapest high-quality OpenAI embedding model |
| **Hybrid RAG (text + embedding)** | Combines BM25 keyword search + dense embeddings via Reciprocal Rank Fusion (RRF) |
| **Large Chunks** | 4 000-character chunks with 500-char overlap and semantic boundary detection |
| **Optional GPT Reranking** | Uses `gpt-6-luna` to re-rank top candidates for higher precision |
| **Perfect Text Extraction** | PyMuPDF with `sort=True` reading order, block extraction, and table detection |
| **Metadata Tracking** | Every chunk carries `doc_name`, `start_page`, `end_page`, and `chunk_index` |
| **Multi-Document** | Upload and query multiple PDFs simultaneously; compare across documents |
| **Dual Mode** | Switch between agent mode (iterative tool use) and conversational mode (classic Q&A) |
| **Multiple LLM Backends** | OpenAI GPT (default) or Ollama (local) |
| **Persistence** | Save and load FAISS indexes to disk |

---

## Architecture

### Overview

```
User Query
    │
    ▼
┌──────────────────────────────────────────────┐
│           Next.js Frontend (frontend/)             │
│           + FastAPI Backend (backend/)       │
│                                              │
│   Mode: [Agent (Free)] [Conversational]       │
│   Backend: [OpenAI GPT]  Embedding: [text-   │
│   embedding-3-small]  Hybrid: [ON]            │
│   Auth: [Email + password]  DB: [PostgreSQL] │
└──────────────────────────────────────────────┘
    │                    │
    ▼                    ▼
┌──────────────┐    ┌──────────────────────┐
│ FreeAgent    │    │ ConversationChain    │
│ (ReAct Loop) │    │ (gpt-6-luna)        │
└──────┬───────┘    └────────┬─────────────┘
       │                     │
       ▼                     ▼
┌───────────────────────────────────────────────┐
│   DocumentToolKit  │  SmartVectorStore       │
│                                        │
│  ┌─────────────┬───────────┬────────┬───┐ │
│  │ search_docs │ read_page │ summer-│   │ │
│  │             │ read_pages│  ize  │...│ │
│  └─────────────┴───────────┴────────┴───┘ │
│          │                              │
│          ▼                              │
│  ┌────────────────────────────────────┐ │
│  │  Hybrid RAG:                        │ │
│  │  ┌─────────────────────────────┐   │ │
│  │  │ Dense: OpenAI Embeddings   │   │ │
│  │  │ (text-embedding-3-small)    │   │ │
│  │  └─────────────────────────────┘   │ │
│  │  ┌─────────────────────────────┐   │ │
│  │  │ Sparse: BM25 Keyword Search │   │ │
│  │  └─────────────────────────────┘   │ │
│  │  ┌─────────────────────────────┐   │ │
│  │  │ Fusion: Reciprocal Rank     │   │ │
│  │  │ Fusion (RRF)                │   │ │
│  │  └─────────────────────────────┘   │ │
│  │  ┌─────────────────────────────┐   │ │
│  │  │ Re-rank: CrossEncoder       │   │ │
│  │  └─────────────────────────────┘   │ │
│  │  ┌─────────────────────────────┐   │ │
│  │  │ FAISS Vector Store           │   │ │
│  │  └─────────────────────────────┘   │ │
│  └────────────────────────────────────┘ │
└───────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────┐
│  documents/ module                           │
│  ┌──────────────┐   ┌──────────────┐         │
│  │ pdf_loader   │   │ splitter     │         │
│  │ (PyMuPDF     │   │ (LargeChunk  │         │
│  │  + tables)   │   │  + Semantic) │         │
│  └──────────────┘   └──────────────┘         │
└──────────────────────────────────────────────┘
```

### Data Flow

1. **PDF Upload** → `DocumentProcessor` loads PDFs via PyMuPDF with perfect
   text extraction, producing `PDFDocument` objects with per-page text
   and metadata.
2. **Chunking** → `SemanticChunkSplitter` splits pages into large (4 000-char)
   chunks, preserving page boundaries and detecting semantic section breaks.
3. **Embedding** → `SmartEmbedding` creates dense embeddings using OpenAI's
   `text-embedding-3-small` (cheap, 1,536-dim).
4. **Indexing** → `SmartVectorStore` builds FAISS (dense) + BM25 (sparse)
   indexes with rich metadata.
5. **Hybrid Retrieval** → When queried:
   - Dense vector search (FAISS) finds semantically similar chunks
   - BM25 keyword search finds textually matching chunks
   - RRF fusion combines both result lists
    - Optional GPT reranker re-scores final candidates
6. **Agent Loop** → The `FreeAgent` iteratively uses `DocumentToolKit` tools
   (search, read_page, summarize, compare) to build confidence before answering.

---

## Project Structure

```
Caht-With-Document-PDF/
├── backend/                       # FastAPI backend (auth, drive, chat API)
│   ├── server.py                  # FastAPI app — REST + streaming SSE endpoints
│   ├── auth.py                    # bcrypt + JWT auth helpers + dependency
│   ├── db.py                      # PostgreSQL connection pool + helpers
│   ├── rag.py                     # Document processing + RAG orchestration
│   ├── config.py                  # Pydantic-style env config
│   ├── .env                       # Backend env (DB url, JWT secret)
│   └── uploads/                   # Uploaded PDFs (gitignored)
│   └── faiss_indexes/             # FAISS indices on disk (gitignored)
├── frontend/                           # Next.js 15 frontend (TypeScript + Tailwind)
│   ├── src/app/                   
│   │   ├── login/                 # Login / signup
│   │   ├── (protected)/
│   │   │   ├── drive/             # Drive: upload + list documents + session picker
│   │   │   └── chat/[sessionId]/  # Streaming RAG chat
│   │   └── layout.tsx
│   ├── src/components/            # UI primitives + drive/chat components
│   ├── src/lib/                   # API client + shared types
│   ├── src/styles/globals.css
│   ├── .env.local                 # Frontend env (API url)
│   └── tests/e2e.spec.ts          # Playwright end-to-end test
├── documents/                     # PDF loading & chunking (page-aware)
│   ├── __init__.py
│   ├── pdf_loader.py              # PyMuPDF loader with page-level metadata
│   │                             # + table extraction + sorted text
│   ├── splitter.py                # LargeChunkSplitter + SemanticChunkSplitter
│   └── processors.py              # DocumentProcessor pipeline
├── embeddings/                    # Smart embedding & vector store (OpenAI)
│   ├── __init__.py
│   ├── smart_embedding.py         # OpenAI embeddings + RRF hybrid + reranker
│   ├── vectoreStore.py            # SmartVectorStore (FAISS + BM25 wrapper)
│   └── huggingfaceEmbedding.py    # Backwards-compatible factory (OpenAI)
├── chat/                          # Conversation chains (GPT-based)
│   ├── __init__.py
│   └── chatWithVSDB.py            # ConversationChain + factory functions
├── agent/                         # Free autonomous agent
│   ├── __init__.py
│   ├── agent.py                   # FreeAgent (ReAct loop)
│   ├── prompts.py                 # ReAct prompt + output parser
│   └── tools/
│       ├── __init__.py
│       ├── registry.py            # Tool dataclass + ToolRegistry
│       └── document_tools.py      # search, read_page, summarize, etc.
├── tests/                         # Unit tests (91 tests)
│   ├── __init__.py
│   ├── test_pdf_loader.py
│   ├── test_splitter.py
│   ├── test_smart_embedding.py
│   └── test_agent.py
├── .env                           # Root env (OpenAI API key + model)
├── .env-example
├── requirements.txt               # Python dependencies
├── ruff.toml                      # Ruff configuration
├── mypy.ini                       # Mypy configuration
└── README.md                      # This file
```

---

## Installation

### Prerequisites

- Python 3.10+
- Node.js 18+
- Docker (to run the PostgreSQL+pgvector container, or use any Postgres)
- An [OpenAI API key](https://platform.openai.com/api-keys) (for GPT LLM + embeddings)

### Step 1 — Clone & Create Virtual Environment

```bash
git clone <repo-url>
cd Caht-With-Document-PDF
python -m venv venv
source venv/bin/activate     # Linux/macOS
# venv\Scripts\activate      # Windows
```

### Step 2 — Install Python Dependencies (backend)

```bash
pip install -r requirements.txt
```

### Step 3 — Start PostgreSQL + create the schema

```bash
docker run -d --name docuchat_pg \
  -e POSTGRES_PASSWORD=docuchat123 -e POSTGRES_DB=docuchat \
  -p 5436:5432 pgvector/pgvector:pg16

PGPASSWORD=docuchat123 psql -h 127.0.0.1 -p 5436 -U postgres -d docuchat \
  -f backend/schema.sql
```

### Step 4 — Configure Environment

Create the root `.env` (OpenAI key) and `backend/.env` (database):

```env
# .env  (repository root)
OPENAI_API_KEY=sk-...
DEFAULT_MODEL=gpt-6-luna
```

```env
# backend/.env
DATABASE_URL=postgresql://postgres:docuchat123@localhost:5436/docuchat
JWT_SECRET=docuchat-dev-secret-change-me
```

### Step 5 — Install Frontend Dependencies

```bash
cd frontend
npm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8000/api" > .env.local
```

---

## Configuration

### Environment Variables

| Variable | Where | Required | Default | Description |
|---|---|---|---|---|
| `OPENAI_API_KEY` | root `.env` | Yes | — | OpenAI key for GPT + `text-embedding-3-small` |
| `DEFAULT_MODEL` | root `.env` | No | `gpt-6-luna` | LLM used for generation. Note: `gpt-6-luna` only supports `temperature=1`, so the agent/conversation chain leave temperature unset. |
| `EMBEDDING_MODEL` | root `.env` | No | `text-embedding-3-small` | Embedding model (1 536-dim) |
| `DATABASE_URL` | `backend/.env` | Yes | `postgresql://postgres:docuchat123@localhost:5436/docuchat` | PostgreSQL (with the `pgvector` extension) |
| `JWT_SECRET` | `backend/.env` | No | `docuchat-dev-secret-change-me` | HS256 secret for auth tokens |
| `NEXT_PUBLIC_API_URL` | `frontend/.env.local` | Yes | `http://localhost:8000/api` | Backend API base URL seen by the browser |
| `OLLAMA_HOST` | root `.env` | No | — | Ollama server URL (optional LLM fallback) |

> **Backend `.env` setup:** copy `backend/.env` (already populated with dev defaults), then set `DATABASE_URL` / `JWT_SECRET` as needed.

### One-command start (Docker PostgreSQL)

A dedicated Postgres+pgvector container is used for users, documents, chunks,
sessions and messages:

```bash
docker run -d --name docuchat_pg \
  -e POSTGRES_PASSWORD=docuchat123 -e POSTGRES_DB=docuchat \
  -p 5436:5432 pgvector/pgvector:pg16
```

Then create the schema (run once):

```bash
PGPASSWORD=docuchat123 psql -h 127.0.0.1 -p 5436 -U postgres -d docuchat \
  -f backend/schema.sql
```

### Embedding Configuration

The default `SmartEmbeddingConfig` uses:

- **Embedding model**: `text-embedding-3-small` (cheapest OpenAI model, 1,536-dim)
- **Optional GPT reranker**: `gpt-6-luna` for relevance re-scoring (opt-in)
- **Chunk size**: 4 000 characters (vs. original 1 028)
- **Chunk overlap**: 500 characters
- **Hybrid search**: ON by default (BM25 + dense RRF fusion)

To customize:

```python
from embeddings.smart_embedding import SmartEmbedding, SmartEmbeddingConfig

config = SmartEmbeddingConfig(
    embedding_model="text-embedding-3-large",  # more powerful, more expensive
    use_hybrid=True,
    hybrid_alpha=0.5,  # equal weight dense + sparse
    use_rrf=True,
    use_reranker=False,  # disable GPT reranker for cost savings
)
embedding = SmartEmbedding(config)
```

### LLM Configuration

Default: `gpt-6-luna` (cheap + good). For higher quality: `gpt-4o` or `gpt-4-turbo`.

```python
from chat.chatWithVSDB import get_llm

llm = get_llm(model_name="gpt-4o", temperature=0.2)
```

---

## Usage

Run the **backend (FastAPI)** and the **frontend (Next.js)** together. They
communicate over HTTP; the OpenAI key lives only on the backend.

### 1. Start the backend (FastAPI)

```bash
# from the project root, with the venv active
source venv/bin/activate
uvicorn backend.server:app --host 0.0.0.0 --port 8000 --reload
```

API docs: <http://localhost:8000/docs>.

### 2. Start the frontend (Next.js)

```bash
# in a separate terminal
cd frontend
npm install      # first time only
npm run dev      # -> http://localhost:3000
```

### 3. Use the app

1. Open <http://localhost:3000> — explore the landing page, then register or sign in (email + password).
2. **Drive** — click **"Upload document"**, pick a PDF, then **"Upload & process"**.
   The file is extracted, chunked, embedded and indexed (FAISS on disk, chunk
   text persisted in PostgreSQL).
3. Click **"Chat"** on a document → choose **"New conversation"** or pick an
   existing session (sessions are recalled from PostgreSQL).
4. Ask a question. Responses **stream** token-by-token. Switch the mode toggle:
   - **Conversational** — classic retrieval chain.
   - **Agent** — the free ReAct agent that searches, reads specific pages, and
     cross-references before answering.

Sessions, messages and documents are stored in PostgreSQL, so your history
survives restarts.

### Backend API overview

| Method | Route | Purpose |
|---|---|---|
| `POST` | `/api/auth/register` | Create account → returns `accessToken` |
| `POST` | `/api/auth/login` | Login → returns `accessToken` |
| `GET`  | `/api/auth/me` | Current user (Bearer auth) |
| `GET`  | `/api/documents` | List the user's documents |
| `POST` | `/api/documents/upload` | Upload + process a PDF (multipart) |
| `GET`  | `/api/documents/{id}/sessions` | List a document's sessions |
| `POST` | `/api/sessions` | Create a session for a document |
| `GET`  | `/api/sessions/{id}` | Load a session + message history |
| `DELETE` | `/api/sessions/{id}` | Delete a session |
| `POST` | `/api/sessions/{id}/chat` | Streaming chat (SSE, JSON body `{message, mode}`) |

> All routes except `/api/health` require `Authorization: Bearer <accessToken>`.

### Option 2: Python API (backend building blocks)

These modules are reused **as-is** by the FastAPI backend.

#### Document Processing

```python
from documents.processors import DocumentProcessor, ProcessingConfig
from documents.pdf_loader import load_pdfs

# Load PDFs with perfect text extraction + page metadata
documents = load_pdfs(["report.pdf", "manual.pdf"])

# Split into large, metadata-rich chunks
processor = DocumentProcessor(ProcessingConfig(
    use_semantic_split=True,
    chunk_size=4000,
    chunk_overlap=500,
))
chunks = processor.process_documents(documents)
```

#### Smart Embedding + Hybrid Vector Store

```python
from embeddings.smart_embedding import SmartEmbedding, SmartEmbeddingConfig
from embeddings.vectoreStore import SmartVectorStore

embedding = SmartEmbedding(SmartEmbeddingConfig(
    embedding_model="text-embedding-3-small",
    use_hybrid=True,       # BM25 + dense
    use_rrf=True,          # Reciprocal Rank Fusion
    use_reranker=True,     # GPT rerank (extra cost)
))
vs = SmartVectorStore(embedding=embedding).build(chunks)

# Hybrid search: combines keyword + embedding + RRF + rerank
results = vs.search("What are the key findings?", top_k=5)
for doc in results:
    print(f"[p. {doc.metadata['start_page']}] {doc.page_content[:200]}")

# Save for later
vs.save("my_index")
```

#### Free Agent

```python
from langchain_openai import ChatOpenAI
from agent.agent import FreeAgent, AgentConfig
from agent.tools.document_tools import DocumentToolKit

llm = ChatOpenAI(model="gpt-6-luna", temperature=0.3)

tool_kit = DocumentToolKit(
    vector_store=vs,
    documents=documents,
    llm=llm,
)

agent = FreeAgent(
    llm=llm,
    tool_kit=tool_kit,
    config=AgentConfig(max_iterations=8, verbose=True),
)

result = agent.run("Compare the methodology sections across all documents.")

print(result.response)      # The final answer
print(len(result.steps))    # How many tool calls were made
print(result.success)       # Whether it reached a FINAL action
```

#### Conversational Chain

```python
from chat.chatWithVSDB import get_conversation_chain

chain = get_conversation_chain(vs, model_name="gpt-6-luna")

response = chain({"question": "What is the conclusion?"})
print(response["answer"])
```

---

## Agent Mode Explained

The **FreeAgent** implements a ReAct loop. Each iteration:

1. **Think** — The LLM reasons about the question and decides what to do.
2. **Act** — The LLM selects a tool and provides parameters.
3. **Observe** — The tool result is fed back to the LLM.
4. **Repeat** — Steps 1–3 until the agent is confident enough to answer.

### Available Tools

| Tool | Description | Parameters |
|---|---|---|
| `search_documents` | Hybrid search (BM25 + dense + RRF + rerank) | `query`, `top_k` |
| `read_page` | Read a specific page | `doc_name`, `page_num` |
| `read_pages` | Read a page range | `doc_name`, `start_page`, `end_page` |
| `list_documents` | List loaded PDFs | _(none)_ |
| `summarize` | Summarize text | `text` |
| `compare_documents` | Search across all documents | `query`, `top_k_per_doc` |
| `get_metadata` | Get chunk/page metadata | `doc_name`, `page_num` |

### Agent Trace Example

```
Iteration 1
  Thought: The user asks about methodology differences. I should search first.
  Action:  search_documents
  Params:  {"query": "methodology approach", "top_k": 5}
  Observation: Found results in report.pdf (pages 3-4) and manual.pdf (page 7)...

Iteration 2
  Thought: I need to see the exact text on page 3 of report.pdf.
  Action:  read_page
  Params:  {"doc_name": "report.pdf", "page_num": 3}
  Observation: "Our methodology uses a mixed-methods approach..."

Iteration 3
  Thought: Now let me read the corresponding section in manual.pdf.
  Action:  read_pages
  Params:  {"doc_name": "manual.pdf", "start_page": 7, "end_page": 9}
  Observation: "The manual describes a purely quantitative approach..."

Iteration 4
  Thought: I have enough information to compare.
  Action:  FINAL
  Response: The key difference is that report.pdf uses a mixed-methods
            approach (p. 3), while manual.pdf exclusively uses quantitative
            methods (p. 7-9)...
```

---

## Hybrid RAG Explained

The system uses **three complementary retrieval strategies** fused together:

### 1. Dense Retrieval (FAISS)
- Embeds the query with `text-embedding-3-small`
- Finds the top-k most semantically similar chunks via vector similarity
- **Strengths**: Captures semantic meaning, handles synonyms/paraphrasing
- **Weaknesses**: May miss exact term matches, embedding quality limits recall

### 2. Sparse Retrieval (BM25)
- Keyword-based search over chunk text
- Uses traditional TF-IDF + BM25 scoring
- **Strengths**: Exact term matching, good for names/dates/numbers
- **Weaknesses**: Misses semantically related but lexically different text

### 3. Fusion (RRF)
- **Reciprocal Rank Fusion** combines both result lists
- RRF score = `sum(1 / (rank + k))` for each list the doc appears in
- No hyperparameter tuning needed — works well with default `k=60`
- **Strengths**: Robust to individual retrieval method failures

### 4. Optional Cross-Encoder Reranking
- After fusion, top candidates are re-ranked with `gpt-6-luna` for relevance scoring
- Cross-encoders compare query+text jointly for higher precision
- **Strengths**: Best precision for final candidate ordering

```python
# Hybrid search pipeline:
# Query → [Dense FAISS] → top-20
#       → [BM25 sparse] → top-20
#       → [RRF fusion]  → merged + ranked
#       → [CrossEncoder] → final top-k
```

---

## API Reference

### `documents/`

| Module | Key Classes/Functions |
|---|---|
| `pdf_loader` | `load_pdf()`, `load_pdfs()`, `extract_page_text()`, `PDFDocument`, `PageText` |
| `splitter` | `LargeChunkSplitter`, `SemanticChunkSplitter`, `split_documents()` |
| `processors` | `DocumentProcessor`, `ProcessingConfig` |

### `embeddings/`

| Module | Key Classes/Functions |
|---|---|
| `smart_embedding` | `SmartEmbedding`, `SmartEmbeddingConfig` (OpenAI + RRF hybrid) |
| `vectoreStore` | `SmartVectorStore`, `VectorStoreConfig` |
| `huggingfaceEmbedding` | `get_vectore_db()`, `get_embedding_model()` |

### `chat/`

| Module | Key Classes/Functions |
|---|---|
| `chatWithVSDB` | `ConversationChain`, `get_conversation_chain()`, `get_llm()` |

### `agent/`

| Module | Key Classes/Functions |
|---|---|
| `agent` | `FreeAgent`, `AgentConfig`, `AgentResult` |
| `tools.registry` | `Tool`, `ToolRegistry` |
| `tools.document_tools` | `DocumentToolKit` (7 tools) |
| `prompts` | `SYSTEM_PROMPT`, `REACT_PROMPT`, `parse_agent_output()` |

---

## Development

### Running Tests

```bash
pytest tests/ -v
```

### Adding a New Tool

1. Add a method to `DocumentToolKit` in `agent/tools/document_tools.py`
2. Register it in `DocumentToolKit.register_all()`
3. Add tests in `tests/test_agent.py`

```python
# In DocumentToolKit
def my_tool(self, param: str) -> str:
    """Description of what this tool does."""
    result = ...  # your logic
    return str(result)

# In register_all()
registry.register(
    Tool(
        name="my_tool",
        description="...",
        parameters={"type": "object", "properties": {"param": {"type": "string"}}, "required": ["param"]},
        func=self.my_tool,
    )
)
```

### Linting

```bash
ruff check .
ruff format .
mypy .
```

### Key Design Decisions

1. **PyMuPDF over PyPDF2** — Better text extraction quality, native page-level
   access, table detection, and `sort=True` for correct reading order.
2. **4 000-char chunks** — Large enough to preserve document context, small
   enough for effective retrieval. Semantic splitting ensures chunks break at
   logical section boundaries.
3. **OpenAI `text-embedding-3-small`** — Cheapest high-quality embedding model.
   1,536-dim with excellent retrieval performance.
4. **Hybrid RAG with RRF** — Combines the strengths of dense (semantic) and
   sparse (keyword) retrieval. RRF is parameter-free and robust.
5. **gpt-6-luna** — Cost-effective LLM with strong reasoning for the agent loop.
6. **Custom ReAct loop** — Full control over the agent's reasoning process,
   rather than relying on opaque LangChain abstractions.

---

## License

This project is provided as-is for educational and research purposes.

---

*Powered by OpenAI • FAISS • PyMuPDF • Hybrid RAG (BM25 + text-embedding-3-small) • Cross-Encoder Reranking*

## Product workspace update

The public `/` route is now a landing page. Sign in or create an account at `/login` to use:

- `/drive`: workspace overview with live document, conversation, page/section, and storage counts; recent chats; AI shortcuts; document search, type filters, sorting, and grid/list views.
- `/drive?view=documents`: document library.
- `/conversations`: searchable conversation history.
- `/agents`: AI studio with executive summary, research, data extraction, and action-item workflows. Selecting a workflow prepares an editable prompt in a new conversation; it does not send automatically.
- `/chat/[sessionId]`: streamed document chat or research agent, configurable answer length and enabled model, a source text reader, response copying, and Markdown export. Stop cancels the browser request; an already-running provider/tool call may still complete on the server.

### Supported files

Upload PDF, Word **DOCX**, Excel **XLSX / XLS**, CSV, TXT, or Markdown files up to **25 MB**. Word tables are included in document order. Excel worksheet names and original row numbers are preserved; large sheets use sections of 150 nonempty rows. Formula text is retained in XLSX and is **not executed or recalculated**. Old binary Word `.doc` files must be saved as `.docx` first. Scanned PDF images need OCR before upload; image OCR is not included.

PDF citations refer to physical pages. Word/text citations refer to logical text sections, and spreadsheet citations refer to worksheet sections, not printed pages. The source panel displays extracted text rather than a visual Office/PDF renderer. The research agent searches and reads the selected document; it does not browse the web.

### Model configuration and persistence

`DEFAULT_MODEL` is always available in the chat model selector. Set `CHAT_MODELS` to a comma-separated list of additional model IDs supported by your configured provider. The server validates model choices. Existing OpenAI-compatible provider configuration remains in use. Restart the backend after changing these values.

```bash
# Install updated parsing dependencies locally
venv/bin/pip install -r requirements.txt
cd frontend
npm ci
```

For Docker, rebuild with `docker compose up -d --build`. Uploaded sources and index directories now use named volumes so newly uploaded files survive backend container recreation. If an earlier container already holds uploads in its writable layer, copy those files out before recreating it and restore them into the upload volume; database metadata alone cannot restore original file contents.

### Verification

```bash
venv/bin/pytest -q
venv/bin/ruff check backend tests
cd frontend
npm run lint
npx tsc --noEmit
npm run build
```

Loader regression tests cover Word paragraph/table order, worksheet names and row numbering, formulas and zero values, CSV quoting, Unicode text, PDF routing, and empty/unsupported files. API tests cover model/mode validation, source ownership, scoped conversation listing, upload limits, message-history ordering, streamed answer persistence, and cleanup after a failed parse.
