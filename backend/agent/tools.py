from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from backend.services.llm import get_llm

llm = get_llm()

# --- Tool 1: Summarizer ---
summarize_prompt = PromptTemplate.from_template(
    """You are an expert document summarizer.
    
    User Request: {question}
    
    Instructions:
    1. Read the Context below carefully.
    2. Summarize according to the User Request (e.g., length, specific topic).
    3. If the user mentions a specific filename, ONLY use information from that file.
    4. You MUST cite the page numbers for every fact (e.g., "Fact... (Page 3)").
    5. CRITICAL: The output must be in valid Markdown format (use bullet points, bold headers, etc.).
    
    Context: 
    {context}
    
    Output:
    """
)
summarizer_chain = summarize_prompt | llm | StrOutputParser()

# --- Tool 2: Q&A (RAG) ---
qa_prompt = PromptTemplate.from_template(
    """You are a helpful research assistant.
    
    Context: 
    {context}
    
    User Question: {question}
    
    Instructions:
    - Answer based ONLY on the context provided.
    - If the user specifies a file, ignore context from other files.
    - Include exact quotes and page citations.
    - Format your response in clean Markdown (use bold for key terms, lists where appropriate).
    """
)
qa_chain = qa_prompt | llm | StrOutputParser()

# --- Tool 3: Comparator ---
compare_prompt = PromptTemplate.from_template(
    """You are a data analyst.
    
    User Request: {question}
    
    Context: 
    {context}
    
    Instructions:
    - Compare the documents based on the User Request.
    - If the user asks for specific fields, focus only on those.
    - CRITICAL: Output the result as a Markdown Table.
    - Add a brief analysis below the table in Markdown text.
    """
)
comparator_chain = compare_prompt | llm | StrOutputParser()

# --- Tool 4: Data Extractor ---
extract_prompt = PromptTemplate.from_template(
    """You are a data extraction engine.
    
    User Request: {question}
    
    Context: 
    {context}
    
    Instructions:
    - Extract ONLY the data requested by the user.
    - Format the output as a Markdown Table or a structured Markdown List.
    - Do not output raw JSON unless explicitly asked.
    """
)
extractor_chain = extract_prompt | llm | StrOutputParser()

# --- Tool 5: Insight Generator ---
insight_prompt = PromptTemplate.from_template(
    """You are a strategic consultant.
    
    User Request: {question}
    
    Context: 
    {context}
    
    Instructions:
    1. Analyze the context to provide insights.
    2. CRITICAL: Strictly follow the length constraints in the User Request (e.g., if asked for "2 lines", give exactly 2 lines).
    3. CRITICAL: If the user mentions a specific file name, IGNORE context from all other files.
    4. Provide actionable recommendations based ONLY on the targeted data.
    5. Format the output in professional Markdown.
    """
)
insight_chain = insight_prompt | llm | StrOutputParser()