# 🧠 Content Research Agent

A powerful **RAG (Retrieval-Augmented Generation)** application designed to perform deep research on uploaded documents. Built with **FastAPI**, **LangGraph**, and **Groq**, it uses an intelligent agentic workflow to route user queries to the best tool.

---

## 🚀 Features

-   **📄 Multi-Format Ingestion**: Upload PDF, DOCX, TXT, PPTX, or Paste Text directly.
-   **🗄️ Vector Memory**: Automatically chunks and embeds content into a **ChromaDB** vector store.
-   **🤖 Agentic Workflow**: Uses **LangGraph** to dynamically decide if a query needs:
    -   `Summarizer`: Concise overviews of large docs.
    -   `Comparator`: Side-by-side analysis of multiple files.
    -   `Extractor`: Pulling specific data points or tables.
    -   `Q&A`: General factual answers grounded in the data.
-   **⚡ High-Speed Inference**: Utilizes **Groq**'s high-speed API with Llama 3 models for near-instant analytical responses.
-   **🔌 API-First**: Fully documented REST API built with **FastAPI**.
-   **🖥️ Built-in Frontend**: Simple HTML/JS interface for immediate testing.

---

## 🛠️ Tech Stack

-   **Backend**: Python 3.12+, FastAPI
-   **AI/LLM Logic**: LangChain, LangGraph, Groq
-   **Database**: ChromaDB (Vector Store)
-   **Processing**: Unstructured, PyPDF, TikToken

---

## 📂 Project Structure

```text
Content_Research_Agent/
├── backend/
│   ├── agent/          # LangGraph workflow, nodes, and specialized tool chains
│   ├── config/         # Global settings, directory paths, and model configurations
│   ├── database/       # ChromaDB vector store initialization and retrieval logic
│   ├── routers/        # FastAPI endpoint definitions (Ingestion & Chat)
│   ├── schemas/        # Pydantic models for API request/response validation
│   └── services/       # Core business logic (File processing & LLM factory)
├── frontend/           # Static assets (HTML, CSS, and vanilla JavaScript)
├── storage/            # Local persistent storage for uploads and the Vector DB
├── main.py             # Main entry point and server configuration
├── requirements.txt    # List of Python dependencies
└── .env                # Private API keys and secrets (Git ignored)
```
---

## 📦 Installation

### 1. Clone the Repository
```bash
git clone [https://github.com/mannmavani1/Content_Research_Agent.git]
cd Content_Research_Agent
```

### 2. Set Up Environment
It is recommended to use a virtual environment to keep your project dependencies isolated.

```bash
python -m venv venv
source venv/bin/activate  # On macOS/Linux
# venv\Scripts\activate   # On Windows
```

### 3. Install Dependencies
Install the required libraries using pip or uv:

```bash
# Using standard pip
pip install -r requirements.txt

# OR using uv (for faster installation)
uv pip install -r requirements.txt
```

### 4. Configure Environment Variables
The application requires API keys to interact with the LLMs. These are stored in a local `.env` file which is ignored by version control for security.

1.  **Create the file** in the root directory:
```bash
touch .env
```

2.  **Add your credentials**: Open the `.env` file and add your keys.
```bash
    # Get yours at: [https://console.groq.com/](https://console.groq.com/)
    GROQ_API_KEY=your_groq_api_key_here
```

---

## 🚦 Usage

### 1. Start the Backend Server
The backend is powered by FastAPI and Uvicorn. Running this command starts the API and serves the frontend interface simultaneously.

```bash
python -m uvicorn main:app --reload
```

### 2. Access the Application
Once the server is running (typically at port 8000), you can access the following:

* **User Interface**: [http://localhost:8000](http://localhost:8000)
    * *Upload documents, paste text, and use the research tools via the chat interface.*
* **Interactive API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
    * *Automatically generated Swagger UI to test individual endpoints and view data schemas.*

---
