from typing import Literal
from langgraph.graph import StateGraph, END
from app.schemas.rag_state import RAGState
from app.services.rag.nodes import (
    summarizer_node,
    router_node,
    rewriter_node,
    retriever_node,
    grader_node,
    rag_generator_node,
    direct_generator_node,
    fallback_generator_node
)

def decide_route(state: RAGState) -> Literal["direct_generator", "rewriter"]:
    """Decides whether to answer directly or retrieve document context."""
    if state.get("route") == "direct":
        return "direct_generator"
    return "rewriter"

def decide_generation(state: RAGState) -> Literal["rag_generator", "fallback_generator"]:
    """Decides whether to generate a RAG answer or trigger fallback if no relevant docs found."""
    docs = state.get("documents", [])
    if docs and len(docs) > 0:
        return "rag_generator"
    return "fallback_generator"

def build_rag_graph():
    """
    Constructs and compiles the Stateful LangGraph RAG workflow with progressive summarization.
    """
    workflow = StateGraph(RAGState)

    # 1. Register Nodes
    workflow.add_node("summarizer", summarizer_node)
    workflow.add_node("router", router_node)
    workflow.add_node("rewriter", rewriter_node)
    workflow.add_node("retriever", retriever_node)
    workflow.add_node("grader", grader_node)
    workflow.add_node("rag_generator", rag_generator_node)
    workflow.add_node("direct_generator", direct_generator_node)
    workflow.add_node("fallback_generator", fallback_generator_node)

    # 2. Set Entry Point (Summarizer maintains long-term conversation context)
    workflow.set_entry_point("summarizer")
    workflow.add_edge("summarizer", "router")

    # 3. Add Conditional Routing Edges
    workflow.add_conditional_edges(
        "router",
        decide_route,
        {
            "direct_generator": "direct_generator",
            "rewriter": "rewriter"
        }
    )

    # 4. Standard Retrieval Pipeline Edges
    workflow.add_edge("rewriter", "retriever")
    workflow.add_edge("retriever", "grader")

    # 5. Add Post-Grading Conditional Edge
    workflow.add_conditional_edges(
        "grader",
        decide_generation,
        {
            "rag_generator": "rag_generator",
            "fallback_generator": "fallback_generator"
        }
    )

    # 6. Terminal Edges
    workflow.add_edge("rag_generator", END)
    workflow.add_edge("direct_generator", END)
    workflow.add_edge("fallback_generator", END)

    # Compile Graph
    return workflow.compile()

# Singleton compiled graph instance
rag_agent_app = build_rag_graph()
