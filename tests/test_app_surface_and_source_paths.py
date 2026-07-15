"""GrievanceHub app surface and portable source-path tests."""

from pathlib import Path

from fastapi.testclient import TestClient

from app.config import PROJECT_ROOT
from app.main import app
from app.services.source_parser import load_manifest, resolve_manifest_local_path

client = TestClient(app)

ALLOWED_OPENAPI_PREFIXES = (
    "/health",
    "/cases",
    "/sources",
    "/docs",
    "/redoc",
    "/openapi.json",
)


def _openapi_paths() -> set[str]:
    return set(client.get("/openapi.json").json()["paths"])


def test_health_route():
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "healthy"
    assert payload["service"] == "GrievanceHub"


def test_openapi_surface_is_grievancehub_only():
    """OpenAPI must expose only GrievanceHub health/cases/sources surfaces."""
    paths = _openapi_paths()
    for path in paths:
        assert any(
            path == prefix or path.startswith(prefix.rstrip("/") + "/") or path.startswith(prefix + "/")
            for prefix in ALLOWED_OPENAPI_PREFIXES
        ) or path in ALLOWED_OPENAPI_PREFIXES, f"unexpected route: {path}"


def test_grievance_routers_registered():
    paths = _openapi_paths()
    assert "/health" in paths
    assert any(path.startswith("/cases") for path in paths)
    assert any(path.startswith("/sources") for path in paths)
    assert any("/export/" in path for path in paths)


def test_manifest_local_paths_are_portable():
    manifest = load_manifest()
    assert "sources" in manifest
    for source_id, source in manifest["sources"].items():
        local_path = source["local_path"]
        path = Path(local_path)
        assert not path.is_absolute(), f"{source_id} path must be relative: {local_path}"
        normalized = local_path.replace("/", "\\")
        assert "Users\\" not in normalized
        assert "/Users/" not in local_path
        assert ":" not in local_path.split("/", 1)[0]
        assert not normalized.lower().startswith("c:\\")
        assert local_path.replace("\\", "/").startswith("app/sources/")


def test_resolve_manifest_local_path_uses_project_root(tmp_path, monkeypatch):
    relative = "app/sources/contract/2022-2025-NPMHU-National-Agreement.pdf"
    resolved = resolve_manifest_local_path(relative)
    assert resolved == (PROJECT_ROOT / relative).resolve()
    assert resolved.is_absolute()

    # Resolution must not depend on the process working directory.
    monkeypatch.chdir(tmp_path)
    resolved_from_other_cwd = resolve_manifest_local_path(relative)
    assert resolved_from_other_cwd == resolved


def test_expected_manifest_source_paths():
    manifest = load_manifest()
    expected = {
        "usps_elm_55": "app/sources/elm/elm55.zip",
        "npmhu_national_agreement_2022_2025": (
            "app/sources/contract/2022-2025-NPMHU-National-Agreement.pdf"
        ),
        "npmhu_cim_v6": "app/sources/cim/CIM-V6.pdf",
    }
    for source_id, expected_path in expected.items():
        assert manifest["sources"][source_id]["local_path"] == expected_path
        resolved = resolve_manifest_local_path(expected_path)
        assert resolved == (PROJECT_ROOT / expected_path).resolve()
