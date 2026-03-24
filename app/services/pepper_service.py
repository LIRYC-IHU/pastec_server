import hashlib
import secrets
from typing import Optional

from fastapi import HTTPException

from db import CenterPepper, engine


def normalize_center(center: str) -> str:
    return center.strip().lower()


def generate_pepper() -> str:
    return secrets.token_hex(32)


def hash_pepper(pepper: str) -> str:
    return hashlib.sha256(pepper.strip().lower().encode("utf-8")).hexdigest()


async def get_center_pepper_record(center: str) -> Optional[CenterPepper]:
    normalized_center = normalize_center(center)
    return await engine.find_one(CenterPepper, CenterPepper.center == normalized_center)


async def create_center_pepper(center: str, created_by: Optional[str] = None) -> tuple[CenterPepper, str]:
    normalized_center = normalize_center(center)
    existing = await get_center_pepper_record(normalized_center)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"A pepper already exists for center '{normalized_center}'",
        )

    pepper = generate_pepper()
    record = CenterPepper(
        center=normalized_center,
        pepper_hash=hash_pepper(pepper),
        created_by=created_by,
    )
    await engine.save(record)
    return record, pepper
