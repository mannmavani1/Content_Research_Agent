import json
import re
import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select, insert, update, delete, func, text, or_
from sqlalchemy.orm import selectinload

from backend.config.settings import settings
from backend.database.models import User, Workspace, Conversation, Message, Document, KnowledgeGraph, DocumentTask

engine = create_async_engine(settings.POSTGRES_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)

async def init_db():
    pass # Handled by Alembic

async def get_or_create_user(workos_id: str, email: str, first_name: str, last_name: str) -> User:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.workos_id == workos_id))
        user = result.scalar_one_or_none()
        
        if not user:
            user = User(workos_id=workos_id, email=email, first_name=first_name, last_name=last_name)
            session.add(user)
            await session.commit()
            await session.refresh(user)
            
            # Create personal workspace
            workspace = Workspace(name="Personal Workspace", owner_id=user.id)
            session.add(workspace)
            await session.commit()
        return user

async def get_user_workspace(user_id: int) -> Workspace:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Workspace).where(Workspace.owner_id == user_id).order_by(Workspace.id.asc()))
        return result.scalars().first()

async def create_conversation(workspace_id: int, title: str = "New Chat") -> dict:
    async with AsyncSessionLocal() as session:
        conv = Conversation(workspace_id=workspace_id, title=title)
        session.add(conv)
        await session.commit()
        await session.refresh(conv)
        return {"id": conv.id, "title": conv.title, "workspace_id": conv.workspace_id}

async def get_conversations(workspace_id: int) -> list:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Conversation).where(Conversation.workspace_id == workspace_id).order_by(Conversation.updated_at.desc())
        )
        convs = result.scalars().all()
        return [{"id": c.id, "title": c.title, "workspace_id": c.workspace_id, "created_at": c.created_at, "updated_at": c.updated_at} for c in convs]

async def get_conversation(conversation_id: int) -> dict | None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Conversation).where(Conversation.id == conversation_id))
        conv = result.scalar_one_or_none()
        if conv:
            return {"id": conv.id, "title": conv.title, "workspace_id": conv.workspace_id, "created_at": conv.created_at, "updated_at": conv.updated_at}
        return None

async def verify_conversation_owner(conversation_id: int, workspace_id: int) -> bool:
    conv = await get_conversation(conversation_id)
    if not conv:
        return False
    return conv["workspace_id"] == workspace_id

async def delete_conversation(conversation_id: int, workspace_id: int):
    async with AsyncSessionLocal() as session:
        # 1. Query all documents in this workspace to find ones associated with this conversation
        stmt = select(Document).where(Document.workspace_id == workspace_id)
        result = await session.execute(stmt)
        docs = result.scalars().all()

        doc_ids_to_delete = []
        files_to_check = set()

        for doc in docs:
            meta = doc.metadata_json or {}
            if meta.get("conversation_id") == conversation_id:
                doc_ids_to_delete.append(doc.id)
                source = meta.get("source", "")
                if source:
                    files_to_check.add(source)

        # 2. Check if files are used by other conversations in this workspace
        if files_to_check:
            other_docs = [d for d in docs if d.id not in doc_ids_to_delete]
            other_sources = set()
            for od in other_docs:
                m = od.metadata_json or {}
                s = m.get("source", "")
                if s:
                    other_sources.add(s)
                    other_sources.add(os.path.basename(s))

            for file_target in files_to_check:
                file_name = os.path.basename(file_target)
                if file_target not in other_sources and file_name not in other_sources:
                    # Remove physical file if no other documents reference it
                    cand_path = file_target if os.path.isabs(file_target) else os.path.join(settings.UPLOAD_DIR, file_name)
                    if os.path.exists(cand_path):
                        try:
                            os.remove(cand_path)
                        except Exception as e:
                            print(f"Failed to remove physical file {cand_path}: {e}")

        # 3. Delete Document records & their linked Knowledge Graph triplets
        if doc_ids_to_delete:
            await session.execute(delete(KnowledgeGraph).where(KnowledgeGraph.chunk_id.in_(doc_ids_to_delete)))
            await session.execute(delete(Document).where(Document.id.in_(doc_ids_to_delete)))

        # 4. Delete the conversation itself (cascades to messages & conversation knowledge graph)
        await session.execute(
            delete(Conversation).where(Conversation.id == conversation_id, Conversation.workspace_id == workspace_id)
        )
        await session.commit()

    # 5. Clean up Chroma vector store for this conversation
    try:
        from backend.database.vector_db import delete_vector_store_conversation
        delete_vector_store_conversation(conversation_id, workspace_id=workspace_id)
    except Exception as e:
        print(f"Failed to delete vector store records for conversation {conversation_id}: {e}")


async def rename_conversation(conversation_id: int, new_title: str, workspace_id: int):
    async with AsyncSessionLocal() as session:
        await session.execute(
            update(Conversation).where(Conversation.id == conversation_id, Conversation.workspace_id == workspace_id).values(title=new_title)
        )
        await session.commit()

async def add_message(conversation_id: int, role: str, content: str):
    async with AsyncSessionLocal() as session:
        msg = Message(conversation_id=conversation_id, role=role, content=content)
        session.add(msg)
        await session.execute(update(Conversation).where(Conversation.id == conversation_id).values(updated_at=func.now()))
        await session.commit()

async def get_messages(conversation_id: int, workspace_id: int) -> list:
    is_owner = await verify_conversation_owner(conversation_id, workspace_id)
    if not is_owner:
        return []
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Message).where(Message.conversation_id == conversation_id).order_by(Message.id.asc())
        )
        messages = result.scalars().all()
        return [{"id": m.id, "role": m.role, "content": m.content, "timestamp": m.timestamp} for m in messages]

async def add_documents(documents, workspace_id: int) -> list:
    inserted_ids = []
    async with AsyncSessionLocal() as session:
        for doc in documents:
            content = doc.page_content
            metadata_json = doc.metadata
            db_doc = Document(workspace_id=workspace_id, content=content, metadata_json=metadata_json)
            db_doc.search_vector = func.to_tsvector('english', content)
            session.add(db_doc)
            await session.flush()
            inserted_ids.append(db_doc.id)
        await session.commit()
    return inserted_ids

async def add_triplets(triplets: list, conversation_id: int, chunk_id: int = None):
    async with AsyncSessionLocal() as session:
        for s, p, o in triplets:
            kg = KnowledgeGraph(subject=s, predicate=p, object_=o, chunk_id=chunk_id, conversation_id=conversation_id)
            session.add(kg)
        await session.commit()

async def search_knowledge_graph(query: str, conversation_id: int, limit: int = 15) -> list:
    tokens = re.findall(r'\b\w{3,}\b', query.lower())
    if not tokens:
        return []
    
    async with AsyncSessionLocal() as session:
        conditions = []
        for token in tokens:
            conditions.append(KnowledgeGraph.subject.ilike(f"%{token}%"))
            conditions.append(KnowledgeGraph.object_.ilike(f"%{token}%"))
        
        result = await session.execute(
            select(KnowledgeGraph)
            .where(KnowledgeGraph.conversation_id == conversation_id)
            .where(or_(*conditions))
            .limit(limit)
        )
        rows = result.scalars().all()
        return [f"({row.subject} --[{row.predicate}]--> {row.object_})" for row in rows]

async def search_documents(query: str, workspace_id: int, limit: int = 5):
    tokens = re.findall(r'\b\w+\b', query)
    ts_query = " | ".join(tokens) if tokens else ""

    async with AsyncSessionLocal() as session:
        results = []
        if ts_query:
            stmt = (
                select(Document, func.ts_rank_cd(Document.search_vector, func.to_tsquery('english', ts_query)).label('rank'))
                .where(Document.workspace_id == workspace_id)
                .where(Document.search_vector.op('@@')(func.to_tsquery('english', ts_query)))
                .order_by(text('rank DESC'))
                .limit(limit)
            )
            try:
                res = await session.execute(stmt)
                for row in res:
                    results.append((row.Document.content, row.Document.metadata_json))
            except Exception as e:
                print(f"TSQuery error: {e}")

        if not results:
            stmt = select(Document).where(Document.workspace_id == workspace_id).order_by(Document.id.desc()).limit(limit)
            res = await session.execute(stmt)
            for doc in res.scalars():
                results.append((doc.content, doc.metadata_json))

        return results

async def delete_document_chunks(filename: str, workspace_id: int, conversation_id: int = None) -> int:
    async with AsyncSessionLocal() as session:
        stmt = select(Document).where(Document.workspace_id == workspace_id)
        result = await session.execute(stmt)
        docs = result.scalars().all()

        ids_to_delete = []
        for doc in docs:
            meta = doc.metadata_json or {}
            if conversation_id is not None and meta.get("conversation_id") != conversation_id:
                continue
            source = meta.get("source", "")
            if os.path.basename(source) == filename or source == filename:
                ids_to_delete.append(doc.id)

        if ids_to_delete:
            await session.execute(delete(KnowledgeGraph).where(KnowledgeGraph.chunk_id.in_(ids_to_delete)))
            await session.execute(delete(Document).where(Document.id.in_(ids_to_delete)))
            await session.commit()
            return len(ids_to_delete)
        return 0

async def delete_all_documents(workspace_id: int):
    async with AsyncSessionLocal() as session:
        stmt = select(Conversation.id).where(Conversation.workspace_id == workspace_id)
        res = await session.execute(stmt)
        conv_ids = res.scalars().all()
        if conv_ids:
            await session.execute(delete(KnowledgeGraph).where(KnowledgeGraph.conversation_id.in_(conv_ids)))
        
        await session.execute(delete(Document).where(Document.workspace_id == workspace_id))
        await session.commit()

async def get_files_for_workspace(workspace_id: int, conversation_id: int = None) -> list:
    async with AsyncSessionLocal() as session:
        stmt = select(Document.metadata_json).where(Document.workspace_id == workspace_id)
        res = await session.execute(stmt)
        files = set()
        for metadata_json in res.scalars():
            if metadata_json:
                if conversation_id is not None and metadata_json.get("conversation_id") != conversation_id:
                    continue
                source = metadata_json.get("source", "")
                if source:
                    files.add(os.path.basename(source))
        return list(files)

async def get_files_for_conversation(workspace_id: int, conversation_id: int) -> list:
    return await get_files_for_workspace(workspace_id, conversation_id=conversation_id)


async def create_document_task(workspace_id: int, filename: str, conversation_id: int = None) -> int:
    async with AsyncSessionLocal() as session:
        task = DocumentTask(
            workspace_id=workspace_id,
            conversation_id=conversation_id,
            filename=filename,
            status="PENDING",
            chunks_processed=0
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)
        return task.id


async def update_document_task_status(task_id: int, status: str, chunks_processed: int = 0, error_message: str = None):
    async with AsyncSessionLocal() as session:
        values = {"status": status, "updated_at": func.now()}
        if chunks_processed:
            values["chunks_processed"] = chunks_processed
        if error_message is not None:
            values["error_message"] = error_message
        await session.execute(
            update(DocumentTask).where(DocumentTask.id == task_id).values(**values)
        )
        await session.commit()


async def get_document_task(task_id: int, workspace_id: int = None) -> dict | None:
    async with AsyncSessionLocal() as session:
        stmt = select(DocumentTask).where(DocumentTask.id == task_id)
        if workspace_id is not None:
            stmt = stmt.where(DocumentTask.workspace_id == workspace_id)
        result = await session.execute(stmt)
        task = result.scalar_one_or_none()
        if not task:
            return None
        return {
            "id": task.id,
            "workspace_id": task.workspace_id,
            "conversation_id": task.conversation_id,
            "filename": task.filename,
            "status": task.status,
            "error_message": task.error_message,
            "chunks_processed": task.chunks_processed,
            "created_at": task.created_at,
            "updated_at": task.updated_at
        }


