# 3GPP RAG Chatbot

A Retrieval-Augmented Generation chatbot over 3GPP telecom specifications,
built for minimal-to-near-zero hallucination, with a LangGraph pipeline
and per-thread persistent memory.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# edit .env and put your OpenAI key in OPENAI_API_KEY
```

## Run

```bash
cd src
python main.py
```

API starts on `http://localhost:8000`. Then, in a separate terminal:

```bash
cd ui
npm install
cp .env.example .env
npm run dev
```

UI opens on `http://localhost:5173`.

## How it works

1. **Upload a PDF** from the sidebar. The backend loads it, chunks it by
   3GPP clause, embeds the chunks, and stores them in a per-thread FAISS +
   BM25 index. The document appears as a card inside the chat thread once
   indexing completes.
2. **Ask a question.** The LangGraph pipeline runs:
   - `chat_node` always runs first. If this thread has no indexed
     document, it answers directly as a plain chatbot and the graph ends.
   - If the thread *does* have an index, `chat_node` defers and the graph
     routes to `rag_node`, which does hybrid retrieval (dense + BM25) +
     LLM rerank + citation-forced generation + a groundedness check.
3. **Conversation memory** persists per `thread_id` via LangGraph's
   `SqliteSaver` checkpointer (`data/checkpoints.sqlite`). Refreshing the
   page or returning later resumes the same thread automatically (the
   frontend keeps `thread_id` in `localStorage`).

```
START -> chat_node -> (thread has an index?)
                          |-- no  --> END        (plain chatbot answer)
                          |-- yes --> rag_node -> END   (grounded, cited answer)
```

## Architecture summary

**Chunking (`src/ingest.py`)** — clause-aware, not fixed-size. Parses 3GPP
clause numbering (e.g. `5.2.1.3`) out of the PDF text, tags every chunk
with `spec_id`, `clause_num`, `title`, `page`. Long clauses sub-split at
sentence boundaries with clean overlap.

**Per-thread vector stores (`src/thread_store.py`)** — each conversation
thread has its own FAISS + BM25 index, built from whatever the user
uploads in that thread. Persisted to `data/threads/<thread_id>/` so it
survives a server restart.

**Retrieval (`src/retrieval.py`)** — hybrid dense (FAISS) + sparse (BM25)
search, merged and deduplicated, then reranked by an LLM call
(`gpt-4o-mini`).

**Generation (`src/generate.py`)** — citation-forced prompting (`gpt-4o`,
temperature 0) + an independent groundedness check (`gpt-4o-mini`) that
flags unsupported claims.

**Graph (`src/graph.py`)** — LangGraph `StateGraph` wiring the two nodes
above, compiled with a `SqliteSaver` checkpointer keyed by `thread_id`.

**API (`src/main.py`)** — FastAPI with `/upload`, `/chat`,
`/thread/{id}/status`, `/thread/{id}/history`, `/thread/new`.

**UI (`ui/`)** — React + Vite. Sidebar PDF upload with a real progress
bar, in-chat PDF cards, citation pills, and a signal-bars indicator that
shows grounding strength per answer.

## Files

```
src/
  ingest.py       PDF loading + clause-aware chunking
  thread_store.py Per-thread FAISS/BM25 index management
  retrieval.py    Hybrid retrieval + rerank
  generate.py     Citation-forced generation + groundedness check
  graph.py        LangGraph pipeline + SQLite checkpointer
  main.py         FastAPI backend
ui/
  src/            React app (see ui/README.md)
data/
  raw/            Sample 3GPP PDF for manual testing
  threads/        Per-thread vector indexes (created at runtime)
  checkpoints.sqlite   LangGraph conversation history (created at runtime)
```

