from __future__ import annotations

import json
from pathlib import Path

from pypdf import PdfReader

from app.config import PROJECT_ROOT

SOURCE_DIR = PROJECT_ROOT / "app" / "sources"
MANIFEST_PATH = SOURCE_DIR / "manifest.json"
INDEX_PATH = SOURCE_DIR / "source_index.json"


def load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def resolve_manifest_local_path(local_path: str | Path) -> Path:
    """Resolve a manifest local_path against the repository project root.

    Relative paths are always joined to PROJECT_ROOT so rebuilds work
    regardless of the current working directory. Absolute paths are returned
    as-is for compatibility, but committed manifests must use relative paths.
    """
    path = Path(local_path)
    if path.is_absolute():
        return path
    return (PROJECT_ROOT / path).resolve()


def extract_pdf_text(pdf_path: Path) -> str:
    text_parts = []
    reader = PdfReader(str(pdf_path))

    for page_number, page in enumerate(reader.pages, start=1):
        page_text = page.extract_text() or ""
        text_parts.append(f"\n\n--- PAGE {page_number} ---\n\n{page_text}")

    return "\n".join(text_parts)


def chunk_text(text: str, chunk_size: int = 1500, overlap: int = 200):
    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        start += chunk_size - overlap

    return chunks


def build_source_index():
    manifest = load_manifest()
    indexed_chunks = []

    for source_id, source in manifest["sources"].items():
        local_path = resolve_manifest_local_path(source["local_path"])

        if local_path.suffix.lower() != ".pdf":
            print(f"Skipping non-PDF: {local_path}")
            continue

        print(f"Parsing {source['name']}...")

        text = extract_pdf_text(local_path)
        chunks = chunk_text(text)

        for i, chunk in enumerate(chunks):
            indexed_chunks.append({
                "source_id": source_id,
                "source_name": source["name"],
                "source_type": source["source_type"],
                "chunk_id": f"{source_id}_{i}",
                "text": chunk
            })

        print(f"Created {len(chunks)} chunks.")

    INDEX_PATH.write_text(json.dumps(indexed_chunks, indent=2), encoding="utf-8")
    print(f"\nSaved index to {INDEX_PATH}")
    print(f"Total chunks: {len(indexed_chunks)}")
