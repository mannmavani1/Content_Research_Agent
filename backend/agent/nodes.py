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

def router_node(state: AgentState):
    """Router node to determine the best tool to use"""

    question = state["question"]
    print(f"Routing: {question}")

    llm = get_llm()

    prompt = PromptTemplate.from_template(
        """You are a routing agent. Your ONLY job is to classify the user's query.
        Do not answer the question. Just output JSON.
        
        Categories:
        - "summarize": Requests for summaries, overviews, or "tl;dr".
        - "compare": Requests to compare multiple items or documents.
        - "extract": Requests for specific numbers, tables, data points, or lists.
        - "insight": Requests for recommendations, analysis, or "what does this mean".
        - "qa": General questions, specific facts, or anything else.
        
        Output format must be strict JSON: {{"category": "summarize"}}
        
        Query: {question}
        """
    )

    router_chain = prompt | llm | JsonOutputParser()

    try:
        decision = router_chain.invoke({"question": question})
        category = decision.get("category", "qa")
        print(f"Routed to: {category}")
    except:
        category = "qa"
        print(f"Routing failed, defaulting to: {category}")

    print(f"Decision: {category}")

    return {"generation": category}

def retrieve_node(state: AgentState):
    """Retrieve the documents from the vector store"""

    retriever = get_retriever()
    docs = retriever.invoke(state["question"])
    formatted_docs = []
    for d in docs:
        source_path = d.metadata.get("source", "Unknown Document")
        filename = source_path.split("/")[-1] if "/" in source_path else source_path
        
        page_num = d.metadata.get("page", "?")
        
        # Create a clear block for the LLM
        entry = f"Source: {filename} (Page {page_num})\nContent: {d.page_content}"
        formatted_docs.append(entry)

    return {"documents": formatted_docs}

def run_tool(state: AgentState,chain,name):
    """Run the tool based on the category"""

    print(f"Running tool: {name}")
    context = "\n\n".join(state["documents"])
    result = chain.invoke({"context": context, "question": state["question"]})
    print(f"Tool {name} result: {result}")
    return {"generation": result}

def summarize_node(state: AgentState):
    """Summarize the documents"""
    return run_tool(state, summarizer_chain, "summarize")

def compare_node(state: AgentState):
    """Compare the documents"""
    return run_tool(state, comparator_chain, "compare")

def extract_node(state: AgentState):
    """Extract the data from the documents"""
    return run_tool(state, extractor_chain, "extract")

def insight_node(state: AgentState):
    """Generate insights from the documents"""
    return run_tool(state, insight_chain, "insight")

def qa_node(state: AgentState):
    """Answer the question"""
    return run_tool(state, qa_chain, "qa")

 