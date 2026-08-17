import os
import pickle
import shutil
from pathlib import Path
from typing import Optional

from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from rank_bm25 import BM25Okapi

from ingest import ingest_pdf, Chunk
from retrieval import chunks_to_documents, EMBEDDING_MODEL

BASE_DIR = Path(__file__).resolve().parent.parent
THREAD_STORE_DIR = BASE_DIR / "data" / "threads"

# In-process cache: thread_id -> {"vectorstore", "bm25", "docs", "filenames"}
_registry: dict[str, dict] = {}


def _thread_dir(thread_id: str) -> Path:
    d = THREAD_STORE_DIR / thread_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def has_index(thread_id: str) -> bool:
    """True if this thread has an in-memory or on-disk index."""
    if thread_id in _registry:
        return True
    return (_thread_dir(thread_id) / "faiss_index").exists()


def get_index(thread_id: str) -> Optional[dict]:
    """Load (from cache or disk) the index for a thread. None if none exists."""
    if thread_id in _registry:
        return _registry[thread_id]

    tdir = _thread_dir(thread_id)
    faiss_path = tdir / "faiss_index"
    bm25_path = tdir / "bm25.pkl"
    docs_path = tdir / "docs.pkl"
    meta_path = tdir / "filenames.pkl"

    if not faiss_path.exists():
        return None

    embeddings = OpenAIEmbeddings(model=EMBEDDING_MODEL)
    vectorstore = FAISS.load_local(
        str(faiss_path), embeddings, allow_dangerous_deserialization=True
    )
    with open(bm25_path, "rb") as f:
        bm25 = pickle.load(f)
    with open(docs_path, "rb") as f:
        docs = pickle.load(f)
    filenames = []
    if meta_path.exists():
        with open(meta_path, "rb") as f:
            filenames = pickle.load(f)

    entry = {
        "vectorstore": vectorstore,
        "bm25": bm25,
        "docs": docs,
        "filenames": filenames,
    }
    _registry[thread_id] = entry
    return entry


def add_document(thread_id: str, pdf_path: str, filename: str) -> dict:
    new_chunks: list[Chunk] = ingest_pdf(pdf_path)

    if not new_chunks:
        raise ValueError(
            "No text could be extracted from the PDF. "
            "The PDF may be scanned/image-based, empty, or unsupported."
        )

    new_docs = chunks_to_documents(new_chunks)

    if not new_docs:
        raise ValueError(
            "PDF text was extracted, but no documents were created from the chunks."
        )

    existing = get_index(thread_id)
    embeddings = OpenAIEmbeddings(model=EMBEDDING_MODEL)

    if existing:
        existing["vectorstore"].add_documents(new_docs)

        all_docs = existing["docs"] + new_docs
        filenames = existing["filenames"] + [filename]
        vectorstore = existing["vectorstore"]

    else:
        vectorstore = FAISS.from_documents(
            new_docs,
            embeddings,
        )

        all_docs = new_docs
        filenames = [filename]

    tokenized = [
        d.page_content.lower().split() for d in all_docs if d.page_content.strip()
    ]

    if not tokenized:
        raise ValueError("No usable text was found in the PDF after processing.")

    bm25 = BM25Okapi(tokenized)

    entry = {
        "vectorstore": vectorstore,
        "bm25": bm25,
        "docs": all_docs,
        "filenames": filenames,
    }

    _registry[thread_id] = entry

    tdir = _thread_dir(thread_id)

    vectorstore.save_local(str(tdir / "faiss_index"))

    with open(tdir / "bm25.pkl", "wb") as f:
        pickle.dump(bm25, f)

    with open(tdir / "docs.pkl", "wb") as f:
        pickle.dump(all_docs, f)

    with open(tdir / "filenames.pkl", "wb") as f:
        pickle.dump(filenames, f)

    return {
        "num_chunks": len(all_docs),
        "filenames": filenames,
    }


def list_documents(thread_id: str) -> list[str]:
    entry = get_index(thread_id)
    return entry["filenames"] if entry else []


def chunk_count(thread_id: str) -> int:
    entry = get_index(thread_id)
    return len(entry["docs"]) if entry else 0
