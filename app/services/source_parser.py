from pathlib import Path
import json
import PyPDF2

BASE_DIR = Path(__file__).resolve().parent.parent
SOURCE_DIR = BASE_DIR / "sources"
MANIFEST_PATH = SOURCE_DIR / "manifest.json"
INDEX_PATH = SOURCE_DIR / "source_index.json"


def load_manifest():
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def extract_pdf_text(pdf_path: Path) -> str:
    text_parts = []

    with pdf_path.open("rb") as file:
        reader = PyPDF2.PdfReader(file)

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
        local_path = Path(source["local_path"])

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