import jwt
import time
from uuid import uuid4
import os
from motor.motor_asyncio import AsyncIOMotorClient
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
import logging
import datetime as dt
from fastapi import HTTPException
from pathlib import Path
from typing import Union
from keycloak import KeycloakOpenID
import httpx

logger = logging.getLogger(__name__)

def load_private_key(path: Union[str, Path]):
    """
    Charge une clé privée depuis :un fichier PEM (-----BEGIN PRIVATE KEY-----)  

    Args: path: chemin du fichier.

    Returns:
        private_key (RSAPrivateKey | EllipticCurvePrivateKey | None)
    """
    path = Path(path)

    try:
        data = path.read_bytes()

        key = serialization.load_pem_private_key(
            data,
            password=None,
            backend=default_backend()
        )
        logger.info("✅  Private key loaded from PEM")
        return key

    except Exception as e:
        logger.error(f"❌  Failed to load private key: {e}")
        raise

def get_keycloak_openid_for_client(client_id: str, key_path: Union[str, Path]) -> KeycloakOpenID:
    """
    Retourne un KeycloakOpenID configuré pour l’authentification client-jwt
    en utilisant la clé privée stockée dans key_path.
    """
    # Charge la clé privée en PEM
    private_key_pem = Path(key_path).read_text()
    return KeycloakOpenID(
        server_url=os.getenv("KEYCLOAK_INTERNAL_SERVER_URL"),
        realm_name=os.getenv("KEYCLOAK_REALM"),
        client_id=client_id,
        client_secret_key=private_key_pem,
        verify=True
    )

async def get_access_token(client_id: str,
                           key_path: str,
                           lifetime: int = 300) -> str:
    """
    Authenticate this AI service via client-jwt and return a Keycloak access token.
    """
    oidc = get_keycloak_openid_for_client(client_id, key_path)

    # Load private key object
    private_key = load_private_key(key_path)

    openid_config = oidc.well_known()
    token_endpoint = openid_config.get("token_endpoint")

    # 2) Construction du payload JWT
    now = int(time.time())
    payload = {
        "iss": client_id,
        "sub": client_id,
        "aud": token_endpoint,    # correspondra exactement à l'une des audiences attendues
        "iat": now,
        "exp": now + lifetime,
        "jti": str(uuid4()),
    }
    
    client_assertion = jwt.encode(payload, private_key, algorithm="RS256")

    # Exchange assertion for token
    token_response = oidc.token(
        grant_type="client_credentials",
        client_id=client_id,
        client_assertion_type="urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
        client_assertion=client_assertion
    )
    
    access_token = token_response.get("access_token")
    
    if not access_token:
        logger.error(f"Failed to obtain access_token for client {client_id}")
        raise HTTPException(500, "Keycloak token request failed")
    
    return access_token

async def fetch_egm(episode_id: str, headers: dict):
    """Récupère l'EGM d'un épisode"""
    url = f"http://fastapi-app:8000/episode/{episode_id}/egm"
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        if response.status_code == 200:
            logger.info(f"EGM obtenu avec succès pour episode_id: {episode_id}")
            return response.content
        else:
            logger.error(f"Erreur lors de l'obtention de l'EGM: {response.status_code} {response.text}")
            response.raise_for_status()
            

def get_mongodb_client() -> AsyncIOMotorClient:
    return AsyncIOMotorClient(os.getenv('MONGODB_URL'))