"""
Answer generation for the 3GPP RAG chatbot.

Two modes:
- RAG mode (a document has been indexed): citation-forced answer, grounded
  strictly in retrieved 3GPP context, with a post-hoc groundedness check.
- Plain chatbot mode (no document indexed yet): behaves like a normal LLM
  chatbot, but every response is clearly labeled as NOT grounded in any
  spec, so the distinction is never hidden from the caller/UI.

Two-stage hallucination defense (RAG mode only):
1. Citation-forced prompting: the model is instructed to answer ONLY from
   the provided context and to cite [spec, clause] for every claim. If the
   context doesn't support an answer, it must say so explicitly instead of
   guessing.
2. Post-hoc groundedness check: after generation, we ask a second cheap
   LLM call to verify each claim in the answer is actually supported by
   the retrieved context. Unsupported claims are flagged.

Why two stages instead of trusting the prompt alone:
prompting reduces hallucination but doesn't eliminate it - models still
occasionally state things confidently that aren't in context. The
groundedness check is a cheap, mechanical safety net independent of the
first call's own (possibly flawed) self-assessment.

Uses LangChain's ChatOpenAI throughout (not the raw openai client), for
consistency with the rest of the stack.
"""

from dataclasses import dataclass
from typing import List
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from retrieval import RetrievedChunk

REFUSAL_TEXT = "The provided specifications do not cover this."

SYSTEM_PROMPT = f"""You are a technical assistant answering questions using ONLY the \
provided context passages retrieved from the user's uploaded document(s).

Rules:
1. Answer using information present in the context below. You may \
synthesize and explain concepts described across multiple passages, as \
long as every claim traces back to something actually stated in the \
context - do not add outside facts, numbers, or claims that aren't in \
the context.
2. Every factual claim you make MUST be followed by a citation in the form \
[Document, Clause/Section X.Y.Z], citing whichever passage(s) it came from.
3. Only respond with "{REFUSAL_TEXT}" if the context is genuinely \
irrelevant to the question - contains nothing that helps answer it, even \
partially. If the context partially addresses the question, answer with \
what IS supported and note what isn't covered, rather than refusing \
outright.
4. Do not blend information from different sections into a single claim \
unless both sections are cited.
5. Be precise. If the source document uses normative language ("shall", \
"may", "should", or similar formal requirements), preserve that language \
level exactly rather than softening or paraphrasing it."""

PLAIN_CHAT_SYSTEM_PROMPT = """You are a helpful general-purpose assistant. \
No 3GPP specification document has been uploaded/indexed yet, so you are \
answering from your own general knowledge, not from any grounded source. \
Be helpful, but if the user asks something clearly specific to 3GPP specs \
that you're not certain about, say so rather than guessing confidently."""

# Two distinct model instances: generation uses a stronger model at temp=0
# for deterministic, low-drift answers; the groundedness check and plain
# chat use a cheaper/faster model since they're simpler tasks.
_generation_llm = ChatOpenAI(
    model="gpt-4o",
    temperature=0,
)
_verify_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
_plain_chat_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)


@dataclass
class GeneratedAnswer:
    answer: str
    grounded: bool
    flagged_claims: List[str]
    sources: List[str]
    mode: str  # "rag" or "plain"


def build_context_block(chunks: List[RetrievedChunk]) -> str:
    parts = []
    for c in chunks:
        parts.append(f"[{c.spec_id}, Clause {c.clause_num} - {c.title}]\n{c.text}")
    return "\n\n---\n\n".join(parts)


def generate_answer(query: str, chunks: List[RetrievedChunk]) -> str:
    if not chunks:
        return "The provided specifications do not cover this."

    context = build_context_block(chunks)
    user_prompt = f"""Context passages:

{context}

---

Question: {query}"""

    response = _generation_llm.invoke(
        [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ]
    )
    return response.content


def check_groundedness(
    answer: str, chunks: List[RetrievedChunk]
) -> tuple[bool, List[str]]:
    """
    Ask the model to check whether each claim in `answer` is supported by
    the context. Returns (is_fully_grounded, list_of_unsupported_claims).
    This is intentionally a separate call from generation - checking your
    own output in the same pass is weaker than a fresh, narrowly-scoped
    verification call.
    """
    if answer.strip() == REFUSAL_TEXT:
        return True, []

    context = build_context_block(chunks)
    verify_prompt = f"""Context passages:

{context}

---

Candidate answer to verify:
{answer}

---

Task: List any sentence or claim in the candidate answer that is NOT \
directly supported by the context passages above. If every claim is \
supported, respond with exactly: "ALL_GROUNDED". Otherwise, list each \
unsupported claim on its own line, prefixed with "UNSUPPORTED: "."""

    response = _verify_llm.invoke([HumanMessage(content=verify_prompt)])
    result = response.content.strip()

    if result == "ALL_GROUNDED":
        return True, []

    flagged = [
        line.replace("UNSUPPORTED:", "").strip()
        for line in result.splitlines()
        if line.strip().startswith("UNSUPPORTED:")
    ]
    return len(flagged) == 0, flagged


def generate_plain_chat_answer(query: str, history: List[dict] | None = None) -> str:
    """
    Plain chatbot fallback used when no document has been indexed yet.
    `history` is an optional list of {"role": "user"|"assistant", "content": str}.
    """
    messages = [SystemMessage(content=PLAIN_CHAT_SYSTEM_PROMPT)]
    for turn in history or []:
        if turn["role"] == "user":
            messages.append(HumanMessage(content=turn["content"]))
        else:
            from langchain_core.messages import AIMessage

            messages.append(AIMessage(content=turn["content"]))
    messages.append(HumanMessage(content=query))

    response = _plain_chat_llm.invoke(messages)
    return response.content


def answer_query(query: str, chunks: List[RetrievedChunk]) -> GeneratedAnswer:
    """RAG-mode answer: citation-forced generation + groundedness check."""
    raw_answer = generate_answer(query, chunks)
    grounded, flagged = check_groundedness(raw_answer, chunks)

    is_refusal = raw_answer.strip() == REFUSAL_TEXT
    sources = (
        []
        if is_refusal
        else sorted({f"{c.spec_id}, Clause {c.clause_num}" for c in chunks})
    )

    if not grounded and flagged:
        # Don't silently ship an ungrounded answer - surface the issue.
        note = (
            "\n\n⚠️ Note: the following claim(s) could not be verified against the retrieved specs:\n"
            + "\n".join(f"- {f}" for f in flagged)
        )
        raw_answer += note

    return GeneratedAnswer(
        answer=raw_answer,
        grounded=grounded,
        flagged_claims=flagged,
        sources=sources,
        mode="rag",
    )


def answer_plain(query: str, history: List[dict] | None = None) -> GeneratedAnswer:
    """Plain-chatbot-mode answer: no document indexed, no grounding claim made."""
    answer = generate_plain_chat_answer(query, history)
    return GeneratedAnswer(
        answer=answer,
        grounded=False,
        flagged_claims=[],
        sources=[],
        mode="plain",
    )
