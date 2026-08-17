"""
Hybrid retrieval + rerank for the 3GPP RAG chatbot.

Why hybrid (dense + BM25) instead of dense-only:
3GPP text is dense with short exact-match identifiers (5QI, AMF, N2, PDU
Session, QFI ...). Embedding similarity blurs short acronyms together;
BM25 nails exact keyword/identifier matches that embeddings miss. We
retrieve candidates from both, merge, then rerank.

Why rerank:
Top-k by raw embedding similarity is noisy on technical text. A cheap
LLM-based rerank re-scores the merged candidate pool for *actual*
relevance to the query before we hand the final context to the answer
generator - this measurably reduces irrelevant-context hallucination.

Note: vector store construction/loading now lives in thread_store.py
(per-thread indexes, keyed by thread_id). This module only holds the
document-conversion helper and the retrieval/rerank logic shared across
threads.
"""

from dataclasses import dataclass
from typing import List

from langchain_openai import ChatOpenAI
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv
from ingest import Chunk
load_dotenv()

EMBEDDING_MODEL = "text-embedding-3-small"  # full 1536 dims - do NOT truncate

_rerank_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)


def chunks_to_documents(chunks: List[Chunk]) -> List[Document]:
    return [
        Document(
            page_content=c.text,
            metadata={
                "spec_id": c.spec_id,
                "clause_num": c.clause_num,
                "title": c.title,
                "page": c.page,
            },
        )
        for c in chunks
    ]


@dataclass
class RetrievedChunk:
    text: str
    spec_id: str
    clause_num: str
    title: str
    page: int
    score: float = 0.0


def hybrid_retrieve(
    query: str,
    vectorstore,
    bm25,
    docs: List[Document],
    dense_k: int = 15,
    sparse_k: int = 15,
) -> List[RetrievedChunk]:
    """Merge dense (FAISS) and sparse (BM25) candidates, dedup by content."""
    dense_hits = vectorstore.similarity_search_with_score(query, k=dense_k)

    tokenized_query = query.lower().split()
    bm25_scores = bm25.get_scores(tokenized_query)
    sparse_ranked_idx = sorted(
        range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True
    )[:sparse_k]

    seen = {}
    for doc, score in dense_hits:
        key = doc.page_content
        seen[key] = RetrievedChunk(
            text=doc.page_content,
            spec_id=doc.metadata["spec_id"],
            clause_num=doc.metadata["clause_num"],
            title=doc.metadata["title"],
            page=doc.metadata["page"],
            score=1.0 / (1.0 + score),  # lower FAISS distance = better, invert
        )

    for i in sparse_ranked_idx:
        doc = docs[i]
        key = doc.page_content
        if key not in seen:
            seen[key] = RetrievedChunk(
                text=doc.page_content,
                spec_id=doc.metadata["spec_id"],
                clause_num=doc.metadata["clause_num"],
                title=doc.metadata["title"],
                page=doc.metadata["page"],
                score=float(bm25_scores[i]),
            )

    return list(seen.values())


def rerank(query: str, candidates: List[RetrievedChunk], top_n: int = 5) -> List[RetrievedChunk]:
    """
    Cheap LLM-based relevance rerank using LangChain's ChatOpenAI (gpt-4o-mini).
    Ask the model to score each candidate 0-10 for relevance to the query,
    keep the top_n. This is the step that fixes noisy embedding-similarity
    ordering before generation - dense similarity alone is not a reliable
    relevance signal on short, acronym-heavy technical text.
    """
    if len(candidates) <= top_n:
        return candidates

    numbered = "\n\n".join(
        f"[{i}] (Clause {c.clause_num} - {c.title})\n{c.text[:500]}"
        for i, c in enumerate(candidates)
    )
    prompt = f"""Query: {query}

Below are numbered passages from 3GPP specifications. Score each passage 0-10
for how directly relevant and useful it is for answering the query.
Respond ONLY with lines of the form "index:score", one per passage, nothing else.

{numbered}"""

    response = _rerank_llm.invoke([HumanMessage(content=prompt)])
    text = response.content

    scores = {}
    for line in text.strip().splitlines():
        line = line.strip()
        if ":" not in line:
            continue
        idx_str, score_str = line.split(":", 1)
        try:
            idx = int(idx_str.strip())
            score = float(score_str.strip())
            scores[idx] = score
        except ValueError:
            continue

    ranked = sorted(
        range(len(candidates)),
        key=lambda i: scores.get(i, 0),
        reverse=True,
    )[:top_n]

    return [candidates[i] for i in ranked]
