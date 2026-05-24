"""Tool definitions (for Claude) and implementations (for the agent loop)."""

import os
from pathlib import Path

import chromadb
from pypdf import PdfReader
from tavily import TavilyClient

from utils import chunk_text

COLLECTION_NAME = "engineering_docs"
DOCS_DIR = Path("docs")

# ── Tool schemas (sent to Claude) ────────────────────────────────────────────

TOOL_DEFINITIONS = [
    {
        "name": "search_documents",
        "description": (
            "Search the local ChromaDB knowledge base of ingested engineering documents. "
            "Use this when the question is likely answered by the docs already on disk "
            "(datasheets, specs, manuals). Returns the top matching text chunks with sources."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to run against the document knowledge base.",
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": "search_web",
        "description": (
            "Search the web for current or general information not covered by local documents. "
            "Use this for recent events, online specs, or anything the local docs may not contain."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The web search query.",
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": "summarize_document",
        "description": (
            "Load and summarize an entire document by filename. Use this when the user asks "
            "for a high-level overview or summary of a specific file rather than a targeted answer."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "The filename (e.g. 'esp32_datasheet.pdf') to summarize.",
                }
            },
            "required": ["filename"],
        },
    },
]

# ── Tool implementations ──────────────────────────────────────────────────────

def search_documents(query: str) -> str:
    chroma_path = Path(".chroma")
    if not chroma_path.exists():
        return "Error: No ChromaDB found. Run ingest.py first."

    client = chromadb.PersistentClient(path=str(chroma_path))
    try:
        collection = client.get_collection(COLLECTION_NAME)
    except Exception:
        return f"Error: Collection '{COLLECTION_NAME}' not found. Run ingest.py first."

    results = collection.query(query_texts=[query], n_results=5)
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]

    if not docs:
        return "No relevant documents found."

    parts = []
    for doc, meta in zip(docs, metas):
        source = f"{meta.get('filename', 'unknown')} (page {meta.get('page', '?')})"
        parts.append(f"[Source: {source}]\n{doc}")
    return "\n\n---\n\n".join(parts)


def search_web(query: str) -> str:
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return "Error: TAVILY_API_KEY not set in .env"

    client = TavilyClient(api_key=api_key)
    response = client.search(query=query, max_results=5)

    results = response.get("results", [])
    if not results:
        return "No web results found."

    parts = []
    for r in results:
        parts.append(f"[{r.get('title', 'No title')}]\nURL: {r.get('url', '')}\n{r.get('content', '')}")
    return "\n\n---\n\n".join(parts)


def summarize_document(filename: str) -> str:
    candidates = list(DOCS_DIR.rglob(filename)) if DOCS_DIR.exists() else []
    if not candidates:
        return f"Error: '{filename}' not found in {DOCS_DIR}/"

    path = candidates[0]
    try:
        if path.suffix.lower() == ".pdf":
            reader = PdfReader(str(path))
            pages = [page.extract_text() or "" for page in reader.pages]
            full_text = "\n\n".join(pages)
        else:
            full_text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"Error reading '{filename}': {e}"

    # Truncate to ~8000 tokens to stay within context limits
    max_chars = 32_000
    if len(full_text) > max_chars:
        full_text = full_text[:max_chars] + "\n\n[... document truncated for length ...]"

    return f"Full text of '{filename}':\n\n{full_text}"


# ── Dispatch ──────────────────────────────────────────────────────────────────

def run_tool(name: str, inputs: dict) -> str:
    if name == "search_documents":
        return search_documents(inputs["query"])
    if name == "search_web":
        return search_web(inputs["query"])
    if name == "summarize_document":
        return summarize_document(inputs["filename"])
    return f"Error: Unknown tool '{name}'"
