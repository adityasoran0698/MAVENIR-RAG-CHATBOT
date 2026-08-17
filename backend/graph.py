import sqlite3
from pathlib import Path
from typing import TypedDict, Annotated, Literal

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage, AIMessage
import json
from langchain_core.messages import HumanMessage, AIMessageChunk
from generate import (
    generate_plain_chat_answer,
    generate_answer,
    check_groundedness,
    REFUSAL_TEXT,
)
from retrieval import hybrid_retrieve, rerank
from thread_store import has_index, get_index

BASE_DIR = Path(__file__).resolve().parent.parent
CHECKPOINT_DB = BASE_DIR / "data" / "checkpoints.sqlite"


class GraphState(TypedDict):
    messages: Annotated[list, add_messages]
    thread_id: str
    mode: str  # "rag" or "plain" - set by whichever node produces the final answer
    grounded: bool
    flagged_claims: list[str]
    sources: list[str]


def chat_node(state: GraphState) -> GraphState:
    """
    Always runs first. If this thread has no indexed document, this node
    produces the final plain-chat answer directly (no need to check
    groundedness against nothing). If an index exists, this node does NOT
    append an answer - it defers entirely to rag_node, which generates and
    appends the one true assistant message for this turn. This avoids two
    assistant messages landing in history for a single user turn.
    """
    thread_id = state["thread_id"]

    if has_index(thread_id):
        # Defer to rag_node - don't touch messages, just no-op through.
        return {}

    history = [
        {
            "role": "user" if isinstance(m, HumanMessage) else "assistant",
            "content": m.content,
        }
        for m in state["messages"][:-1]
    ]
    query = state["messages"][-1].content
    answer = generate_plain_chat_answer(query, history)

    return {
        "messages": [AIMessage(content=answer)],
        "mode": "plain",
        "grounded": False,
        "flagged_claims": [],
        "sources": [],
    }


def rag_node(state: GraphState) -> GraphState:
    """
    Runs only when this thread has an indexed document (chat_node deferred
    to us in that case). Retrieves, reranks, generates a citation-forced
    answer, and checks groundedness.
    """
    thread_id = state["thread_id"]
    query = state["messages"][-1].content  # chat_node did not append anything this turn

    entry = get_index(thread_id)
    candidates = hybrid_retrieve(
        query, entry["vectorstore"], entry["bm25"], entry["docs"]
    )
    top_chunks = rerank(query, candidates, top_n=5)

    raw_answer = generate_answer(query, top_chunks)
    grounded, flagged = check_groundedness(raw_answer, top_chunks)

    is_refusal = raw_answer.strip() == REFUSAL_TEXT
    sources = (
        []
        if is_refusal
        else sorted({f"{c.spec_id}, Clause {c.clause_num}" for c in top_chunks})
    )

    if not grounded and flagged:
        note = (
            "\n\n⚠️ Note: the following claim(s) could not be verified against the retrieved specs:\n"
            + "\n".join(f"- {f}" for f in flagged)
        )
        raw_answer += note

    # This is the one true assistant message for this turn (chat_node deferred).
    return {
        "messages": [AIMessage(content=raw_answer)],
        "mode": "rag",
        "grounded": grounded,
        "flagged_claims": flagged,
        "sources": sources,
    }


def route_after_chat(state: GraphState) -> Literal["rag_node", "__end__"]:
    """Conditional edge: only enter rag_node if this thread has a vector store."""
    if has_index(state["thread_id"]):
        return "rag_node"
    return END


def build_graph():
    graph = StateGraph(GraphState)
    graph.add_node("chat_node", chat_node)
    graph.add_node("rag_node", rag_node)

    graph.set_entry_point("chat_node")
    graph.add_conditional_edges(
        "chat_node", route_after_chat, {"rag_node": "rag_node", END: END}
    )
    graph.add_edge("rag_node", END)

    CHECKPOINT_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(CHECKPOINT_DB), check_same_thread=False)
    checkpointer = SqliteSaver(conn)

    return graph.compile(checkpointer=checkpointer)


_compiled_graph = None


def get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()
    return _compiled_graph


def stream_turn(thread_id: str, query: str):
    """
    Generator yielding SSE-ready dicts:
      {"type": "token", "content": "..."}      - one or more per token
      {"type": "meta", ...run_turn fields...}   - exactly one, at the end
      {"type": "error", "detail": "..."}        - on failure, in place of meta

    Usage (in main.py):
        for event in stream_turn(thread_id, query):
            yield f"data: {json.dumps(event)}\n\n"
    """
    graph = get_graph()
    config = {"configurable": {"thread_id": thread_id}}

    try:
        final_state = None
        for msg_chunk, metadata in graph.stream(
            {"messages": [HumanMessage(content=query)], "thread_id": thread_id},
            config=config,
            stream_mode="messages",
        ):
            if isinstance(msg_chunk, AIMessageChunk) and msg_chunk.content:
                yield {"type": "token", "content": msg_chunk.content}

        # After the stream is exhausted, pull final graph state for the
        # metadata fields that are only known post-generation (grounding,
        # sources, mode) - groundedness checking runs inside rag_node
        # after the full answer text exists, so it can't be streamed
        # token-by-token itself.
        state = graph.get_state(config)
        values = state.values

        yield {
            "type": "meta",
            "mode": values.get("mode", "plain"),
            "grounded": values.get("grounded", False),
            "flagged_claims": values.get("flagged_claims", []),
            "sources": values.get("sources", []),
        }
    except Exception as e:
        yield {"type": "error", "detail": str(e)}


def run_turn(thread_id: str, query: str) -> dict:
    """
    Run one turn of conversation for the given thread_id. Returns the final
    answer plus grounding metadata. Uses the LangGraph checkpointer so
    conversation history for this thread_id is automatically loaded and
    extended - the caller never needs to pass prior turns manually.
    """
    graph = get_graph()
    config = {"configurable": {"thread_id": thread_id}}

    result = graph.invoke(
        {"messages": [HumanMessage(content=query)], "thread_id": thread_id},
        config=config,
    )

    final_message = result["messages"][-1]
    return {
        "answer": final_message.content,
        "mode": result.get("mode", "plain"),
        "grounded": result.get("grounded", False),
        "flagged_claims": result.get("flagged_claims", []),
        "sources": result.get("sources", []),
    }


def get_thread_history(thread_id: str) -> list[dict]:
    """Retrieve the full message history for a thread_id, for UI resume."""
    graph = get_graph()
    config = {"configurable": {"thread_id": thread_id}}
    state = graph.get_state(config)
    if not state or not state.values.get("messages"):
        return []
    return [
        {
            "role": "user" if isinstance(m, HumanMessage) else "assistant",
            "content": m.content,
        }
        for m in state.values["messages"]
    ]
