from fastapi.security import OAuth2AuthorizationCodeBearer
from keycloak import KeycloakOpenID
from settings import *
from fastapi import Security, HTTPException, status,Depends
from schemas import User
from aiohttp import ClientSession
import logging
logger = logging.getLogger('uvicorn.error')

# This is used for fastapi docs authentification


# This actually does the auth checks
# client_secret_key is not mandatory if the client is public on keycloak
keycloak_openid = KeycloakOpenID(
    server_url=KEYCLOAK_INTERNAL_SERVER_URL,
    client_id=KEYCLOAK_CLIENT_ID,
    realm_name=KEYCLOAK_REALM,
    verify=True
)

oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl=KEYCLOAK_AUTH_URL,
    tokenUrl=KEYCLOAK_TOKEN_URL
)

# Get the payload/token from keycloak
async def get_payload(token: str = Security(oauth2_scheme)) -> dict:
    try:
        return keycloak_openid.decode_token(
            token
        )
    except Exception as e:
        logger.error
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e), # "Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
# Get user infos from the payload
async def get_user_info(payload: dict = Depends(get_payload)) -> User:
    try:
        return User(
            id=payload.get("sub"),
            username=payload.get("preferred_username"),
            email=payload.get("email"),
            first_name=payload.get("given_name"),
            last_name=payload.get("family_name"),
            realm_roles=payload.get("realm_access", {}).get("roles", []),
            client_roles=payload.get("realm_access", {}).get("roles", [])
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e), # "Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )