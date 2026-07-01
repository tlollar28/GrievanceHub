from pathlib import Path
from urllib.parse import urljoin
import hashlib
import json
import re
import requests

from app.config import DATA_DIR

SOURCE_DIR = DATA_DIR / "sources"
REGISTRY_PATH = SOURCE_DIR / "source_registry.json"
MANIFEST_PATH = SOURCE_DIR / "manifest.json"


def load_registry():
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))["sources"]


def load_manifest():
    if MANIFEST_PATH.exists():
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {"sources": {}}


def save_manifest(manifest):
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def discover_links(official_page):
    response = requests.get(
        official_page,
        timeout=60,
        headers={"User-Agent": "Mozilla/5.0 GrievanceHub Source Manager"},
    )
    response.raise_for_status()

    links = re.findall(r'href=["\']([^"\']+)["\']', response.text, re.IGNORECASE)
    return [urljoin(official_page, link) for link in links]


def score_link(link, source):
    lower = link.lower()
    score = 0

    for file_type in source["allowed_file_types"]:
        if lower.endswith(file_type):
            score += 10

    for keyword in source["preferred_keywords"]:
        if keyword.lower() in lower:
            score += 5

    return score


def choose_best_link(links, source):
    candidates = []

    for link in links:
        score = score_link(link, source)
        if score > 0:
            candidates.append((score, link))

    candidates.sort(reverse=True)

    if not candidates:
        raise ValueError(f"No downloadable file found for {source['name']}")

    return candidates[0][1]


def download_file(url):
    response = requests.get(
        url,
        timeout=60,
        allow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0 GrievanceHub Source Manager"},
    )
    response.raise_for_status()
    return response


def update_source(source, manifest):
    print(f"\nChecking {source['name']}...")

    links = discover_links(source["official_page"])
    download_url = choose_best_link(links, source)

    print(f"Selected URL: {download_url}")

    response = download_file(download_url)
    content = response.content
    file_hash = sha256(content)

    existing = manifest["sources"].get(source["id"])
    if existing and existing.get("sha256") == file_hash:
        print("Unchanged.")
        return

    suffix = Path(download_url).suffix or ".bin"
    file_name = f"{source['id']}{suffix}"
    save_path = SOURCE_DIR / source["save_folder"] / file_name
    save_path.parent.mkdir(parents=True, exist_ok=True)
    save_path.write_bytes(content)

    manifest["sources"][source["id"]] = {
        "name": source["name"],
        "source_type": source["source_type"],
        "official_page": source["official_page"],
        "download_url": download_url,
        "final_url": response.url,
        "local_path": str(save_path),
        "sha256": file_hash,
        "content_type": response.headers.get("content-type"),
    }

    print(f"Saved: {save_path}")


def update_all_sources():
    manifest = load_manifest()

    for source in load_registry():
        try:
            update_source(source, manifest)
        except Exception as e:
            print(f"FAILED: {source['name']}")
            print(e)

    save_manifest(manifest)
    print("\nSource update complete.")