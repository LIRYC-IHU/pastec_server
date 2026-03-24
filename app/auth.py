import json
import logging
import os
import time
from typing import Any, Iterable, Optional

import httpx
import jwt
from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import HTTPBearer, OAuth2AuthorizationCodeBearer, OAuth2PasswordBearer
from jwt import ExpiredSignatureError, InvalidTokenError, decode as jwt_decode, get_unverified_header
from keycloak import KeycloakOpenID

from db import AIModel, Center, User, UserType
from services.pepper_service import get_center_pepper_record
from settings import (
    KEYCLOAK_AUTH_URL,
    KEYCLOAK_CLIENT_ID,
    KEYCLOAK_INTERNAL_SERVER_URL,
    KEYCLOAK_REALM,
    KEYCLOAK_SERVER_URL,
    KEYCLOAK_TOKEN_URL,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

keycloak_openid = KeycloakOpenID(
    server_url=KEYCLOAK_INTERNAL_SERVER_URL,
    client_id=KEYCLOAK_CLIENT_ID,
    realm_name=KEYCLOAK_REALM,
    verify=True,
)

oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl=KEYCLOAK_AUTH_URL,
    tokenUrl=KEYCLOAK_TOKEN_URL,
)
oauth2_scheme_app = OAuth2PasswordBearer(tokenUrl=KEYCLOAK_TOKEN_URL)
security = HTTPBearer()

AUTH_CENTER_GROUP_PREFIX = os.getenv("AUTH_CENTER_GROUP_PREFIX", "centers").strip("/")
AUTH_PROJECT_GROUP_PREFIX = os.getenv("AUTH_PROJECT_GROUP_PREFIX", "projects").strip("/")
AUTH_CENTER_ROLE_PREFIX = os.getenv("AUTH_CENTER_ROLE_PREFIX", "center:")
AUTH_PROJECT_ROLE_PREFIX = os.getenv("AUTH_PROJECT_ROLE_PREFIX", "project:")
AUTH_GLOBAL_ACCESS_ROLES = {
    role.strip()
    for role in os.getenv("AUTH_GLOBAL_ACCESS_ROLES", "pastec-admin").split(",")
    if role.strip()
}
AUTH_ALLOW_LEGACY_UNSCOPED_ACCESS = os.getenv(
    "AUTH_ALLOW_LEGACY_UNSCOPED_ACCESS", "true"
).lower() in {"1", "true", "yes", "on"}
_JWKS_CACHE_TTL_SECONDS = int(os.getenv("JWKS_CACHE_TTL_SECONDS", "300"))

_jwks_cache: dict[str, Any] = {"value": None, "expires_at": 0.0}


def _normalize_enum_value(value: Any) -> str:
    if isinstance(value, tuple):
        value = value[0]
    return str(value).strip().lower()


KNOWN_CENTERS = {_normalize_enum_value(center.value) for center in Center}
KNOWN_USER_TYPES = {_normalize_enum_value(user_type.value) for user_type in UserType}


def _normalize_list_claim(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Iterable):
        return [str(item) for item in value if item is not None]
    return [str(value)]


def _dedupe(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = str(value).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _normalize_group(group: str) -> str:
    return group.strip().strip("/")


def _extract_prefixed_values(values: Iterable[str], prefix: str) -> list[str]:
    extracted: list[str] = []
    for value in values:
        if value.startswith(prefix):
            extracted.append(value[len(prefix) :].strip().lower())
    return extracted


def _extract_group_children(groups: Iterable[str], prefix: str) -> list[str]:
    extracted: list[str] = []
    for raw_group in groups:
        group = _normalize_group(raw_group)
        parts = [part for part in group.split("/") if part]
        if len(parts) >= 2 and parts[0].lower() == prefix.lower():
            extracted.append(parts[1].strip().lower())
    return extracted


def _extract_centers(payload: dict[str, Any], roles: list[str], groups: list[str]) -> list[str]:
    direct_centers = [
        value.strip().lower()
        for value in _normalize_list_claim(payload.get("centers")) + _normalize_list_claim(payload.get("center"))
    ]
    role_centers = _extract_prefixed_values(roles, AUTH_CENTER_ROLE_PREFIX)
    group_centers = _extract_group_children(groups, AUTH_CENTER_GROUP_PREFIX)
    legacy_group_centers = [
        _normalize_group(group).lower()
        for group in groups
        if _normalize_group(group).lower() in KNOWN_CENTERS
    ]
    return _dedupe(direct_centers + role_centers + group_centers + legacy_group_centers)


def _extract_projects(payload: dict[str, Any], roles: list[str], groups: list[str]) -> list[str]:
    direct_projects = [
        value.strip().lower()
        for value in _normalize_list_claim(payload.get("projects")) + _normalize_list_claim(payload.get("project"))
    ]
    role_projects = _extract_prefixed_values(roles, AUTH_PROJECT_ROLE_PREFIX)
    group_projects = _extract_group_children(groups, AUTH_PROJECT_GROUP_PREFIX)
    return _dedupe(direct_projects + role_projects + group_projects)


def _extract_user_type(payload: dict[str, Any], roles: list[str], groups: list[str]) -> Optional[str]:
    candidates = (
        _normalize_list_claim(payload.get("user_type"))
        + roles
        + [_normalize_group(group) for group in groups]
    )
    for candidate in candidates:
        normalized = candidate.strip().lower()
        if normalized in KNOWN_USER_TYPES:
            return normalized
    return None


async def fetch_jwks() -> dict[str, Any]:
    now = time.time()
    if _jwks_cache["value"] and _jwks_cache["expires_at"] > now:
        return _jwks_cache["value"]

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{KEYCLOAK_INTERNAL_SERVER_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/certs"
        )
        response.raise_for_status()
        jwks = response.json()
        _jwks_cache["value"] = jwks
        _jwks_cache["expires_at"] = now + _JWKS_CACHE_TTL_SECONDS
        return jwks


async def get_public_key(kid: str):
    jwks = await fetch_jwks()
    for key in jwks["keys"]:
        if key["kid"] == kid:
            return jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(key))
    raise HTTPException(status_code=401, detail="Key ID not found in JWKS")


async def decode_token(token: str, audience: str | None = None) -> dict[str, Any]:
    try:
        unverified_header = get_unverified_header(token)
        public_key = await get_public_key(unverified_header["kid"])
        payload = jwt_decode(
            token,
            key=public_key,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )
        return payload
    except ExpiredSignatureError as exc:
        logger.warning("Expired token received")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except (InvalidTokenError, KeyError) as exc:
        logger.error("Invalid token: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def build_user_from_payload(payload: dict[str, Any]) -> User:
    realm_access = payload.get("realm_access") or {}
    resource_access = payload.get("resource_access") or {}
    realm_roles = _dedupe(realm_access.get("roles", []))
    client_roles = _dedupe(resource_access.get(KEYCLOAK_CLIENT_ID, {}).get("roles", []))
    roles = _dedupe(realm_roles + client_roles)
    raw_groups = _normalize_list_claim(payload.get("groups")) or _normalize_list_claim(
        payload.get("group-membership")
    )
    groups = _dedupe(_normalize_group(group) for group in raw_groups)
    centers = _extract_centers(payload, roles, groups)
    projects = _extract_projects(payload, roles, groups)
    primary_center = centers[0] if centers else None
    user_type = _extract_user_type(payload, roles, groups)

    return User(
        id=payload.get("sub"),
        username=payload.get("preferred_username"),
        email=payload.get("email"),
        first_name=payload.get("given_name"),
        last_name=payload.get("family_name"),
        realm_roles=realm_roles,
        client_roles=client_roles,
        roles=roles,
        groups=groups,
        centers=centers,
        projects=projects,
        primary_center=primary_center,
        user_type=user_type,
    )


def build_ai_model_from_payload(payload: dict[str, Any]) -> AIModel:
    resource_access = payload.get("resource_access") or {}
    return AIModel(
        client_id=payload.get("sub"),
        model_name=payload.get("client_id"),
        client_roles=resource_access.get(KEYCLOAK_CLIENT_ID, {}).get("roles", []),
        realm_roles=(payload.get("realm_access") or {}).get("roles", []),
    )


async def check_center_affiliation(token: str, center_name: str):
    audience = f"{KEYCLOAK_SERVER_URL}/realms/{KEYCLOAK_REALM}"
    payload = await decode_token(token, audience)
    user = build_user_from_payload(payload)
    normalized_center = center_name.strip().lower()
    if normalized_center not in user.centers:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User is not affiliated with the center: {center_name}",
        )


async def get_payload(token: str = Security(oauth2_scheme)):
    audience = f"{KEYCLOAK_SERVER_URL}/realms/{KEYCLOAK_REALM}"
    return await decode_token(token, audience)


async def get_user_info(payload: dict = Depends(get_payload)) -> User:
    logger.info("Human User Authentication")
    return build_user_from_payload(payload)


def check_role(role: str):
    async def _check_role(user: User = Depends(get_user_info)):
        if role not in user.roles:
            raise HTTPException(
                status_code=403, detail="User does not have the required role"
            )
        return user

    return _check_role


async def get_ai_model_info(payload: dict = Depends(get_payload)) -> AIModel:
    logger.info("AI Model Authentication")
    return build_ai_model_from_payload(payload)


async def get_token_with_credentials(username: str, password: str) -> dict:
    try:
        logger.info("Authenticating user with username and password")
        return keycloak_openid.token(
            username=username, password=password, grant_type="password"
        )
    except Exception as exc:
        logger.error("Authentication failed: %s", exc)
        raise HTTPException(status_code=401, detail="Authentication failed") from exc


async def get_refresh_token(refresh_token: str) -> dict:
    try:
        token_response = keycloak_openid.refresh_token(refresh_token)
        return {
            "access_token": token_response.get("access_token"),
            "refresh_token": token_response.get("refresh_token"),
            "expires_in": token_response.get("expires_in"),
        }
    except Exception as exc:
        logger.error("Refresh token failure: %s", exc)
        raise HTTPException(
            status_code=401,
            detail=f"Failed to refresh token: {str(exc)}",
        ) from exc


def _is_service_account(payload: dict) -> bool:
    return payload.get("preferred_username", "").startswith("service-account-")


async def get_auth_info(payload: dict = Depends(get_payload)):
    try:
        if _is_service_account(payload):
            return {"type": "application", "info": build_ai_model_from_payload(payload)}
        return {"type": "user", "info": build_user_from_payload(payload)}
    except Exception as exc:
        logger.error("Authentication failed: %s", exc)
        raise HTTPException(401, "Authentication failed") from exc


def has_global_access(user: User) -> bool:
    return any(role in AUTH_GLOBAL_ACCESS_ROLES for role in user.roles)


def get_episode_access_query(
    user: User,
    *,
    center_field: str = "center",
    projects_field: str = "projects",
) -> dict[str, Any]:
    if has_global_access(user):
        return {}

    clauses: list[dict[str, Any]] = []
    if user.centers:
        clauses.append({center_field: {"$in": user.centers}})
    if user.projects:
        clauses.append({projects_field: {"$in": user.projects}})
    if AUTH_ALLOW_LEGACY_UNSCOPED_ACCESS:
        clauses.append({center_field: {"$exists": False}})
        clauses.append({center_field: None})

    if not clauses:
        return {"_id": {"$exists": False}}

    return {"$or": clauses}


def can_access_resource(
    user: User,
    *,
    center: Optional[str],
    projects: Optional[Iterable[str]] = None,
) -> bool:
    if has_global_access(user):
        return True

    normalized_center = center.strip().lower() if isinstance(center, str) and center.strip() else None
    normalized_projects = {
        str(project).strip().lower()
        for project in (projects or [])
        if str(project).strip()
    }

    if normalized_center and normalized_center in user.centers:
        return True
    if normalized_projects and normalized_projects.intersection(set(user.projects)):
        return True
    if normalized_center is None and AUTH_ALLOW_LEGACY_UNSCOPED_ACCESS:
        return True
    return False


def ensure_resource_access(
    user: User,
    *,
    center: Optional[str],
    projects: Optional[Iterable[str]] = None,
) -> None:
    if not can_access_resource(user, center=center, projects=projects):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not allowed to access this resource scope",
        )


def resolve_user_center(user: User, requested_center: Optional[str] = None) -> str:
    if has_global_access(user) and requested_center:
        return requested_center.strip().lower()

    if requested_center:
        normalized_center = requested_center.strip().lower()
        if normalized_center not in user.centers:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User is not allowed to write data for center '{requested_center}'",
            )
        return normalized_center

    if user.primary_center:
        return user.primary_center
    if len(user.centers) == 1:
        return user.centers[0]

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Unable to resolve a center for this user",
    )


def parse_projects(projects_value: Optional[str]) -> list[str]:
    if not projects_value:
        return []
    try:
        if projects_value.strip().startswith("["):
            parsed = json.loads(projects_value)
            return _dedupe(str(item).strip().lower() for item in parsed if str(item).strip())
    except json.JSONDecodeError:
        logger.warning("Invalid JSON project list received, falling back to CSV parsing")

    return _dedupe(
        project.strip().lower()
        for project in projects_value.split(",")
        if project.strip()
    )


async def ensure_center_pepper_binding(request: Request, center: str) -> None:
    normalized_center = center.strip().lower()
    record = await get_center_pepper_record(normalized_center)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"No registered pepper fingerprint for center '{center}'",
        )

    request_center = request.headers.get("x-pastec-center")
    if request_center and request_center.strip().lower() != normalized_center:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Center header does not match the authorized upload center",
        )

    fingerprint = request.headers.get("x-pastec-pepper-fingerprint", "").strip().lower()
    if not fingerprint:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing pepper fingerprint header",
        )

    if fingerprint != record.pepper_hash:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid pepper fingerprint for the requested center",
        )


def check_authorization(role: str | None = None):
    async def _check_authorization(payload: dict = Depends(get_auth_info)):
        info = payload["info"]
        if role is not None:
            roles = getattr(info, "roles", None) or (
                getattr(info, "client_roles", []) + getattr(info, "realm_roles", [])
            )
            if role not in roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"User does not have the required role: {role}",
                )
        return info

    return _check_authorization
