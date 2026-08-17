"""
FastAPI backend for the 3GPP RAG chatbot - LangGraph edition.

Flow:
  - Conversation state and history persist per thread_id via LangGraph's
    SqliteSaver checkpointer. The frontend generates a thread_id once and
    reuses it, so refreshing or returning later resumes exactly where the
    user left off.
  - Each thread has its own vector store (per-thread isolation). Uploading
    a PDF via /upload ingests it (load -> chunk -> embed -> store) into
    that thread's index only.
  - /chat runs one turn of the graph: chat_node always runs first; if the
    thread has an index, it defers to rag_node for a grounded, cited
    answer; otherwise chat_node's own plain answer is final.

Endpoints:
  POST /upload          - upload + ingest a PDF into this thread's vector store
  POST /chat             - ask a question (runs the LangGraph turn)
  GET  /thread/{id}/history - resume: fetch full message history for a thread
  GET  /thread/{id}/status  - whether this thread has an index, doc list, chunk count
  GET  /health            - liveness check
"""

import json
import os
import shutil
import uuid
from pathlib import Path
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv

from graph import run_turn, get_thread_history, stream_turn
from thread_store import add_document, has_index, list_documents, chunk_count

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="3GPP RAG Chatbot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://mavenir-rag-chatbot.vercel.app/",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    query: str
    thread_id: str


class ChatResponse(BaseModel):
    answer: str
    grounded: bool
    flagged_claims: list[str]
    sources: list[str]
    mode: str


class UploadResponse(BaseModel):
    filename: str
    num_chunks: int
    documents: list[str]


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/upload", response_model=UploadResponse)
async def upload_pdf(thread_id: str, file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    thread_upload_dir = UPLOAD_DIR / thread_id
    thread_upload_dir.mkdir(parents=True, exist_ok=True)
    dest_path = thread_upload_dir / file.filename

    with open(dest_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        result = add_document(thread_id, str(dest_path), file.filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process PDF: {e}")

    return UploadResponse(
        filename=file.filename,
        num_chunks=result["num_chunks"],
        documents=result["filenames"],
    )


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    try:
        result = run_turn(req.thread_id, req.query)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return ChatResponse(
        answer=result["answer"],
        grounded=result["grounded"],
        flagged_claims=result["flagged_claims"],
        sources=result["sources"],
        mode=result["mode"],
    )


@app.post("/chat/stream")
def chat_stream(req: ChatRequest):
    def event_generator():
        try:
            for event in stream_turn(req.thread_id, req.query):
                yield f"data: {json.dumps(event)}\n\n"

            done_event = {"type": "done"}
            yield f"data: {json.dumps(done_event)}\n\n"

        except Exception as e:
            error_event = {
                "type": "error",
                "message": str(e),
            }
            yield f"data: {json.dumps(error_event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/thread/{thread_id}/history")
def thread_history(thread_id: str):
    return {"messages": get_thread_history(thread_id)}


@app.get("/thread/{thread_id}/status")
def thread_status(thread_id: str):
    return {
        "indexed": has_index(thread_id),
        "documents": list_documents(thread_id),
        "num_chunks": chunk_count(thread_id),
    }


@app.post("/thread/new")
def new_thread():
    return {"thread_id": str(uuid.uuid4())}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
