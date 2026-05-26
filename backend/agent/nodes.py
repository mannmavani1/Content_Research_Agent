from typing import Literal
from langgraph.graph import StateGraph, END
from backend.models.state import AgentState
from backend.database.retriever import get_retriever
from backend.agent.tools import (
    summarizer_chain, qa_chain, comparator_chain, 
    extractor_chain, insight_chain
)
from backend.services.llm import get_llm
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser

def router_node(state: AgentState):
    """
    Analyzes the user's query and routes the workflow to the appropriate processing node.

    Args:
        state (AgentState): The current state of the agent, containing the user's question.

    Returns:
        dict: A dictionary containing the 'generation' key with the predicted tool category 
              (e.g., 'summarize', 'compare', 'extract', 'insight', or 'qa').
    """
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
    except Exception as e:
        category = "qa"
        print(f"Routing failed due to {e}, defaulting to: {category}")

    return {"generation": category}

def retrieve_node(state: AgentState):
    """
    Queries the vector database to retrieve relevant document chunks based on the user's question.

    Args:
        state (AgentState): The current state of the agent, containing the user's question.

    Returns:
        dict: A dictionary with the 'documents' key containing a list of formatted 
              strings representing the retrieved context and metadata.
    """
    retriever = get_retriever()
    docs = retriever.invoke(state["question"])
    formatted_docs = []
    for d in docs:
        source_path = d.metadata.get("source", "Unknown Document")
        filename = source_path.split("/")[-1] if "/" in source_path else source_path
        page_num = d.metadata.get("page", "?")
        
        entry = f"Source: {filename} (Page {page_num})\nContent: {d.page_content}"
        formatted_docs.append(entry)

    return {"documents": formatted_docs}

def run_tool(state: AgentState, chain, name: str):
    """
    A helper function to execute a specific LangChain processing chain.

    Args:
        state (AgentState): The current state containing documents and the original question.
        chain: The LangChain Runnable/Chain to be executed.
        name (str): The display name of the tool for logging purposes.

    Returns:
        dict: A dictionary with the 'generation' key containing the final text output 
              produced by the LLM chain.
    """
    print(f"Running tool: {name}")
    context = "\n\n".join(state["documents"])
    result = chain.invoke({"context": context, "question": state["question"]})
    return {"generation": result}

def summarize_node(state: AgentState):
    """
    Generates a concise summary or overview of the retrieved documents.

    Args:
        state (AgentState): The current state containing retrieved context.

    Returns:
        dict: The result of the summarizer_chain.
    """
    return run_tool(state, summarizer_chain, "summarize")

def compare_node(state: AgentState):
    """
    Performs a comparative analysis between different documents or entities within the context.

    Args:
        state (AgentState): The current state containing retrieved context.

    Returns:
        dict: The result of the comparator_chain.
    """
    return run_tool(state, comparator_chain, "compare")

def extract_node(state: AgentState):
    """
    Identifies and pulls specific data points, tables, or facts from the retrieved documents.

    Args:
        state (AgentState): The current state containing retrieved context.

    Returns:
        dict: The result of the extractor_chain.
    """
    return run_tool(state, extractor_chain, "extract")

def insight_node(state: AgentState):
    """
    Analyzes the data to provide recommendations, deep analysis, or strategic insights.

    Args:
        state (AgentState): The current state containing retrieved context.

    Returns:
        dict: The result of the insight_chain.
    """
    return run_tool(state, insight_chain, "insight")

def qa_node(state: AgentState):
    """
    Answers general or factual questions using the provided document context.

    Args:
        state (AgentState): The current state containing retrieved context.

    Returns:
        dict: The result of the qa_chain.
    """
    return run_tool(state, qa_chain, "qa")