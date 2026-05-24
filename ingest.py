#!/usr/bin/env python3
"""Ingest PDF and text documents into ChromaDB."""

import sys
import hashlib
from pathlib import Path

import chromadb
from pypdf import PdfReader
from rich.console import Console
from rich.progress import track

from utils import chunk_text

console = Console()
COLLECTION_NAME = "engineering_docs"


def extract_text_pdf(path: Path) -> list[tuple[str, int]]:
    """Return list of (page_text, page_number) tuples."""
    reader = PdfReader(str(path))
    return [(page.extract_text() or "", i + 1) for i, page in enumerate(reader.pages)]


def extract_text_plain(path: Path) -> list[tuple[str, int]]:
    return [(path.read_text(encoding="utf-8", errors="replace"), 1)]


def collect_files(target: Path) -> list[Path]:
    if target.is_file():
        return [target]
    return [p for p in target.rglob("*") if p.suffix.lower() in {".pdf", ".txt", ".md"}]


def ingest(target_path: str) -> None:
    target = Path(target_path)
    if not target.exists():
        console.print(f"[red]Path not found:[/red] {target}")
        sys.exit(1)

    files = collect_files(target)
    if not files:
        console.print("[yellow]No PDF or text files found.[/yellow]")
        sys.exit(0)

    client = chromadb.PersistentClient(path=".chroma")
    collection = client.get_or_create_collection(COLLECTION_NAME)

    total_chunks = 0

    for file in track(files, description="Ingesting files..."):
        try:
            if file.suffix.lower() == ".pdf":
                pages = extract_text_pdf(file)
            else:
                pages = extract_text_plain(file)
        except Exception as e:
            console.print(f"[red]Error reading {file.name}:[/red] {e}")
            continue

        for page_text, page_num in pages:
            chunks = chunk_text(page_text)
            for i, chunk in enumerate(chunks):
                chunk_id = hashlib.md5(f"{file.name}:{page_num}:{i}:{chunk[:50]}".encode()).hexdigest()
                collection.upsert(
                    ids=[chunk_id],
                    documents=[chunk],
                    metadatas=[{"filename": file.name, "page": page_num, "chunk_index": i}],
                )
                total_chunks += 1

    console.print(f"\n[green]Done.[/green] Ingested [bold]{total_chunks}[/bold] chunks from [bold]{len(files)}[/bold] file(s) into '{COLLECTION_NAME}'.")


def remove_document(filename: str) -> None:
    client = chromadb.PersistentClient(path=".chroma")
    try:
        collection = client.get_collection(COLLECTION_NAME)
    except Exception:
        console.print(f"[red]Collection '{COLLECTION_NAME}' not found.[/red]")
        sys.exit(1)

    collection.delete(where={"filename": filename})
    console.print(f"[green]Removed[/green] all chunks for '[bold]{filename}[/bold]'.")


def reset() -> None:
    client = chromadb.PersistentClient(path=".chroma")
    try:
        client.delete_collection(COLLECTION_NAME)
        console.print(f"[green]Reset complete.[/green] Collection '{COLLECTION_NAME}' deleted.")
    except Exception:
        console.print("[yellow]Collection not found — nothing to reset.[/yellow]")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        console.print("Usage:")
        console.print("  python ingest.py <file_or_folder>       — ingest documents")
        console.print("  python ingest.py --remove <filename>    — remove one document")
        console.print("  python ingest.py --reset                — wipe entire collection")
        sys.exit(1)

    if sys.argv[1] == "--reset":
        reset()
    elif sys.argv[1] == "--remove":
        if len(sys.argv) != 3:
            console.print("Usage: python ingest.py --remove <filename>")
            sys.exit(1)
        remove_document(sys.argv[2])
    else:
        ingest(sys.argv[1])
