
import os
from motor.motor_asyncio import AsyncIOMotorClient
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
import logging
import jwt
import datetime as dt
import httpx
from fastapi import HTTPException
from base64 import b64decode
from pathlib import Path
from cryptography.hazmat.primitives.serialization import pkcs12, Encoding, PublicFormat
import hashlib, base64
from uuid import uuid4
from typing import Optional, Union
from keycloak import KeycloakAdmin

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
    
async def get_access_token(client_id: str,
                           key_path: str,
                           lifetime: int = 300) -> str:
    """
    Authenticate *this* AI service against Keycloak using
    Private-Key JWT and return a regular access-token.

    Parameters
    ----------
    client_id      : the Keycloak *Client ID* (e.g. "ai_bsc_af")
    key_path       : path to the PEM or PKCS#12 file holding the **private** key
    key_password   : password for the PKCS#12 (None for PEM or unprotected .p12)
    lifetime       : JWT assertion lifetime, seconds (default 5 min)

    Returns
    -------
    str – Keycloak access token
    """
    # 1) Load private key ------------------------------------------------------
    private_key = load_private_key(key_path)
    if private_key is None:
        raise HTTPException(500, "Unable to load private key")
    
    realm   = os.getenv("KEYCLOAK_REALM")
    host    = os.getenv("KEYCLOAK_INTERNAL_SERVER_URL")  

    kc = KeycloakAdmin(
        server_url=f"{host}",
        username=os.getenv("KEYCLOAK_PASTEC_ADMIN"),
        password=os.getenv("KEYCLOAK_PASTEC_ADMIN_PASSWORD"),
        realm_name=os.getenv("KEYCLOAK_REALM"),
        verify=True
    )

    try: 
        logger.info(f"trying to get client_id {client_id}")
        clients = kc.get_clients()
        logger.info(f"nombre de clients: {len(clients)}")
        uuid = kc.get_client_id(client_id)
        if uuid is None:
            logger.error(f"Client ID {client_id} not found in Keycloak")
            raise HTTPException(500, f"Client ID {client_id} not found in Keycloak")
        logger.info(f"Client ID {client_id} found in Keycloak: {uuid}")
    except Exception as e:
        logger.error(f"Error fetching client ID {client_id}: {e}")
        raise HTTPException(500, f"Error fetching client ID")

    # 2) Build client-assertion -----------------------------------------------
    realm   = os.getenv("KEYCLOAK_REALM")
    host    = os.getenv("KEYCLOAK_INTERNAL_SERVER_URL") 
    domain = os.getenv("KEYCLOAK_SERVER_URL")
    
    # e.g. https://kc.example.com
    if not (realm and host):
        logger.error("KEYCLOAK_* env-vars missing")
        logger.error(f"KEYCLOAK_REALM: {realm}")
        logger.error(f"KEYCLOAK_URL: {host}")   
        raise HTTPException(500, "KEYCLOAK_* env-vars missing")

    token_endpoint = f"{host}/realms/{realm}/protocol/openid-connect/token"
    domain_endpoint = f"{domain}/realms/{realm}/protocol/openid-connect/token"
    
    logger.info(f"Keycloak token endpoint: {token_endpoint}")

    now = int(dt.datetime.now(dt.timezone.utc).timestamp())
    
    assertion_payload = {
        "iss": client_id,  # **must** be the client ID
        "sub": client_id,  # **must** be the client ID
        "aud": domain_endpoint,    # **must** be the exact token URL
        "iat": now,
        "exp": now + lifetime,
        "jti": str(uuid4()),  # unique ID for this assertion
    }

    public_key = private_key.public_key()
    
    der = public_key.public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)
    sha256 = hashlib.sha256(der).digest()
    kid = base64.urlsafe_b64encode(sha256).rstrip(b'=').decode()
    
    headers = {
        "kid": kid
    }

    client_assertion = jwt.encode(assertion_payload,
                                  private_key,
                                  algorithm="RS256",
                                  headers=headers)
    
    # 3) Exchange assertion for an access-token -------------------------------
    data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_assertion_type":
            "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
        "client_assertion": client_assertion
    }

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(token_endpoint, data=data)
        if resp.status_code != 200:
            raise HTTPException(resp.status_code,
                                f"Keycloak token request failed: {resp.text}")

        token = resp.json()["access_token"]
        logger.info(f"✅  Access token obtained for client_id {client_id}")
        logger.debug(f"Access token: {token}")
        return token

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