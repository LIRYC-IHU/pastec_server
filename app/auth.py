from fastapi.security import OAuth2AuthorizationCodeBearer, HTTPBearer, OAuth2PasswordBearer
from keycloak import KeycloakOpenID
from settings import *
from fastapi import Security, HTTPException, status, Depends
from schemas import User, AIModel
from jwt import decode, encode, InvalidTokenError, ExpiredSignatureError, get_unverified_header
from functools import lru_cache
import logging
import os
import httpx
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Keycloak Configuration
keycloak_openid = KeycloakOpenID(
    server_url=KEYCLOAK_INTERNAL_SERVER_URL,
    client_id=KEYCLOAK_CLIENT_ID,
    realm_name=KEYCLOAK_REALM,
    client_secret_key=KEYCLOAK_CLIENT_SECRET,
    verify=True,
)

# Security Schemes
oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl=KEYCLOAK_AUTH_URL,
    tokenUrl=KEYCLOAK_TOKEN_URL,
)
oauth2_scheme_app = OAuth2PasswordBearer(tokenUrl=KEYCLOAK_TOKEN_URL)
security = HTTPBearer()

# Cache for JWKS
@lru_cache
async def fetch_jwks():
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{KEYCLOAK_SERVER_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/certs")
        response.raise_for_status()
        return response.json()

# Get Public Key from JWKS
async def get_public_key(kid: str):
    jwks = await fetch_jwks()
    for key in jwks["keys"]:
        if key["kid"] == kid:
            return jwt.algorithms.RSAAlgorithm.from_jwk(key)
    raise HTTPException(status_code=401, detail="Key ID not found in JWKS")

# Decode and Validate Token
async def decode_token(token: str, audience: str) -> dict:
    try:
        unverified_header = get_unverified_header(token)
        logger.info(f"En-tête non vérifié du token: {unverified_header}")
        payload = decode(token, options={"verify_signature": False}, algorithms=["RS256"])
        logger.info(f"Payload décodé: {payload}")
        return payload
    except Exception as e:
        logger.error(f"Erreur lors du décodage du token: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

# Get Payload from Token
async def get_payload(token: str = Security(oauth2_scheme)):
    audience = f"{KEYCLOAK_SERVER_URL}/realms/{KEYCLOAK_REALM}"
    return await decode_token(token, audience)

# Get User Info from Token
async def get_user_info(payload: dict = Depends(get_payload)) -> User:
    try:
        return User(
            id=payload.get("sub"),
            username=payload.get("preferred_username"),
            email=payload.get("email"),
            first_name=payload.get("given_name"),
            last_name=payload.get("family_name"),
            realm_roles=payload.get("realm_access", {}).get("roles", []),
            client_roles=payload.get("resource_access", {}).get(KEYCLOAK_CLIENT_ID, {}).get("roles", []),
        )
    except Exception as e:
        logger.error(f"Error extracting user info: {str(e)}")
        raise HTTPException(status_code=400, detail="Invalid token payload")

# Role Check Dependency
def check_role(role: str):
    async def _check_role(user: User = Depends(get_user_info)):
        if role not in user.realm_roles:
            raise HTTPException(
                status_code=403, detail="User does not have the required role"
            )
        return user
    return _check_role

# Get Application Info
async def get_ai_model_info(payload: dict = Depends(get_payload)) -> AIModel:
    try:
        return AIModel(
            client_id=payload.get("sub", "")
        )
    except Exception as e:
        logger.error(f"Error extracting AI model info: {str(e)}")
        raise HTTPException(status_code=400, detail="Invalid token payload")

# Get Token with Username and Password
async def get_token_with_credentials(username: str, password: str) -> dict:
    try:
        return keycloak_openid.token(
            username=username, password=password, grant_type="password"
        )
    except Exception as e:
        logger.error(f"Authentication failed: {str(e)}")
        raise HTTPException(status_code=401, detail="Authentication failed")

# Combine User and Application Authentication
async def get_auth_info(payload: dict = Depends(get_payload)):
    try:
        if "preferred_username" in payload:
            return {"type": "user", "info": await get_user_info(payload)}
        else:
            return {"type": "application", "info": await get_ai_model_info(payload)}
    except Exception as e:
        logger.error(f"Error in get_auth_info: {str(e)}")
        raise HTTPException(status_code=401, detail="Authentication failed")