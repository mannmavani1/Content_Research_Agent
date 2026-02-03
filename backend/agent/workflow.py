from typing import Literal
from langgraph.graph import StateGraph, END
from backend.models.state import AgentState
from backend.database.vector_store import get_retriever
from backend.agent.tools import (
    summarizer_chain, qa_chain, comparator_chain, 
    extractor_chain, insight_chain
)
from backend.services.llm import get_llm
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from backend.agent.nodes import router_node, retrieve_node, summarize_node, compare_node, extract_node, insight_node, qa_node

def build_graph():
    """Build the LangGraph workflow"""

    workflow = StateGraph(AgentState)

    workflow.add_node("router", router_node)
    workflow.add_node("retrieve", retrieve_node)

    workflow.add_node("summarize", summarize_node)
    workflow.add_node("compare", compare_node)
    workflow.add_node("extract", extract_node)
    workflow.add_node("insight", insight_node)
    workflow.add_node("qa", qa_node)

    workflow.set_entry_point("retrieve")
    workflow.add_edge("retrieve", "router")

    def route_decision(state: AgentState):
        """Route the decision based on the category"""
        category = state["generation"]
        if category == "summarize":
            return "summarize"
        elif category == "compare":
            return "compare"
        elif category == "extract":
            return "extract"
        elif category == "insight":
            return "insight"
        elif category == "qa":
            return "qa"
        else:
            return "qa"
    
    workflow.add_conditional_edges(
        "router",
        route_decision,
        {
            "summarize": "summarize",
            "compare": "compare",
            "extract": "extract",
            "insight": "insight",
            "qa": "qa"
        }
    )
    workflow.add_edge("summarize", END)
    workflow.add_edge("compare", END)
    workflow.add_edge("extract", END)
    workflow.add_edge("insight", END)
    workflow.add_edge("qa", END)

    return workflow.compile()

research_agent = build_graph()