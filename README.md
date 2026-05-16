# 📚 NotesRAG-Chatbot

A production-ready, Python-only **Retrieval-Augmented Generation (RAG)** chatbot for structured academic notes — powered by **Anthropic Claude**, **FAISS**, and **SentenceTransformers**, with a Flask backend and a Streamlit frontend, plus a basic **Multi-Party Computation (MPC)** module for privacy-preserving query simulation.

---

## ✨ Features

- Ingest **PDF / DOCX / URL / OneNote-JSON** notes into a hierarchical database (*Subject → Unit → Topic → Subtopic → Note*).
- Token-aware overlapping **chunking** with metadata preservation.
- Local-first **FAISS** vector store using normalised `bge-large-en-v1.5` embeddings.
- **Claude API** answer generation with retrieval-grounded prompt templates.
- REST API (Flask blueprints) — upload, query, search, browse.
- **Streamlit** chat UI with file upload, semantic search, hierarchy browser, chat history, typing indicator, and an MPC toggle.
- Lightweight **MPC simulation** (`mpc_module/`) demonstrating additive-shared inner-product retrieval across multiple parties.
- Solid engineering hygiene: pydantic-settings config, structured logging, type hints, docstrings, modular blueprints, validation, retries, tests.

---

## 🏗 Architecture

```
                     ┌─────────────────────────────────────────┐
                     │           Streamlit Frontend            │
                     │   chat · upload · search · browse · mpc │
                     └───────────────┬─────────────────────────┘
                                     │  HTTP/JSON
                                     ▼
                     ┌─────────────────────────────────────────┐
                     │              Flask API                  │
                     │  /upload  /query  /search  /subjects    │
                     │  /units   /topics /health               │
                     └────┬─────────────────┬──────────────────┘
                          │                 │
                          ▼                 ▼
       ┌──────────────────────────┐  ┌─────────────────────────────┐
       │   Ingestion Pipeline     │  │       RAG Pipeline          │
       │ PDF / DOCX / URL / JSON  │  │  chunk → embed → FAISS      │
       │  ↓ clean ↓ hierarchy     │  │  retrieve → Claude answer   │
       └────────────┬─────────────┘  └─────────┬───────────────────┘
                    │                          │
                    ▼                          ▼
          ┌────────────────────┐      ┌──────────────────────────┐
          │  SQL DB (ORM)      │      │   FAISS Index + Meta     │
          │  Subject/Unit/...  │      │   (storage/faiss_index/) │
          └────────────────────┘      └──────────────────────────┘
                          │
                          ▼
                 ┌───────────────────────┐
                 │   MPC Module (sim.)   │
                 │  shared inner-product │
                 └───────────────────────┘
```

---

## 📂 Folder Structure

```
notes-rag-chatbot/
├── api/                       # Flask app factory + blueprints
│   ├── blueprints/
│   │   ├── health.py
│   │   ├── upload.py
│   │   ├── query.py
│   │   ├── search.py
│   │   └── notes_browse.py
│   └── errors.py
├── frontend/
│   ├── streamlit_app/
│   │   ├── main.py            # Streamlit UI entrypoint
│   │   └── api_client.py
│   ├── templates/index.html   # Minimal Flask template fallback
│   └── static/style.css
├── database/
│   ├── models.py              # SQLAlchemy ORM models
│   ├── repository.py          # Thin CRUD helpers
│   ├── session.py             # Engine, sessions, init_db()
│   └── migrations/            # Alembic-ready directory
├── rag_pipeline/
│   ├── chunker.py             # Token-aware overlapping chunker
│   ├── embeddings.py          # SentenceTransformer wrapper
│   ├── vector_store.py        # FAISS index + on-disk persistence
│   ├── pipeline.py            # build_vector_index / similarity_search / retrieve_context
│   ├── claude_client.py       # Anthropic SDK wrapper (retries)
│   └── response_generator.py  # Prompt templates
├── data_ingestion/
│   ├── pdf_loader.py
│   ├── docx_loader.py
│   ├── url_loader.py
│   ├── onenote_loader.py
│   └── pipeline.py
├── mpc_module/
│   ├── secret_sharing.py
│   ├── parties.py
│   ├── secure_query.py
│   └── README.md
├── storage/
│   ├── raw_files/             # Original uploaded files
│   ├── processed/
│   └── faiss_index/           # FAISS .index + meta pickle
├── utils/
│   ├── logger.py
│   ├── text_cleaning.py
│   ├── hashing.py
│   └── validators.py
├── logs/
├── scripts/
│   └── batch_ingest.py           # CLI batch-ingest tool
├── tests/
├── config/settings.py
├── app.py                     # Flask entrypoint
├── requirements.txt
├── .env.example
└── README.md
```

---

## 🚀 Quick Start

### 1. Clone & install

```bash
git clone <repo-url> notes-rag-chatbot && cd notes-rag-chatbot
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY
```

| Variable             | Default                          | Notes                                    |
| -------------------- | -------------------------------- | ---------------------------------------- |
| `DATABASE_URL`       | `sqlite:///./storage/notes.db`   | Set to a Postgres URL in production       |
| `ANTHROPIC_API_KEY`  | _empty_                          | Required for `/query`                    |
| `CLAUDE_MODEL`       | `claude-sonnet-4-6`              | Any Anthropic chat model                 |
| `EMBEDDING_MODEL`    | `BAAI/bge-large-en-v1.5`         | First run downloads the model            |
| `CHUNK_SIZE`         | `800`                            | Tokens per chunk                         |
| `CHUNK_OVERLAP`      | `120`                            | Token overlap                            |
| `TOP_K`              | `5`                              | Retrieval depth                          |
| `MPC_NUM_PARTIES`    | `3`                              | Simulated parties for MPC mode           |

### 3. Run the backend

```bash
python app.py
# or for production:
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### 4. Run the frontend

```bash
streamlit run frontend/streamlit_app/main.py
```

The Streamlit app expects the Flask API to be reachable at `API_BASE_URL` (default `http://localhost:5000`).

---

## 🔑 Claude API Setup

1. Create an account at [console.anthropic.com](https://console.anthropic.com/).
2. Generate an API key.
3. Put it in `.env`:
   ```env
   ANTHROPIC_API_KEY=sk-ant-...
   CLAUDE_MODEL=claude-sonnet-4-6
   ```
4. The `ClaudeClient` (in `rag_pipeline/claude_client.py`) handles retries with exponential backoff and converts Anthropic SDK exceptions into a friendly `ClaudeAPIError`.

---

## 🗄 Database Setup

By default the app uses **SQLite** (zero-config). For PostgreSQL:

```bash
createdb notesrag
# .env
DATABASE_URL=postgresql+psycopg2://user:pass@localhost:5432/notesrag
```

Tables are created automatically on startup via `database.session.init_db()`. The hierarchy:

```
Subject ── 1:N ── Unit ── 1:N ── Topic ── 1:N ── Subtopic ── 1:N ── Note
                                                                   │
                                                                   ├── Source (PDF/URL/…)
                                                                   └── Tags
```

Indexes cover every foreign key, `notes.embedding_id`, `notes.content_hash`, `sources.checksum`, and `tags.name`.

---

## 🧠 FAISS Explanation

We use **`faiss.IndexFlatIP`** because all embeddings are L2-normalised — inner product on normalised vectors equals cosine similarity. The index and a parallel pickle of `_Record` metadata are persisted under `storage/faiss_index/`. When the corpus grows beyond a few hundred thousand chunks you can swap in `IndexHNSWFlat` or `IndexIVFPQ` by changing one method in `rag_pipeline/vector_store.py`.

---

## 🔐 MPC Overview

The `mpc_module/` package demonstrates how RAG could work when no single party holds the entire corpus or query:

- The query embedding is split into **N additive shares** (`Σ shares = query`).
- Each `Party` owns a horizontal slice of the note vectors.
- Each party computes partial inner products on its slice.
- Scores are reconstructed and a top-k list is sent to Claude for answer generation.

It is **educational, not production cryptography** — see `mpc_module/README.md` for limitations and the path to plugging in **PySyft**, **SecretFlow**, or **MP-SPDZ**.

Toggle MPC retrieval from the Streamlit sidebar or by passing `"use_mpc": true` to `/query`.

---

## 📡 API Documentation

### `GET /health`
Returns API status and active model names.

### `POST /upload`  *(multipart/form-data)*
Upload one PDF / DOCX / OneNote-JSON file.

| Field        | Required | Description                                    |
| ------------ | -------- | ---------------------------------------------- |
| `file`       | ✅       | Binary file                                    |
| `subject`    | ✅       | Subject name (created if missing)              |
| `unit`       | ✅       | Unit / chapter                                 |
| `topic`      | ✅       | Topic name                                     |
| `subtopic`   | ✅       | Subtopic name                                  |
| `difficulty` |          | `easy` / `medium` / `hard` (default `medium`)  |
| `tags`       |          | Comma-separated                                |

Response:
```json
{
  "source_id": 12,
  "title": "Lecture 3 – Scheduling",
  "source_type": "pdf",
  "note_count": 14,
  "chunks_indexed": 39,
  "duplicate": false
}
```

### `POST /upload/url`  *(application/json)*
```json
{
  "url": "https://en.wikipedia.org/wiki/CPU_scheduling",
  "subject": "OS", "unit": "Processes", "topic": "Scheduling", "subtopic": "RR",
  "tags": "cpu,rr"
}
```

### `POST /query`  *(application/json)*
```json
{
  "query": "Explain context switching overhead",
  "top_k": 5,
  "use_mpc": false,
  "history": [
    {"role": "user", "content": "What is preemption?"},
    {"role": "assistant", "content": "Preemption is..."}
  ]
}
```

Response:
```json
{
  "answer": "Context switching overhead refers to ... [Source 1]",
  "sources": [
    {"note_id": 42, "score": 0.81, "excerpt": "…", "metadata": {...}}
  ],
  "retrieval_count": 5
}
```

### `GET /subjects` · `GET /units?subject_id=` · `GET /topics?unit_id=`
Returns hierarchy nodes for the browse UI.

### `GET /search?q=...&mode=semantic|text&limit=10`
- `mode=semantic` — runs FAISS retrieval (default).
- `mode=text` — SQL `ILIKE` fallback.

---

## 📥 Ingesting PDFs (notes / Q&A / handwritten / quiz / exam)

The PDF pipeline supports five **content types**:

| Type          | When to use                                           | Behaviour                                              |
| ------------- | ----------------------------------------------------- | ------------------------------------------------------ |
| `notes`       | Lecture notes, textbook prose                         | Page-by-page text extraction (default)                 |
| `qna`         | Question-and-answer documents                         | Detects `Q…/A…` pairs, stores each as one structured note |
| `handwritten` | Scanned or handwritten PDFs                           | Forces Tesseract OCR on every page                     |
| `quiz`        | Short-form quizzes                                    | Q&A parser + tagged as `type:quiz`                     |
| `exam`        | Exam papers with marks                                | Q&A parser + captures `marks` per question             |

The Q&A parser detects:

- `Q1.` / `Q.1` / `Q 1:` / `Question 2:` / `Quiz 3:` / `1)` numbered lists
- `Ans:` / `Answer:` / `Sol:` / `Solution:` / `A.`
- Marks annotations: `[5 marks]`, `(10 points)`, `[2 pts]`
- Section/Part headings: `Section A`, `Part B`, etc.

Each detected Q&A pair becomes its own `Note` row with `question`, `answer`, `marks`, and `content_type` populated — so retrieval can rank quiz/exam questions independently of lecture prose.

### OCR Setup (handwritten PDFs)

1. Install the Tesseract binary on your machine:
   - **macOS**: `brew install tesseract`
   - **Ubuntu/Debian**: `sudo apt-get install tesseract-ocr`
   - **Windows**: download from [UB-Mannheim Tesseract](https://github.com/UB-Mannheim/tesseract/wiki)
2. Install the Python bindings (already in `requirements.txt`): `pip install pytesseract Pillow`
3. Optionally set `TESSERACT_LANG=eng+hin` (or any installed lang pack) in `.env`.

### Batch ingest from a folder

The `scripts/batch_ingest.py` CLI walks a folder of PDFs and pushes each one through the full pipeline (extract → parse → chunk → embed → index):

```bash
# Auto-infer content type from filenames (handwritten*, quiz*, exam*, qna*, …)
python -m scripts.batch_ingest   --path "/path/to/your/pdfs"   --subject "Operating Systems"   --unit   "Core Concepts"   --recursive

# Force a content type for the whole batch
python -m scripts.batch_ingest   --path ./study_pdfs/handwritten   --subject "Operating Systems" --unit "Memory"   --topic "Paging" --subtopic "Lecture Notes"   --content-type handwritten   --force-ocr

# Dry-run to preview which file gets which type
python -m scripts.batch_ingest --path ./pdfs --subject OS --unit Core --dry-run
```

Filename-based inference:

| Pattern in filename                | Inferred type   |
| ---------------------------------- | --------------- |
| `*handwritten*`, `*scan*`          | `handwritten`   |
| `*quiz*`                           | `quiz`          |
| `*exam*`, `*midterm*`, `*final*`   | `exam`          |
| `*qna*`, `*q&a*`, `*questions*`    | `qna`           |
| everything else                    | `notes`         |

Already-ingested files are skipped (matched by SHA-256 checksum).

### Via Streamlit UI

The upload page now includes a **Content type** dropdown and a **Force OCR** toggle. Selecting `handwritten` automatically OCRs every page.

### Via API

```bash
curl -F "file=@midterm.pdf"      -F "subject=OS" -F "unit=Core" -F "topic=Paging" -F "subtopic=Midterm"      -F "content_type=exam"      -F "force_ocr=false"      -F "tags=midterm,fall26"      http://localhost:5000/upload
```

---

## 🧪 Tests

```bash
pytest -q
```

Tests cover:
- Chunker correctness & overlap.
- Text cleaning edge cases.
- SQLAlchemy model round-trip.
- MPC secret-sharing round-trip.
- Flask `/health` and `/` endpoints.

The Anthropic SDK and the embedding model are **not** required to run the test suite (they're lazy-loaded).

---

## 🖼 Screenshots

> Place your captured PNGs in `docs/screenshots/` and they'll render here.

- `docs/screenshots/chat.png` — Chat with citations
- `docs/screenshots/upload.png` — Upload UI
- `docs/screenshots/browse.png` — Hierarchy browser
- `docs/screenshots/mpc.png` — MPC-mode query

---

## 🛠 Example Workflow

```bash
# 1. Boot backend
python app.py

# 2. Ingest a PDF
curl -F "file=@lecture3.pdf" \
     -F "subject=Operating Systems" \
     -F "unit=Processes" \
     -F "topic=Scheduling" \
     -F "subtopic=Round Robin" \
     -F "tags=cpu,rr" \
     http://localhost:5000/upload

# 3. Ask a question
curl -X POST http://localhost:5000/query \
     -H 'Content-Type: application/json' \
     -d '{"query":"Why does RR with very small quantum perform poorly?"}'
```

---

## 🔭 Future Improvements

- **Streaming responses** via Anthropic's `messages.stream`.
- Swap FAISS Flat → HNSW once corpus > 100k chunks.
- Real MPC backend: integrate **PySyft** or **MP-SPDZ** behind the existing `secure_query()` interface.
- Per-user namespaces & auth (JWT).
- Background ingestion via Celery + Redis.
- Automatic taxonomy suggestion using Claude to propose Subject/Unit/Topic from an uploaded file.
- Multi-modal notes (images, equations via LaTeX parsing).
- Re-rankers (e.g., `bge-reranker-large`) on top of top_k FAISS candidates.

---

## 📜 License

MIT — see `LICENSE` (not included).
