from typing import List
from langchain_core.retrievers import BaseRetriever
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from pydantic import Field

from backend.database.database import search_documents, search_knowledge_graph
from backend.database.vector_db import search_vector_store

def reciprocal_rank_fusion(results_vector: List[Document], results_keyword: List[Document], k: int = 60, top_n: int = 5) -> List[Document]:
    """
    Applies Reciprocal Rank Fusion (RRF) on two retrieved lists of Documents.
    """
    fused_scores = {}
    doc_map = {}
    
    for rank, doc in enumerate(results_vector):
        content = doc.page_content
        doc_map[content] = doc
        fused_scores[content] = fused_scores.get(content, 0) + 1.0 / (k + rank + 1)
        
    for rank, doc in enumerate(results_keyword):
        content = doc.page_content
        doc_map[content] = doc
        fused_scores[content] = fused_scores.get(content, 0) + 1.0 / (k + rank + 1)
        
    sorted_contents = sorted(fused_scores.keys(), key=lambda x: fused_scores[x], reverse=True)
    return [doc_map[content] for content in sorted_contents[:top_n]]

class HybridRetriever(BaseRetriever):
    """
    A Langchain-compatible retriever that performs Hybrid Search (ChromaDB + SQLite BM25)
    and merges it with local Knowledge Graph context (GraphRAG).
    """
    k: int = Field(default=5)
    conversation_id: int = Field(default=None)

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> List[Document]:
        """
        Retrieves hybrid relevance-fused documents and appends Knowledge Graph context.
        """
        # 1. Semantic Vector Search (ChromaDB)
        try:
            vector_docs = search_vector_store(query, conversation_id=self.conversation_id, k=self.k)
        except Exception as e:
            print(f"ChromaDB search failed: {e}")
            vector_docs = []

        # 2. Keyword Search (SQLite FTS5 / BM25)
        try:
            keyword_results = search_documents(query, conversation_id=self.conversation_id, k=self.k)
            keyword_docs = [Document(page_content=content, metadata=meta) for content, meta in keyword_results]
        except Exception as e:
            print(f"SQLite FTS5 search failed: {e}")
            keyword_docs = []

        # 3. Merge results using Reciprocal Rank Fusion
        fused_docs = reciprocal_rank_fusion(vector_docs, keyword_docs, top_n=self.k)

        # 4. Inject Knowledge Graph context (GraphRAG)
        if self.conversation_id is not None:
            try:
                triplets = search_knowledge_graph(query, conversation_id=self.conversation_id, limit=10)
                if triplets:
                    kg_content = "Knowledge Graph Context (Extracted Relationships):\n" + "\n".join(f"- {t}" for t in triplets)
                    kg_doc = Document(
                        page_content=kg_content,
                        metadata={"source": "Knowledge Graph", "media_type": "text"}
                    )
                    # Prepend Knowledge Graph document to context so the LLM parses it first
                    fused_docs.insert(0, kg_doc)
            except Exception as e:
                print(f"Knowledge Graph search failed: {e}")

        return fused_docs

def get_retriever(conversation_id: int = None) -> HybridRetriever:
    """
    Returns an instance of the HybridRetriever.
    """
    return HybridRetriever(k=5, conversation_id=conversation_id)
