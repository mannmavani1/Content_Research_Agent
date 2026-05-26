import sqlite3
import json
from backend.config.settings import settings

def get_db_connection():
    """
    Creates and returns a connection to the SQLite database.
    """
    conn = sqlite3.connect(settings.LOCAL_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """
    Initializes the SQLite database with tables for storing documents and FTS5 indexing.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Table for storing the raw documents and metadata
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                metadata TEXT
            )
        """)
        
        # FTS5 virtual table for full-text search (BM25)
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
                content,
                content='documents',
                content_rowid='id'
            )
        """)
        
        # Triggers to keep FTS index synced with documents table
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS documents_ai AFTER INSERT ON documents BEGIN
                INSERT INTO documents_fts(rowid, content) VALUES (new.id, new.content);
            END;
        """)
        
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS documents_ad AFTER DELETE ON documents BEGIN
                INSERT INTO documents_fts(documents_fts, rowid, content) VALUES('delete', old.id, old.content);
            END;
        """)
        
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS documents_au AFTER UPDATE ON documents BEGIN
                INSERT INTO documents_fts(documents_fts, rowid, content) VALUES('delete', old.id, old.content);
                INSERT INTO documents_fts(rowid, content) VALUES (new.id, new.content);
            END;
        """)
        
        conn.commit()

def add_documents(documents):
    """
    Adds a list of document chunks to the database.
    
    Args:
        documents: A list of Langchain Document objects.
    """
    init_db()  # Ensure tables exist
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        for doc in documents:
            content = doc.page_content
            metadata_str = json.dumps(doc.metadata)
            cursor.execute(
                "INSERT INTO documents (content, metadata) VALUES (?, ?)",
                (content, metadata_str)
            )
        conn.commit()

def search_documents(query: str, k: int = 5):
    """
    Searches the documents using FTS5 (which uses BM25 internally).
    
    Args:
        query: The search string.
        k: The number of results to return.
        
    Returns:
        List of tuples (content, metadata_dict).
    """
    import re
    # Extract only alphanumeric words for the OR query
    tokens = re.findall(r'\b\w+\b', query)
    or_query = " OR ".join(tokens) if tokens else ""
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            results = []
            
            # Try matching with OR for better recall in natural language
            if or_query:
                cursor.execute(f"""
                    SELECT documents.content, documents.metadata, bm25(documents_fts) as score
                    FROM documents_fts
                    JOIN documents ON documents.id = documents_fts.rowid
                    WHERE documents_fts MATCH ?
                    ORDER BY score
                    LIMIT ?
                """, (or_query, k))
                results = cursor.fetchall()
            
            # Fallback: if no keyword match is found (common with generic queries like "summarize this"),
            # return the most recently inserted documents so the LLM has context.
            if not results:
                cursor.execute("""
                    SELECT content, metadata
                    FROM documents
                    ORDER BY id DESC
                    LIMIT ?
                """, (k,))
                results = cursor.fetchall()
            
            docs = []
            for row in results:
                metadata = {}
                if row['metadata']:
                    try:
                        metadata = json.loads(row['metadata'])
                    except json.JSONDecodeError:
                        pass
                docs.append((row['content'], metadata))
                
            return docs
    except sqlite3.OperationalError as e:
        print(f"Search error: {e}")
        return []
