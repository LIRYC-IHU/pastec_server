from fastapi.security import OAuth2AuthorizationCodeBearer
from keycloak import KeycloakOpenID
from settings import *
from fastapi import Security, HTTPException, status, Depends
from schemas import User
from jwcrypto import jwk, jws
from functools import lru_cache


keycloak_openid = KeycloakOpenID(
    server_url=KEYCLOAK_INTERNAL_SERVER_URL,
    client_id=KEYCLOAK_CLIENT_ID,
    realm_name=KEYCLOAK_REALM,
    client_secret_key=KEYCLOAK_CLIENT_SECRET,
    verify=True
)

oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl=KEYCLOAK_AUTH_URL,
    tokenUrl=KEYCLOAK_TOKEN_URL
)


@lru_cache
def get_public_key() -> str:
    # Get the public key from the server
    key = (
        "-----BEGIN PUBLIC KEY-----\n"
        + keycloak_openid.public_key()
        + "\n-----END PUBLIC KEY-----"
    )
    
    key = jwk.JWK.from_pem(key.encode("utf-8"))
    return key

# Get the payload/token from keycloak
async def get_payload(token: str = Security(oauth2_scheme)) -> dict:
    key = get_public_key()
    try:
        return keycloak_openid.decode_token(token, key=key, validate=True)
    except jws.InvalidJWSSignature: 
        # Reset the public key cache
        get_public_key.cache_clear()
        key = get_public_key()
        try:
            return keycloak_openid.decode_token(token, key=key, validate=True)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail= f'Peristent error after public key refresh: {e}',
                headers={"WWW-Authenticate": "Bearer"},
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail = str(e), 
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
            detail=str(e), 
            headers={"WWW-Authenticate": "Bearer"},
        )

def check_role(role: str):
    async def _check_role(user: User = Depends(get_user_info)):
        if role in user.realm_roles:
            return
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='User does not have the appropriate roles', 
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _check_role

# handle login from keycloak

async def get_token_with_credentials(username: str, password: str) -> dict:
    try:
        token = keycloak_openid.token(
            username=username,
            password=password,
            grant_type=["password"]
        )
        return token
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Échec de l'authentification: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )