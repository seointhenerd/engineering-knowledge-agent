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


if __name__ == "__main__":
    if len(sys.argv) != 2:
        console.print("Usage: python ingest.py <file_or_folder>")
        sys.exit(1)
    ingest(sys.argv[1])
