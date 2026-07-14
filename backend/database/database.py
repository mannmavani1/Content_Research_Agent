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
        
        # Table for storing conversation sessions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                user_id TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Ensure user_id column exists for existing DBs
        cursor.execute("PRAGMA table_info(conversations)")
        columns = [column[1] for column in cursor.fetchall()]
        if "user_id" not in columns:
            cursor.execute("ALTER TABLE conversations ADD COLUMN user_id TEXT NOT NULL DEFAULT ''")
        
        # Table for storing messages within a conversation
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (conversation_id) REFERENCES conversations (id) ON DELETE CASCADE
            )
        """)

        # Table for storing Knowledge Graph Triplets (GraphRAG)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_graph (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject TEXT NOT NULL,
                predicate TEXT NOT NULL,
                object TEXT NOT NULL,
                chunk_id INTEGER,
                conversation_id INTEGER NOT NULL,
                FOREIGN KEY (conversation_id) REFERENCES conversations (id) ON DELETE CASCADE
            )
        """)
        
        conn.commit()

def create_conversation(title: str = "New Chat", user_id: str = "") -> dict:
    """Creates a new conversation session for a specific user."""
    init_db()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO conversations (title, user_id) VALUES (?, ?)", (title, user_id))
        conn.commit()
        return {"id": cursor.lastrowid, "title": title, "user_id": user_id}

def get_conversations(user_id: str = None) -> list:
    """Returns a list of conversations for a user ordered by recent activity."""
    init_db()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if user_id is not None:
            cursor.execute(
                "SELECT id, title, user_id, created_at, updated_at FROM conversations WHERE user_id = ? ORDER BY updated_at DESC",
                (user_id,)
            )
        else:
            cursor.execute("SELECT id, title, user_id, created_at, updated_at FROM conversations ORDER BY updated_at DESC")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

def get_conversation(conversation_id: int) -> dict | None:
    """Returns details of a specific conversation session."""
    init_db()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, title, user_id, created_at, updated_at FROM conversations WHERE id = ?", (conversation_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def verify_conversation_owner(conversation_id: int, user_id: str) -> bool:
    """Verifies whether a conversation session belongs to the given user ID."""
    conv = get_conversation(conversation_id)
    if not conv:
        return False
    # If conversation has an assigned user_id, it must match
    if conv["user_id"] and conv["user_id"] != user_id:
        return False
    return True

def delete_conversation(conversation_id: int, user_id: str = None):
    """Deletes a conversation and all its messages via ON DELETE CASCADE if authorized."""
    init_db()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if user_id is not None:
            cursor.execute("DELETE FROM conversations WHERE id = ? AND user_id = ?", (conversation_id, user_id))
        else:
            cursor.execute("DELETE TABLE conversations WHERE id = ?", (conversation_id,))
        conn.commit()

def rename_conversation(conversation_id: int, new_title: str, user_id: str = None):
    """Updates the title of a conversation if authorized."""
    init_db()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if user_id is not None:
            cursor.execute("UPDATE conversations SET title = ? WHERE id = ? AND user_id = ?", (new_title, conversation_id, user_id))
        else:
            cursor.execute("UPDATE conversations SET title = ? WHERE id = ?", (new_title, conversation_id))
        conn.commit()

def add_message(conversation_id: int, role: str, content: str):
    """Appends a message to a conversation and updates the conversation timestamp."""
    init_db()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)",
            (conversation_id, role, content)
        )
        cursor.execute(
            "UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (conversation_id,)
        )
        conn.commit()

def get_messages(conversation_id: int, user_id: str = None) -> list:
    """Returns all messages for a specific conversation in chronological order if owned by user."""
    init_db()
    if user_id is not None and not verify_conversation_owner(conversation_id, user_id):
        return []
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, role, content, timestamp FROM messages WHERE conversation_id = ? ORDER BY id ASC",
            (conversation_id,)
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

def add_documents(documents) -> list:
    """
    Adds a list of document chunks to the database.
    
    Args:
        documents: A list of Langchain Document objects.
        
    Returns:
        List of inserted document IDs.
    """
    init_db()  # Ensure tables exist
    
    inserted_ids = []
    with get_db_connection() as conn:
        cursor = conn.cursor()
        for doc in documents:
            content = doc.page_content
            metadata_str = json.dumps(doc.metadata)
            cursor.execute(
                "INSERT INTO documents (content, metadata) VALUES (?, ?)",
                (content, metadata_str)
            )
            inserted_ids.append(cursor.lastrowid)
        conn.commit()
    return inserted_ids

def add_triplets(triplets: list, conversation_id: int, chunk_id: int = None):
    """
    Adds a list of (subject, predicate, object) triplets to the knowledge graph SQLite table.
    """
    init_db()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        for s, p, o in triplets:
            cursor.execute(
                "INSERT INTO knowledge_graph (subject, predicate, object, chunk_id, conversation_id) VALUES (?, ?, ?, ?, ?)",
                (s, p, o, chunk_id, conversation_id)
            )
        conn.commit()

def search_knowledge_graph(query: str, conversation_id: int, limit: int = 15) -> list:
    """
    Queries the knowledge graph SQLite table for triplets matching terms in the query.
    """
    init_db()
    import re
    tokens = re.findall(r'\b\w{3,}\b', query.lower()) # words of length >= 3
    if not tokens:
        return []
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Search for tokens matching subject or object
        conditions = []
        params = [conversation_id]
        for token in tokens:
            conditions.append("LOWER(subject) LIKE ?")
            conditions.append("LOWER(object) LIKE ?")
            params.append(f"%{token}%")
            params.append(f"%{token}%")
        
        where_clause = " OR ".join(conditions)
        sql = f"""
            SELECT subject, predicate, object 
            FROM knowledge_graph 
            WHERE conversation_id = ? AND ({where_clause})
            LIMIT ?
        """
        cursor.execute(sql, params + [limit])
        rows = cursor.fetchall()
        return [f"({row['subject']} --[{row['predicate']}]--> {row['object']})" for row in rows]

def search_documents(query: str, conversation_id: int = None, k: int = 5):
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
                if conversation_id is not None:
                    cursor.execute(f"""
                        SELECT documents.content, documents.metadata, bm25(documents_fts) as score
                        FROM documents_fts
                        JOIN documents ON documents.id = documents_fts.rowid
                        WHERE documents_fts MATCH ? AND json_extract(documents.metadata, '$.conversation_id') = ?
                        ORDER BY score
                        LIMIT ?
                    """, (or_query, conversation_id, k))
                else:
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
                if conversation_id is not None:
                    cursor.execute("""
                        SELECT content, metadata
                        FROM documents
                        WHERE json_extract(metadata, '$.conversation_id') = ?
                        ORDER BY id DESC
                        LIMIT ?
                    """, (conversation_id, k))
                else:
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

def delete_document_chunks(filename: str, conversation_id: int = None) -> int:
    """
    Deletes all chunks associated with a specific filename from the SQLite database.
    """
    import os
    init_db()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, metadata FROM documents")
        rows = cursor.fetchall()
        
        ids_to_delete = []
        for row in rows:
            try:
                meta = json.loads(row['metadata']) if row['metadata'] else {}
                source = meta.get("source", "")
                doc_conv_id = meta.get("conversation_id")
                
                # If conversation_id is provided, only delete chunks for that conversation
                if conversation_id is not None and doc_conv_id != conversation_id:
                    continue
                    
                if os.path.basename(source) == filename or source == filename:
                    ids_to_delete.append(row['id'])
            except Exception:
                continue
        
        if ids_to_delete:
            placeholders = ",".join("?" for _ in ids_to_delete)
            cursor.execute(f"DELETE FROM documents WHERE id IN ({placeholders})", ids_to_delete)
            cursor.execute(f"DELETE FROM knowledge_graph WHERE chunk_id IN ({placeholders})", ids_to_delete)
            conn.commit()
            return len(ids_to_delete)
        return 0

def delete_all_documents(conversation_id: int = None):
    """
    Deletes all records from the documents table, keeping conversations intact.
    If conversation_id is provided, only deletes documents for that session.
    """
    init_db()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if conversation_id is not None:
            # Requires querying to find IDs because json_extract might not be indexed for DELETE
            cursor.execute("SELECT id FROM documents WHERE json_extract(metadata, '$.conversation_id') = ?", (conversation_id,))
            rows = cursor.fetchall()
            ids_to_delete = [row['id'] for row in rows]
            if ids_to_delete:
                placeholders = ",".join("?" for _ in ids_to_delete)
                cursor.execute(f"DELETE FROM documents WHERE id IN ({placeholders})", ids_to_delete)
            cursor.execute("DELETE FROM knowledge_graph WHERE conversation_id = ?", (conversation_id,))
        else:
            cursor.execute("DELETE FROM documents")
            cursor.execute("DELETE FROM knowledge_graph")
        conn.commit()

def get_files_for_conversation(conversation_id: int) -> list:
    """
    Returns a list of distinct filenames active for a specific conversation.
    """
    import os
    init_db()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT metadata FROM documents WHERE json_extract(metadata, '$.conversation_id') = ?", (conversation_id,))
        rows = cursor.fetchall()
        
        files = set()
        for row in rows:
            try:
                meta = json.loads(row['metadata']) if row['metadata'] else {}
                source = meta.get("source", "")
                if source:
                    files.add(os.path.basename(source))
            except Exception:
                pass
        return list(files)
