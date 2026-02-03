from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from backend.services.llm import get_llm

llm = get_llm()

# --- Tool 1: Summarizer ---
summarize_prompt = PromptTemplate.from_template(
    """You are an expert document summarizer. 
    Read the following context and provide a structured summary with bullet points.
    Critically: You MUST cite the page numbers and document names provided in the context for every fact.
    
    Context: {context}
    
    Output Format:
    ## Executive Summary
    - Key Point 1 (Source: Page X, Document Name)
    - Key Point 2 (Source: Page Y, Document Name)
    """
)
summarizer_chain = summarize_prompt | llm | StrOutputParser()

# --- Tool 2: Q&A (RAG) ---
qa_prompt = PromptTemplate.from_template(
    """Answer the user's question based ONLY on the context provided.
    If the answer is not in the text, say 'I cannot find that info'.
    Include exact quotes and page and document name citations.
    
    Context: {context}
    Question: {question}
    """
)
qa_chain = qa_prompt | llm | StrOutputParser()

# --- Tool 3: Comparator ---
compare_prompt = PromptTemplate.from_template(
    """You are a data analyst. Compare the documents provided in the context.
    Create a Markdown Table comparing them on key metrics relevant to the user's request.
    Critically: You MUST cite the page numbers and document names provided in the context for every fact.
    
    Context: {context}
    User Request: {question}
    
    Output: A clean Markdown table followed by a brief analysis. Critically: You MUST cite the page numbers and document names provided in the context for every fact.
    """
)
comparator_chain = compare_prompt | llm | StrOutputParser()

# --- Tool 4: Data Extractor ---
extract_prompt = PromptTemplate.from_template(
    """Extract all key numerical data, dates, and metrics from the context.
    Present them in a structured JSON-like format or a clear list. Critically: You MUST cite the page numbers and document names provided in the context for every fact.
    
    Context: {context}
    Focus on: {question}
    """
)
extractor_chain = extract_prompt | llm | StrOutputParser()

# --- Tool 5: Insight Generator ---
insight_prompt = PromptTemplate.from_template(
    """Act as a strategic consultant. Analyze the context and provide 3-5 high-level insights
    and actionable recommendations based on the data.
    Critically: You MUST cite the page numbers and document names provided in the context for every fact.
    
    Context: {context}
    """
)
insight_chain = insight_prompt | llm | StrOutputParser()