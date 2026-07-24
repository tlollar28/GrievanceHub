"""Interim API-key authentication for externally reachable routes.

This is not a multi-user identity system. There is no persisted User/Role model
in the repository. Until a product identity provider is chosen, source and
retrieval endpoints require server-configured API keys:

- ``GRIEVANCEHUB_API_KEY`` — read-only retrieval and source inspection
- ``GRIEVANCEHUB_ADMIN_API_KEY`` — source mutation, sync, process, upload

Trusted internal service callers do not use these dependencies; they must call
explicitly named internal helpers that construct a trusted authorization
context in code.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass
from typing import Literal

from fastapi import Header, HTTPException, status

from app.services.retrieval.models import RetrievalAuthorizationContext

PrincipalRole = Literal["read", "admin"]


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    """Server-derived caller identity for interim API-key auth."""

    principal_id: str
    role: PrincipalRole
    correlation_id: str | None = None

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    def retrieval_authorization(self) -> RetrievalAuthorizationContext:
        """Bind retrieval scope to the authenticated principal.

        Organization membership is not modeled. External callers receive
        global-corpus access only. Organization IDs, admin flags, and
        allow_all_organizations cannot be supplied by the client.
        """
        return RetrievalAuthorizationContext(
            authenticated=True,
            principal_id=self.principal_id,
            allow_global_sources=True,
            allowed_organization_ids=frozenset(),
            is_admin=False,
            allow_all_organizations=False,
            correlation_id=self.correlation_id,
        )


def _configured_read_key() -> str | None:
    value = os.getenv("GRIEVANCEHUB_API_KEY")
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _configured_admin_key() -> str | None:
    value = os.getenv("GRIEVANCEHUB_ADMIN_API_KEY")
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _extract_presented_secret(
    authorization: str | None,
    x_api_key: str | None,
) -> str | None:
    if x_api_key and x_api_key.strip():
        return x_api_key.strip()
    if authorization and authorization.strip():
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() == "bearer" and token.strip():
            return token.strip()
    return None


def _fingerprint(secret: str) -> str:
    digest = hashlib.sha256(secret.encode("utf-8")).hexdigest()[:16]
    return digest


def _matches(presented: str, expected: str) -> bool:
    return hmac.compare_digest(
        presented.encode("utf-8"),
        expected.encode("utf-8"),
    )


def authenticate_principal(
    *,
    authorization: str | None = None,
    x_api_key: str | None = None,
    require_admin: bool = False,
) -> AuthenticatedPrincipal:
    """Validate credentials and return a server-derived principal.

    Fail closed when credentials are missing/invalid or when the required
    server key is not configured.
    """
    read_key = _configured_read_key()
    admin_key = _configured_admin_key()
    presented = _extract_presented_secret(authorization, x_api_key)

    if presented is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if require_admin:
        if admin_key is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Administrative authentication is not configured.",
            )
        if _matches(presented, admin_key):
            return AuthenticatedPrincipal(
                principal_id=f"api-admin:{_fingerprint(admin_key)}",
                role="admin",
            )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative authorization required.",
        )

    if read_key is None and admin_key is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API authentication is not configured.",
        )

    if admin_key is not None and _matches(presented, admin_key):
        return AuthenticatedPrincipal(
            principal_id=f"api-admin:{_fingerprint(admin_key)}",
            role="admin",
        )
    if read_key is not None and _matches(presented, read_key):
        return AuthenticatedPrincipal(
            principal_id=f"api-read:{_fingerprint(read_key)}",
            role="read",
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_read_principal(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> AuthenticatedPrincipal:
    return authenticate_principal(
        authorization=authorization,
        x_api_key=x_api_key,
        require_admin=False,
    )


def require_admin_principal(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> AuthenticatedPrincipal:
    return authenticate_principal(
        authorization=authorization,
        x_api_key=x_api_key,
        require_admin=True,
    )


def generate_test_api_key() -> str:
    """Helper for tests; never used as a default production secret."""
    return secrets.token_urlsafe(32)
