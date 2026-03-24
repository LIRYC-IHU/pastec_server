import base64
import json
import os
from datetime import datetime, timezone
from typing import Any

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey
from fastapi import HTTPException


CONFIG_BUNDLE_KIND = "pastec-center-config"
CONFIG_BUNDLE_VERSION = 1


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _canonical_json(data: dict[str, Any]) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _load_private_key() -> RSAPrivateKey:
    raw_key = os.getenv("CONFIG_BUNDLE_SIGNING_PRIVATE_KEY", "").strip()
    if not raw_key:
        raise HTTPException(
            status_code=500,
            detail="CONFIG_BUNDLE_SIGNING_PRIVATE_KEY is not configured",
        )
    try:
        return serialization.load_pem_private_key(
            raw_key.encode("utf-8"),
            password=None,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="CONFIG_BUNDLE_SIGNING_PRIVATE_KEY is invalid",
        ) from exc


def _load_public_key() -> RSAPublicKey:
    raw_key = os.getenv("CONFIG_BUNDLE_SIGNING_PUBLIC_KEY", "").strip()
    if raw_key:
        try:
            return serialization.load_pem_public_key(raw_key.encode("utf-8"))
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail="CONFIG_BUNDLE_SIGNING_PUBLIC_KEY is invalid",
            ) from exc

    return _load_private_key().public_key()


def get_public_key_pem() -> str:
    public_key = _load_public_key()
    return public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")


def build_signed_center_bundle(
    *,
    center: str,
    pepper: str,
    api_url: str | None,
    created_by: str | None,
) -> dict[str, Any]:
    payload = {
        "kind": CONFIG_BUNDLE_KIND,
        "version": CONFIG_BUNDLE_VERSION,
        "center": center.strip().lower(),
        "pepper": pepper.strip(),
        "api_url": api_url.strip().rstrip("/") if api_url else None,
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "issued_by": created_by,
    }

    payload_bytes = _canonical_json(payload)
    private_key = _load_private_key()
    signature = private_key.sign(
        payload_bytes,
        padding.PKCS1v15(),
        hashes.SHA256(),
    )

    return {
        "payload": payload,
        "signature": _b64url_encode(signature),
        "algorithm": "RS256",
    }
