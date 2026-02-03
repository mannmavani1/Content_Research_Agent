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
from backend.agent.nodes import (
    router_node, retrieve_node, summarize_node, 
    compare_node, extract_node, insight_node, qa_node
)

def build_graph():
    """
    Initializes and compiles the LangGraph state machine for the research agent.
    
    This function defines the computational graph by:
    1. Registering nodes for retrieval, routing, and specific analysis tools.
    2. Establishing the linear path from document retrieval to query routing.
    3. Implementing conditional branching logic to direct the flow to specialized 
       LLM chains based on the user's intent.
    
    Returns:
        CompiledGraph: A compiled LangGraph instance ready to invoke with an AgentState.
    """

    workflow = StateGraph(AgentState)

    # --- Node Definitions ---
    workflow.add_node("router", router_node)
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("summarize", summarize_node)
    workflow.add_node("compare", compare_node)
    workflow.add_node("extract", extract_node)
    workflow.add_node("insight", insight_node)
    workflow.add_node("qa", qa_node)

    # --- Edge Definitions ---
    # Entry flow: First retrieve context, then decide how to process it.
    workflow.set_entry_point("retrieve")
    workflow.add_edge("retrieve", "router")

    def route_decision(state: AgentState) -> Literal["summarize", "compare", "extract", "insight", "qa"]:
        """
        A conditional edge function that reads the classification from the router node.

        Args:
            state (AgentState): The current graph state containing the 'generation' key 
                                populated by the router.

        Returns:
            str: The name of the next node to transition to.
        """
        category = state["generation"]
        if category in ["summarize", "compare", "extract", "insight", "qa"]:
            return category
        return "qa"  # Default fallback
    
    # --- Routing Configuration ---
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

    # --- Exit Edges ---
    # All tool nodes conclude the workflow by transitioning to the END state.
    workflow.add_edge("summarize", END)
    workflow.add_edge("compare", END)
    workflow.add_edge("extract", END)
    workflow.add_edge("insight", END)
    workflow.add_edge("qa", END)

    return workflow.compile()

# The executable instance of the research agent
research_agent = build_graph()