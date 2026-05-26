from typing import List
from langchain_core.retrievers import BaseRetriever
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from pydantic import Field

from backend.database.database import search_documents

class VectorlessRetriever(BaseRetriever):
    """
    A Langchain-compatible retriever that uses local SQLite FTS5 for vectorless search.
    """
    k: int = Field(default=5)

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> List[Document]:
        """
        Retrieves documents matching the query using full-text search.
        """
        results = search_documents(query, k=self.k)
        
        documents = []
        for content, metadata in results:
            documents.append(Document(page_content=content, metadata=metadata))
            
        return documents

def get_retriever() -> VectorlessRetriever:
    """
    Returns an instance of the VectorlessRetriever.
    """
    return VectorlessRetriever(k=5)
