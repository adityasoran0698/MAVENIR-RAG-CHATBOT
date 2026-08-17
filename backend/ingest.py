"""
Ingestion + clause-aware chunking for 3GPP spec PDFs.

Why not RecursiveCharacterTextSplitter alone:
3GPP specs are numbered outlines (5.2.1, 5.2.1.1 ...) with tables and
cross references. Blind character/token splitting slices a clause away
from its own heading, so a retrieved chunk loses the context of *which*
procedure or NF it's describing. That's a direct hallucination source.

Strategy:
1. Load PDF page by page (PyPDFLoader), keep page numbers.
2. Detect clause headings via regex (e.g. "5.2.1.3  Registration procedure").
3. Group text under its nearest clause heading -> each chunk carries the
   full clause path + spec name as metadata AND as an inline header in
   the chunk text itself, so an isolated chunk is still self-describing.
4. If a clause's text is long, sub-split by paragraph (never mid-sentence,
   never separating text from its clause heading).
5. Small, intentional overlap (not a blind sliding window) to preserve
   continuity between adjacent chunks of the same clause.
"""

import re
import os
from dataclasses import dataclass, field
from typing import List
from langchain_community.document_loaders import PyPDFLoader

# Matches "5.2.1.3 Registration procedure" or "5.2.1.3\tRegistration procedure"
# 3GPP clause numbers are typically 1-6 levels deep, e.g. "4", "4.2", "4.2.1.1"
CLAUSE_HEADING_RE = re.compile(
    r"^(?P<num>\d{1,2}(?:\.\d{1,3}){0,5})\s+(?P<title>[A-Z][A-Za-z0-9\-/,'&() ]{2,90})\s*$"
)

# Annex headings, e.g. "Annex A: ..." — treated as top-level clauses too
ANNEX_HEADING_RE = re.compile(r"^(Annex\s+[A-Z])\s*[:\-]?\s*(?P<title>.{0,90})$")


@dataclass
class Clause:
    spec_id: str
    clause_num: str
    title: str
    page_start: int
    text: str = ""


@dataclass
class Chunk:
    spec_id: str
    clause_num: str
    title: str
    page: int
    text: str
    chunk_index: int = 0  # sub-chunk index within a clause, for overlap bookkeeping


def infer_spec_id(filename: str) -> str:
    """
    Try to pull a 3GPP spec id like '23.501' or '38.300' out of the filename.
    ETSI filenames look like 'ts_123501v180500p.pdf' where '123501' encodes
    series '23' + spec '501' (a leading '1' prefixes the 3-digit series).
    Falls back to the filename itself if no pattern is found.
    """
    base = os.path.basename(filename)
    # ETSI convention: ts_1XXYYYvZZZZZZp.pdf -> series XX, spec YYY
    m = re.search(r"ts_1(\d{2})(\d{3})v", base, re.IGNORECASE)
    if m:
        return f"TS {m.group(1)}.{m.group(2)}"
    # Fallback: any bare XX.YYY / XXYYY pattern elsewhere in the name
    m = re.search(r"(\d{2})[._\-](\d{3})", base)
    if m:
        return f"TS {m.group(1)}.{m.group(2)}"
    return os.path.splitext(base)[0]


def load_pdf_pages(pdf_path: str):
    """Returns list of (page_number, page_text)."""
    loader = PyPDFLoader(pdf_path)
    docs = loader.load()
    return [(i + 1, d.page_content) for i, d in enumerate(docs)]


def split_into_clauses(pages, spec_id: str) -> List[Clause]:
    """
    Walk through page text line by line, detect clause headings, and
    accumulate text under the most recent heading.
    """
    clauses: List[Clause] = []
    current: Clause | None = None

    for page_num, page_text in pages:
        lines = page_text.split("\n")
        for line in lines:
            stripped = _strip_running_header(line.strip())
            if not stripped:
                continue

            # Skip Table-of-Contents-style lines (dot-leader + trailing page number,
            # e.g. "4.2.8.1 General Concepts ....................... 56"). Real body
            # clause headings never have a dot-leader run or trailing page number.
            if re.search(r"\.{3,}\s*\d{1,4}\s*$", stripped):
                continue

            m = CLAUSE_HEADING_RE.match(stripped)
            a = ANNEX_HEADING_RE.match(stripped) if not m else None

            if m:
                # New clause boundary -> close old, start new
                if current is not None:
                    clauses.append(current)
                current = Clause(
                    spec_id=spec_id,
                    clause_num=m.group("num"),
                    title=m.group("title").strip(),
                    page_start=page_num,
                )
                continue

            if a:
                if current is not None:
                    clauses.append(current)
                current = Clause(
                    spec_id=spec_id,
                    clause_num=a.group(1),
                    title=a.group("title").strip(),
                    page_start=page_num,
                )
                continue

            # Skip obvious running headers/footers (ETSI boilerplate, page numbers)
            if _is_boilerplate(stripped):
                continue

            if current is None:
                # Text before the first detected heading. For 3GPP specs this
                # is genuine front matter (title page, scope, references). For
                # non-3GPP documents with no numbered clause structure at all
                # (resumes, slide exports, prose reports), this bucket ends up
                # holding the entire document - label it generically rather
                # than "Front matter / Scope", which would be misleading and
                # could bias a downstream LLM to under-weight it as metadata.
                current = Clause(
                    spec_id=spec_id,
                    clause_num="0",
                    title="Document content",
                    page_start=page_num,
                )
            current.text += stripped + "\n"

    if current is not None:
        clauses.append(current)

    return clauses


def _is_boilerplate(line: str) -> bool:
    patterns = [
        r"^3GPP TS \d",
        r"^ETSI TS \d",
        r"^ETSI\s*$",
        r"^Release \d",
        r"^\d+$",  # bare page number
        r"^© \d{4}",
        r"^All rights reserved",
    ]
    return any(re.match(p, line) for p in patterns)


def _strip_running_header(line: str) -> str:
    """
    ETSI PDF text extraction glues the running header directly onto body
    text with no whitespace, e.g.:
      'ETSI TS 123 501 V18.5.0 (2024-05)1003GPP TS 23.501 version 18.5.0 Release 18'
    followed immediately by real content on the same extracted line, or the
    header appears as its own fused line. This strips that fused header
    prefix (page-number digits included) so it doesn't get swallowed into
    clause body text or block heading detection.
    """
    pattern = re.compile(
        r"^ETSI\s+TS\s+\d{3}\s+\d{3}\s+V[\d.]+\s+\([\d\-]+\)\s*\d*\s*3GPP\s+TS\s+[\d.]+\s+version\s+[\d.]+\s+Release\s+\d+\s*"
    )
    return pattern.sub("", line).strip()


def clause_to_chunks(
    clause: Clause, max_chars: int = 1200, overlap_chars: int = 150
) -> List[Chunk]:
    """
    Turn one clause into one or more chunks. Short clauses -> 1 chunk.
    Long clauses -> paragraph-boundary sub-split with small overlap,
    every sub-chunk still prefixed with the clause header for self-description.
    """
    header = f"[{clause.spec_id} | Clause {clause.clause_num} | {clause.title}]\n"
    body = clause.text.strip()

    if not body:
        return []

    if len(body) <= max_chars:
        return [
            Chunk(
                spec_id=clause.spec_id,
                clause_num=clause.clause_num,
                title=clause.title,
                page=clause.page_start,
                text=header + body,
            )
        ]

    # Sub-split on paragraph boundaries (blank-line separated or sentence-grouped)
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    if len(paragraphs) == 1:
        # No paragraph breaks found (common after boilerplate stripping) ->
        # fall back to sentence-boundary grouping so we never cut mid-sentence.
        paragraphs = re.split(r"(?<=[.;:])\s+(?=[A-Z0-9])", body)

    chunks: List[Chunk] = []
    current_text = ""
    idx = 0
    for para in paragraphs:
        if len(current_text) + len(para) + 1 > max_chars and current_text:
            chunks.append(
                Chunk(
                    spec_id=clause.spec_id,
                    clause_num=clause.clause_num,
                    title=clause.title,
                    page=clause.page_start,
                    text=header + current_text.strip(),
                    chunk_index=idx,
                )
            )
            idx += 1
            # small intentional overlap: carry the tail of the previous chunk
            # forward, snapped to the nearest sentence boundary at or before
            # the overlap window so we never resume mid-word/mid-sentence.
            search_from = max(0, len(current_text) - overlap_chars * 3)
            window = current_text[search_from:]
            last_period = window.rfind(". ")
            if last_period != -1:
                tail = window[last_period + 2 :]
            else:
                tail = current_text[-overlap_chars:]
            current_text = tail + " " + para
        else:
            current_text += " " + para

    if current_text.strip():
        chunks.append(
            Chunk(
                spec_id=clause.spec_id,
                clause_num=clause.clause_num,
                title=clause.title,
                page=clause.page_start,
                text=header + current_text.strip(),
                chunk_index=idx,
            )
        )

    return chunks


def ingest_pdf(
    pdf_path: str, max_chars: int = 1200, overlap_chars: int = 150
) -> List[Chunk]:
    spec_id = infer_spec_id(pdf_path)
    pages = load_pdf_pages(pdf_path)
    clauses = split_into_clauses(pages, spec_id)

    all_chunks: List[Chunk] = []
    for clause in clauses:
        # Skip near-empty / boilerplate-only clauses (e.g. "0 Front matter" with
        # nothing but a table of contents artifact)
        if len(clause.text.strip()) < 20:
            continue
        all_chunks.extend(clause_to_chunks(clause, max_chars, overlap_chars))

    return all_chunks


if __name__ == "__main__":
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else "data/raw/sample.pdf"
    chunks = ingest_pdf(path)
    print(f"Produced {len(chunks)} chunks from {path}")
    for c in chunks[:5]:
        print("---")
        print(c.text[:300])
