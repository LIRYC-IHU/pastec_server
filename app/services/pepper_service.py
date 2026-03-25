import hashlib
import secrets
from typing import Optional

from fastapi import HTTPException

from db import CenterPepper, engine


def normalize_center(center: str) -> str:
    return center.strip().lower()


def generate_pepper() -> str:
    return secrets.token_hex(32)


def normalize_pepper(pepper: str) -> str:
    normalized = pepper.strip().lower()
    if len(normalized) != 64 or any(char not in "0123456789abcdef" for char in normalized):
        raise HTTPException(
            status_code=400,
            detail="Pepper must be a 64-character hexadecimal string",
        )
    return normalized


def hash_pepper(pepper: str) -> str:
    return hashlib.sha256(normalize_pepper(pepper).encode("utf-8")).hexdigest()


async def get_center_pepper_record(center: str) -> Optional[CenterPepper]:
    normalized_center = normalize_center(center)
    return await engine.find_one(CenterPepper, CenterPepper.center == normalized_center)


async def create_center_pepper(
    center: str,
    created_by: Optional[str] = None,
    pepper: Optional[str] = None,
) -> tuple[CenterPepper, str, bool]:
    normalized_center = normalize_center(center)
    existing = await get_center_pepper_record(normalized_center)
    if existing:
        if pepper:
            resolved_pepper = normalize_pepper(pepper)
            if existing.pepper_hash == hash_pepper(resolved_pepper):
                return existing, resolved_pepper, False
        raise HTTPException(
            status_code=409,
            detail=f"A pepper already exists for center '{normalized_center}'",
        )

    resolved_pepper = normalize_pepper(pepper) if pepper else generate_pepper()
    record = CenterPepper(
        center=normalized_center,
        pepper_hash=hash_pepper(resolved_pepper),
        created_by=created_by,
    )
    await engine.save(record)
    return record, resolved_pepper, True
