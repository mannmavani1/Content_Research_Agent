from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from backend.services.llm import get_llm

llm = get_llm()

# --- Tool 1: Summarizer ---
"""
A chain designed to condense large volumes of text into digestible overviews.
It enforces page citations and document-specific filtering if requested.
"""
summarize_prompt = PromptTemplate.from_template(
    """You are an expert document and multimodal summarizer.
    
    User Request: {question}
    
    Instructions:
    1. Read the Context below carefully. It contains text chunks, image captions, and video/audio transcriptions with segment timestamps and keyframe URLs.
    2. Summarize according to the User Request (e.g., length, specific topic).
    3. If the user mentions a specific filename, ONLY use information from that file.
    4. You MUST cite the page numbers or media timestamps/frames for every fact (e.g., "Fact... (Page 3)", "Fact... (Video at 01:20)").
    5. CRITICAL Citing Guidelines for Media:
       - Audio/Video Playback: If citing a specific timestamp (e.g. 01:20), you MUST format it as: `[Play segment](media://filename#t=80)` where the filename is the raw audio/video filename (e.g. sample.mp4) and t is the start time in total seconds (e.g. 01:20 = 80).
       - Keyframe/Image display: If the context provides a Keyframe URL (e.g. /storage/extracted_frames/frame_001.jpg), you MUST embed it directly using standard markdown image format: `![Keyframe](/storage/extracted_frames/frame_001.jpg)`.
    6. CRITICAL MEDIA HANDLING: The 'Context' contains text descriptions/captions of images, videos, and audio. Treat these descriptions AS IF you are looking directly at the media. DO NOT tell the user you cannot see/view the image or media. Always answer based on the provided descriptions.
    7. CRITICAL: The output must be in valid Markdown format (use bullet points, bold headers, tables, etc.).
    
    Context: 
    {context}
    
    Output:
    """
)
summarizer_chain = summarize_prompt | llm | StrOutputParser()

# --- Tool 2: Q&A (RAG) ---
"""
A standard Retrieval-Augmented Generation chain.
Focuses on strict adherence to context and verbatim quotes with page citations.
"""
qa_prompt = PromptTemplate.from_template(
    """You are a helpful multimodal research assistant.
    
    Context: 
    {context}
    
    User Question: {question}
    
    Instructions:
    - Answer based ONLY on the context provided.
    - If the user specifies a file, ignore context from other files.
    - Include exact quotes, page numbers, or precise media timestamps.
    - CRITICAL Citing Guidelines for Media:
       - Audio/Video Playback: If citing a specific timestamp (e.g. 01:20), you MUST format it as: `[Play segment](media://filename#t=80)` where the filename is the raw audio/video filename (e.g. sample.mp4) and t is the start time in total seconds (e.g. 01:20 = 80).
       - Keyframe/Image display: If the context provides a Keyframe URL or image path, you MUST embed it directly using standard markdown image format: `![Keyframe](/storage/extracted_frames/frame_001.jpg)`.
    - CRITICAL MEDIA HANDLING: The 'Context' contains text descriptions of images/media. Treat these descriptions AS IF you are looking directly at the media. DO NOT tell the user you cannot see/view the image.
    - Format your response in clean Markdown (use bold for key terms, lists where appropriate).
    """
)
qa_chain = qa_prompt | llm | StrOutputParser()

# --- Tool 3: Comparator ---
"""
A specialized chain for cross-document analysis.
Forces the output into a Markdown Table format for structured side-by-side comparison.
"""
compare_prompt = PromptTemplate.from_template(
    """You are a data analyst.
    
    User Request: {question}
    
    Context: 
    {context}
    
    Instructions:
    - Compare the documents based on the User Request.
    - If the user asks for specific fields, focus only on those.
    - For audio/video files, cite specific segments or timestamps using: `[Play segment](media://filename#t=seconds)` (e.g. `[Play at 01:10](media://video.mp4#t=70)`).
    - If keyframe/image URLs are present, embed them using: `![Keyframe](/storage/extracted_frames/frame_001.jpg)`.
    - CRITICAL MEDIA HANDLING: The 'Context' contains text descriptions of images/media. Treat these descriptions AS IF you are looking directly at the media. DO NOT tell the user you cannot see/view the image.
    - CRITICAL: Output the result as a Markdown Table.
    - Add a brief analysis below the table in Markdown text.
    """
)
comparator_chain = compare_prompt | llm | StrOutputParser()

# --- Tool 4: Data Extractor ---
"""
A precision-focused chain for pulling specific metrics, lists, or tables.
Avoids conversational filler and focuses purely on structured data extraction.
"""
extract_prompt = PromptTemplate.from_template(
    """You are a data extraction engine.
    
    User Request: {question}
    
    Context: 
    {context}
    
    Instructions:
    - Extract ONLY the data requested by the user.
    - For media files, include timestamps and embed any keyframe/image URLs where appropriate.
    - CRITICAL MEDIA HANDLING: The 'Context' contains text descriptions of images/media. Treat these descriptions AS IF you are looking directly at the media. DO NOT tell the user you cannot see/view the image.
    - Format the output as a Markdown Table or a structured Markdown List.
    - Do not output raw JSON unless explicitly asked.
    """
)
extractor_chain = extract_prompt | llm | StrOutputParser()

# --- Tool 5: Insight Generator ---
"""
A chain for higher-level analysis and consultancy.
Designed to handle strict length constraints and provide actionable recommendations.
"""
insight_prompt = PromptTemplate.from_template(
    """You are a strategic consultant.
    
    User Request: {question}
    
    Context: 
    {context}
    
    Instructions:
    1. Analyze the context (which includes documents, audio/video transcripts, and image descriptions) to provide insights.
    2. Cite precise times/pages and embed visual frame images (`![Keyframe](/storage/extracted_frames/frame_001.jpg)`) if directly relevant to the insights.
    3. CRITICAL MEDIA HANDLING: Treat text descriptions and captions of images/media AS IF you are looking directly at the media. DO NOT tell the user you cannot see/view the image.
    4. CRITICAL: Strictly follow the length constraints in the User Request (e.g., if asked for "2 lines", give exactly 2 lines).
    5. CRITICAL: If the user mentions a specific file name, IGNORE context from all other files.
    6. Provide actionable recommendations based ONLY on the targeted data.
    7. Format the output in professional Markdown.
    """
)
insight_chain = insight_prompt | llm | StrOutputParser()