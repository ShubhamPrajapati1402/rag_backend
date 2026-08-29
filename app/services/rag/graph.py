from typing import Literal
from langgraph.graph import StateGraph, END
from app.schemas.rag_state import RAGState
from app.services.rag.nodes import (
    summarizer_node,
    router_node,
    rewriter_node,
    retriever_node,
    reranker_node,
    grader_node,
    rag_generator_node,
    direct_generator_node,
    fallback_generator_node,
    input_guardrail_node,
    hallucination_guard_node
)

def decide_input_guardrail(state: RAGState) -> Literal["router", "__end__"]:
    """Decides whether the user input passes security guardrails."""
    if state.get("route") == "blocked":
        return "__end__"
    return "router"

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
    Constructs and compiles the Stateful LangGraph RAG workflow with multi-layer Guardrails.
    """
    workflow = StateGraph(RAGState)

    # 1. Register Core & Guardrail Nodes
    workflow.add_node("summarizer", summarizer_node)
    workflow.add_node("input_guardrail", input_guardrail_node)
    workflow.add_node("router", router_node)
    workflow.add_node("rewriter", rewriter_node)
    workflow.add_node("retriever", retriever_node)
    workflow.add_node("reranker", reranker_node)
    workflow.add_node("grader", grader_node)
    workflow.add_node("rag_generator", rag_generator_node)
    workflow.add_node("hallucination_guard", hallucination_guard_node)
    workflow.add_node("direct_generator", direct_generator_node)
    workflow.add_node("fallback_generator", fallback_generator_node)

    # 2. Set Entry Point: Summarizer -> Input Guardrail
    workflow.set_entry_point("summarizer")
    workflow.add_edge("summarizer", "input_guardrail")

    # 3. Input Guardrail Conditional Edge
    workflow.add_conditional_edges(
        "input_guardrail",
        decide_input_guardrail,
        {
            "router": "router",
            "__end__": END
        }
    )

    # 4. Router Conditional Routing Edges
    workflow.add_conditional_edges(
        "router",
        decide_route,
        {
            "direct_generator": "direct_generator",
            "rewriter": "rewriter"
        }
    )

    # 5. Standard Two-Stage Retrieval Pipeline Edges
    workflow.add_edge("rewriter", "retriever")
    workflow.add_edge("retriever", "reranker")
    workflow.add_edge("reranker", "grader")

    # 6. Post-Grading Conditional Edge
    workflow.add_conditional_edges(
        "grader",
        decide_generation,
        {
            "rag_generator": "rag_generator",
            "fallback_generator": "fallback_generator"
        }
    )

    # 7. Post-Generation Hallucination Guardrail Edge
    workflow.add_edge("rag_generator", "hallucination_guard")

    # 8. Terminal Edges
    workflow.add_edge("hallucination_guard", END)
    workflow.add_edge("direct_generator", END)
    workflow.add_edge("fallback_generator", END)

    # Compile Graph
    return workflow.compile()

# Singleton compiled graph instance
rag_agent_app = build_rag_graph()
