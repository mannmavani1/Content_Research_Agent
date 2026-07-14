import os
from tavily import TavilyClient
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

async def router_node(state: AgentState):
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

    llm = get_llm(streaming=False)

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
        decision = await router_chain.ainvoke({"question": question})
        category = decision.get("category", "qa")
        print(f"Routed to: {category}")
    except Exception as e:
        category = "qa"
        print(f"Routing failed due to {e}, defaulting to: {category}")

    return {"generation": category}

async def retrieve_node(state: AgentState):
    """
    Queries the vectorless database to retrieve relevant document chunks or multimodal segments.

    Args:
        state (AgentState): The current state of the agent, containing the user's question.

    Returns:
        dict: A dictionary with the 'documents' key containing formatted visual/text/audio context.
    """
    retriever = get_retriever(
        conversation_id=state.get("conversation_id"), 
        workspace_id=state.get("workspace_id")
    )
    docs = await retriever.ainvoke(state["question"])
    formatted_docs = []
    
    for d in docs:
        source_path = d.metadata.get("source", "Unknown Document")
        filename = source_path.split("/")[-1] if "/" in source_path else source_path
        media_type = d.metadata.get("media_type", "text")
        
        # Multimodal formatting for LLM prompt context injection
        if media_type == "image":
            entry = f"Source: {filename} (Image File, available at URL: /storage/{filename})\nContent: {d.page_content}"
        elif media_type == "audio":
            t = d.metadata.get("timestamp", "00:00")
            entry = f"Source: {filename} (Audio Segment at {t})\nContent: {d.page_content}"
        elif media_type == "video":
            t = d.metadata.get("timestamp", "00:00")
            frame_url = d.metadata.get("frame_url", "")
            frame_suffix = f" with Keyframe URL: {frame_url}" if frame_url else ""
            entry = f"Source: {filename} (Video Segment at {t}{frame_suffix})\nContent: {d.page_content}"
        else:
            page_num = d.metadata.get("page", "?")
            entry = f"Source: {filename} (Page {page_num})\nContent: {d.page_content}"
            
        formatted_docs.append(entry)

    return {"documents": formatted_docs}

async def run_tool(state: AgentState, chain, name: str):
    """
    A helper function to execute a specific LangChain processing chain.

    Args:
        state (AgentState): The graph state containing documents and the question.
        chain: The LangChain sequence to invoke.
        name (str): Identifier for logging purposes.

    Returns:
        dict: The updated state dictionary containing the generated 'generation'.
    """
    print(f"Executing Tool: {name}")
    docs = state.get("documents", [])
    context = "\n\n".join(docs) if docs else "No relevant context found in documents."
    question = state.get("question", "")
    
    # Format chat history
    messages = state.get("messages", [])
    chat_history_str = ""
    for msg in messages:
        role = "User" if msg.type == "human" else "AI"
        chat_history_str += f"{role}: {msg.content}\n"
    
    if not chat_history_str:
        chat_history_str = "No previous chat history."

    try:
        result = await chain.ainvoke({"context": context, "question": question, "chat_history": chat_history_str})
        return {"generation": result}
    except Exception as e:
        print(f"Error in {name}: {e}")
        return {"generation": f"Error generating response: {e}"}

async def summarize_node(state: AgentState):
    """
    Generates a concise summary or overview of the retrieved documents.

    Args:
        state (AgentState): The current state containing retrieved context.

    Returns:
        dict: The result of the summarizer_chain.
    """
    return await run_tool(state, summarizer_chain, "summarize")

async def compare_node(state: AgentState):
    """
    Performs a comparative analysis between different documents or entities within the context.

    Args:
        state (AgentState): The current state containing retrieved context.

    Returns:
        dict: The result of the comparator_chain.
    """
    return await run_tool(state, comparator_chain, "compare")

async def extract_node(state: AgentState):
    """
    Identifies and pulls specific data points, tables, or facts from the retrieved documents.

    Args:
        state (AgentState): The current state containing retrieved context.

    Returns:
        dict: The result of the extractor_chain.
    """
    return await run_tool(state, extractor_chain, "extract")

async def insight_node(state: AgentState):
    """
    Analyzes the data to provide recommendations, deep analysis, or strategic insights.

    Args:
        state (AgentState): The current state containing retrieved context.

    Returns:
        dict: The result of the insight_chain.
    """
    return await run_tool(state, insight_chain, "insight")

async def qa_node(state: AgentState):
    """
    Answers general or factual questions using the provided document context.

    Args:
        state (AgentState): The current state containing retrieved context.

    Returns:
        dict: The result of the qa_chain.
    """
    return await run_tool(state, qa_chain, "qa")

async def evaluate_context_node(state: AgentState):
    """
    Evaluates if the retrieved documents contain sufficient context to answer the question.
    """
    docs = state.get("documents", [])
    if not docs:
        print("No documents retrieved. Web search is required.")
        return {"needs_search": True}
        
    context = "\n\n".join(docs)
    question = state.get("question", "")
    
    llm = get_llm(streaming=False)
    prompt = PromptTemplate.from_template(
        """You are an information grading agent. Your job is to determine whether the provided document context has sufficient information to answer the user's question.
        
        If the question requires information that is not in the context (such as more recent statistics, comparison with future/unreleased data, details of subsequent years, or is completely unrelated to the documents), you must reply with needs_search: true.
        Otherwise, if the question can be fully answered using the provided context, reply with needs_search: false.
        
        Document Context:
        {context}
        
        User Question:
        {question}
        
        Output format must be strict JSON: {{"needs_search": true}} or {{"needs_search": false}}
        """
    )
    
    chain = prompt | llm | JsonOutputParser()
    try:
        result = await chain.ainvoke({"context": context, "question": question})
        needs_search = result.get("needs_search", False)
        print(f"Context evaluation result: needs_search = {needs_search}")
        return {"needs_search": needs_search}
    except Exception as e:
        print(f"Error evaluating context: {e}, defaulting to no web search.")
        return {"needs_search": False}

async def web_search_node(state: AgentState):
    """
    Performs web search using Tavily and appends results to the document context.
    """
    question = state.get("question", "")
    tavily_key = os.getenv("TAVILY_API_KEY")
    if not tavily_key:
        print("TAVILY_API_KEY not found in environment. Skipping web search.")
        return {}
        
    print(f"Executing Web Search for: {question}")
    try:
        client = TavilyClient(api_key=tavily_key)
        response = client.search(query=question, max_results=5)
        results = response.get("results", [])
        
        web_docs = []
        for r in results:
            title = r.get("title", "Web Page")
            url = r.get("url", "")
            content = r.get("content", "")
            web_docs.append(f"Source URL: {url} (Title: {title})\nContent: {content}")
            
        current_docs = list(state.get("documents", []))
        current_docs.extend(web_docs)
        print(f"Web search completed. Added {len(web_docs)} external search chunks.")
        return {"documents": current_docs}
    except Exception as e:
        print(f"Web search failed: {e}")
        return {}